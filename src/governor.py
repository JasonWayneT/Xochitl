"""Session-level token budget governor.

Tracks estimated token spend across all LLM turns in a session and applies
progressive routing restrictions to prevent runaway cloud cost accumulation.

Tier model (ascending restriction):

    FULL          < XCH_PREFER_LOCAL_TOKENS  — normal routing; cloud allowed
    PREFER_LOCAL  ≥ XCH_PREFER_LOCAL_TOKENS  — one-time warning; routing unchanged
    LOCAL_ONLY    ≥ XCH_LOCAL_ONLY_TOKENS    — cloud blocked; force_route → local
    HARD_STOP     ≥ XCH_HARD_STOP_TOKENS     — no LLM call; canned budget message

See CR-026, ADR-004.
"""
# Implements FR-ORCH-025 (tiered routing based on session token budget)
# Implements NFR-PERF-011 (character-count token estimation, no I/O overhead)

from __future__ import annotations

import os
from enum import Enum


# ── Tier definition ───────────────────────────────────────────────────────────

class Tier(str, Enum):
    """Routing restriction tier, ordered from least to most restrictive."""
    FULL = "full"
    PREFER_LOCAL = "prefer_local"
    LOCAL_ONLY = "local_only"
    HARD_STOP = "hard_stop"


# ── Configurable thresholds (estimated tokens) ────────────────────────────────

def _threshold(env_var: str, default: int) -> int:
    """Read an integer env var with a fallback default."""
    raw = os.getenv(env_var, "")
    try:
        return int(raw) if raw.strip() else default
    except ValueError:
        return default


def _load_thresholds() -> tuple[int, int, int]:
    """Return (prefer_local, local_only, hard_stop) thresholds.

    Called at module import time so the governor picks up env vars set
    before the process starts.  Tests that need to vary thresholds should
    reload the module after patching os.environ.
    """
    prefer = _threshold("XCH_PREFER_LOCAL_TOKENS", 20_000)
    local  = _threshold("XCH_LOCAL_ONLY_TOKENS",   40_000)
    hard   = _threshold("XCH_HARD_STOP_TOKENS",    80_000)
    return prefer, local, hard


_PREFER_LOCAL_THRESHOLD, _LOCAL_ONLY_THRESHOLD, _HARD_STOP_THRESHOLD = _load_thresholds()


# ── Token estimation (ADR-004) ────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters (OpenAI rule of thumb).

    Returns at least 1 to avoid zero-token turns from empty strings.
    Implements NFR-PERF-011.
    """
    return max(1, len(text) // 4)


# ── Governor ──────────────────────────────────────────────────────────────────

class SessionGovernor:
    """Tracks estimated token spend and exposes the current routing tier.

    Intended to be instantiated once per ``XochitlChat`` session.

    Implements FR-ORCH-025.
    """

    def __init__(self) -> None:
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        # Track which tiers have already triggered a warning this session.
        self._warned: set[Tier] = set()
        # Track approach-level warnings (75%, 90% of next-tier gap). FR-JARV-005.
        self._warned_approach: set[str] = set()

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def total_tokens(self) -> int:
        """Cumulative estimated tokens (prompt + completion) this session."""
        return self._prompt_tokens + self._completion_tokens

    def tier(self) -> Tier:
        """Return the current routing tier based on accumulated token estimate."""
        total = self.total_tokens
        if total >= _HARD_STOP_THRESHOLD:
            return Tier.HARD_STOP
        if total >= _LOCAL_ONLY_THRESHOLD:
            return Tier.LOCAL_ONLY
        if total >= _PREFER_LOCAL_THRESHOLD:
            return Tier.PREFER_LOCAL
        return Tier.FULL

    # ── Actions ───────────────────────────────────────────────────────────────

    def record_turn(self, prompt: str, response: str) -> None:
        """Accumulate estimated token usage for one completed LLM turn.

        *prompt* is the user message text; *response* is the assistant reply.
        System prompt and context injections are not counted (see ADR-004).
        """
        self._prompt_tokens     += _estimate_tokens(prompt)
        self._completion_tokens += _estimate_tokens(response)

    def force_route(self) -> str | None:
        """Return a local-category force_route string when cloud must be blocked.

        Returns ``"general"`` (a local-routed TieredRouter category) for
        LOCAL_ONLY and HARD_STOP tiers; ``None`` for FULL and PREFER_LOCAL.
        """
        if self.tier() in (Tier.LOCAL_ONLY, Tier.HARD_STOP):
            return "general"
        return None

    def should_warn(self, t: Tier) -> bool:
        """Return True the first time this tier is seen; False on repeats.

        Prevents repeated warning messages across turns within the same tier.
        Implements AC-CR026-007.
        """
        if t not in self._warned:
            self._warned.add(t)
            return True
        return False

    def approach_pct(self, next_tier: Tier) -> float:
        """Return progress (0.0–1.0) toward the next tier's threshold. FR-JARV-005.

        Used to surface gradual budget warnings at 75% and 90% approach.

        Args:
            next_tier: The tier whose threshold we are approaching.

        Returns:
            Float in [0.0, 1.0] — fraction of the current-tier gap consumed.
        """
        total = self.total_tokens
        current = self.tier()
        thresholds = {
            Tier.PREFER_LOCAL: _PREFER_LOCAL_THRESHOLD,
            Tier.LOCAL_ONLY: _LOCAL_ONLY_THRESHOLD,
            Tier.HARD_STOP: _HARD_STOP_THRESHOLD,
        }
        target = thresholds.get(next_tier)
        if target is None:
            return 0.0
        # Lower bound is the current tier's threshold (or 0 for FULL).
        lower_thresholds = {
            Tier.PREFER_LOCAL: 0,
            Tier.LOCAL_ONLY: _PREFER_LOCAL_THRESHOLD,
            Tier.HARD_STOP: _LOCAL_ONLY_THRESHOLD,
        }
        lower = lower_thresholds.get(next_tier, 0)
        if current.value >= next_tier.value:
            return 1.0
        gap = target - lower
        if gap <= 0:
            return 0.0
        if total <= lower:
            return 0.0
        return min(1.0, (total - lower) / gap)

    def should_warn_approach(self, next_tier: Tier, level: float) -> bool:
        """Return True the first time approach reaches `level`; False on repeats. FR-JARV-005.

        Args:
            next_tier: Tier we are approaching.
            level: Threshold fraction (e.g., 0.75 or 0.90).

        Returns:
            True if this is the first time approach_pct >= level for this tier+level combo.
        """
        key = f"{next_tier.value}@{int(level * 100)}"
        if self.approach_pct(next_tier) >= level and key not in self._warned_approach:
            self._warned_approach.add(key)
            return True
        return False

    # ── Display ───────────────────────────────────────────────────────────────

    def status_line(self) -> str:
        """One-line human-readable status for the /budget command and warnings."""
        total = self.total_tokens
        t = self.tier()
        pct_to_local = min(100, int(total / _LOCAL_ONLY_THRESHOLD * 100))
        return (
            f"~{total:,} est. tokens this session | "
            f"tier: {t.value} | "
            f"{pct_to_local}% to local-only ({_LOCAL_ONLY_THRESHOLD:,} token threshold)"
        )

    def budget_detail(self) -> str:
        """Multi-line budget report for /budget slash command."""
        total = self.total_tokens
        t = self.tier()
        lines = [
            "[bold]Session Token Budget[/bold]",
            f"  Estimated usage : ~{total:,} tokens",
            f"  Prompt portion  : ~{self._prompt_tokens:,}",
            f"  Response portion: ~{self._completion_tokens:,}",
            f"  Current tier    : [bold]{t.value}[/bold]",
            "",
            "[bold]Thresholds[/bold]",
            f"  prefer-local : {_PREFER_LOCAL_THRESHOLD:,} tokens "
            f"(XCH_PREFER_LOCAL_TOKENS)",
            f"  local-only   : {_LOCAL_ONLY_THRESHOLD:,} tokens "
            f"(XCH_LOCAL_ONLY_TOKENS)",
            f"  hard-stop    : {_HARD_STOP_THRESHOLD:,} tokens "
            f"(XCH_HARD_STOP_TOKENS)",
            "",
            "[dim]Estimates use chars/4 approximation — not a billing meter.[/dim]",
        ]
        return "\n".join(lines)

    def budget_message(self) -> str:
        """Canned response returned to the user when HARD_STOP is reached."""
        return (
            f"I've reached this session's estimated token budget "
            f"(~{self.total_tokens:,} tokens). "
            f"To continue, start a new session with `xochitl chat`.\n\n"
            f"_Tip: set `XCH_HARD_STOP_TOKENS` to a higher value to extend the limit._"
        )
