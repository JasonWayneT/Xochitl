"""ContextManager — Engine-based context lifecycle for Xochitl.

Implements FR-ORCH-003 (PreFlight Fact Injection — SYSTEM_FACTS block)
Implements FR-ORCH-004 (Provenance Tagging — [SOURCE: USER/SYSTEM])
Implements FR-ORCH-005 (Skill Manifest — SkillManifestEngine injects tool definitions)
Implements NFR-PERF-004 (Token budget enforcement at 75% capacity)

Inspired by OpenClaw's Context Engine pattern (Ingest → Assemble → Compact).
Each Engine is responsible for a single context domain: Soul, Memory, File, Facts, Skills.
The ContextManager orchestrates them all and enforces the global token budget.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Token budget constants ───────────────────────────────────────────────────
# Local models (Gemma 8k context) vs cloud (Gemini 1M, but we self-limit to 32k)
_LOCAL_TOKEN_LIMIT  = 6_000   # conservative for gemma4-e4b 8k window
_CLOUD_TOKEN_LIMIT  = 28_000  # safe cloud budget
_BUDGET_RATIO       = 0.75    # compact when above this fraction of limit
_CHARS_PER_TOKEN    = 4       # rough approximation (4 chars ≈ 1 token)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token per 4 characters."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


_PROJECT_ROOT = Path(__file__).parent.parent


def _first_existing(paths: list[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def _persona_search_paths(filename: str, example_name: str) -> list[Path]:
    cwd = Path.cwd()
    home_config = Path.home() / ".xochitl"
    return [
        cwd / ".xochitl" / filename,
        home_config / filename,
        _PROJECT_ROOT / example_name,
    ]


# ── Engine base ──────────────────────────────────────────────────────────────

@dataclass
class ContextEngine:
    """Abstract engine for a single context domain.

    Lifecycle:
      ingest()   — load raw data (file reads, DB queries, etc.)
      assemble() — format data into a prompt block
      compact()  — summarize/truncate to fit within a token budget
    """

    name: str
    _content: str = field(default="", init=False, repr=False)
    _token_count: int = field(default=0, init=False, repr=False)
    _loaded_at: float = field(default=0.0, init=False, repr=False)

    def ingest(self) -> None:
        """Load data from the source. Override in subclasses."""
        pass

    def assemble(self) -> str:
        """Return the formatted prompt block for this engine."""
        return self._content

    def compact(self, max_tokens: int) -> str:
        """Return a summarized version within max_tokens. Override for smarter summarization."""
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        # Hard truncation with a note — subclasses should override with summarization
        truncated = text[:max_chars]
        # Try to break at a line boundary
        last_nl = truncated.rfind("\n")
        if last_nl > max_chars * 0.7:
            truncated = truncated[:last_nl]
        return truncated + f"\n\n[Context compacted — {len(text)} chars → {len(truncated)} chars]"

    @property
    def token_count(self) -> int:
        return _estimate_tokens(self.assemble())


# ── Concrete engines ─────────────────────────────────────────────────────────

@dataclass
class FactsEngine(ContextEngine):
    """Injects hard system facts to prevent LLM hallucination about its environment.

    Implements FR-ORCH-003 — PreFlight Fact Injection.
    Every prompt receives a [SYSTEM_FACTS] block with CWD, active project,
    local mode status, and WIP count.
    """

    _project: Optional[str] = field(default=None, init=False)
    _wip_count: int = field(default=0, init=False)
    _local_mode: bool = field(default=True, init=False)

    def __init__(self):
        super().__init__(name="facts")

    def ingest(self, project: Optional[str] = None, local_mode: bool = True) -> None:  # type: ignore[override]
        self._project = project
        self._local_mode = local_mode
        try:
            from src import database as db
            with db.get_connection() as conn:
                queue = db.get_queue(conn)
            self._wip_count = len(queue)
        except Exception:
            self._wip_count = 0
        self._loaded_at = time.time()

    def assemble(self) -> str:
        cwd = str(Path.cwd())
        project_line = f"Active Project: {self._project}" if self._project else "Active Project: None"
        mode = "Local (Ollama)" if self._local_mode else "Cloud"
        return (
            f"[SYSTEM_FACTS]\n"
            f"Current Directory: {cwd}\n"
            f"{project_line}\n"
            f"Execution Mode: {mode}\n"
            f"WIP Queue: {self._wip_count}/3 items\n"
            f"Platform: {os.name} (Windows)\n"
            f"[/SYSTEM_FACTS]"
        )

    def compact(self, max_tokens: int) -> str:
        # Facts block is always small — never compact it
        return self.assemble()


@dataclass
class SoulEngine(ContextEngine):
    """Loads and caches SOUL.md persona.

    CR-029: SOUL.md follows a four-section format:
      ## [IDENTITY]   — who Xochitl is (load-bearing anchor, always preserved)
      ## [VOICE]      — tone and cultural texture
      ## [VALUES]     — what she cares about
      ## [BOUNDARIES] — what she will not do

    Implements FR-ORCH-029, NFR-ORCH-004, NFR-ORCH-005.
    """

    # Priority order for compact() — [IDENTITY] is always kept first.
    _SECTION_ORDER = ("IDENTITY", "VOICE", "VALUES", "BOUNDARIES")
    _FALLBACK_IDENTITY = "You are Xochitl, a terminal-native personal AI system."

    def __init__(self):
        super().__init__(name="soul")
        self._identity_anchor: str = self._FALLBACK_IDENTITY

    def _extract_section(self, section_name: str) -> str:
        """Return the text of a '## [SECTION_NAME]' block, stripped of its header."""
        lines = self._content.split("\n")
        header = f"## [{section_name}]"
        in_section = False
        collected: list[str] = []
        for line in lines:
            if line.strip() == header:
                in_section = True
                continue
            if in_section and line.startswith("## ["):
                break
            if in_section:
                collected.append(line)
        return "\n".join(collected).strip()

    @property
    def identity_anchor(self) -> str:
        """The [IDENTITY] section text — the load-bearing persona anchor."""
        return self._identity_anchor

    def ingest(self) -> None:  # type: ignore[override]
        # Implements FR-ORCH-029, NFR-ORCH-004
        soul_path = _first_existing(_persona_search_paths("SOUL.md", "SOUL.md.example"))
        if soul_path:
            self._content = soul_path.read_text(encoding="utf-8")
        else:
            self._content = (
                f"## [IDENTITY]\n{self._FALLBACK_IDENTITY}\n\n"
                "## [VOICE]\nWarm, precise, lightly witty.\n\n"
                "## [VALUES]\nHonesty, momentum, craft, long-term wellbeing.\n\n"
                "## [BOUNDARIES]\nPreserve values; require approval before mutating actions."
            )
        # Extract and validate [IDENTITY] anchor — NFR-ORCH-004
        extracted = self._extract_section("IDENTITY")
        if extracted:
            self._identity_anchor = extracted
        else:
            print(
                "\033[33m[SOUL] Warning: [IDENTITY] section missing from SOUL.md — "
                "using fallback anchor. Add '## [IDENTITY]' to your SOUL.md.\033[0m"
            )
            self._identity_anchor = self._FALLBACK_IDENTITY
        self._loaded_at = time.time()

    def assemble(self) -> str:
        return self._content

    def compact(self, max_tokens: int) -> str:
        """Always preserve [IDENTITY]; add other sections in priority order.

        Implements NFR-ORCH-005.
        """
        max_chars = max_tokens * _CHARS_PER_TOKEN
        # [IDENTITY] is always first — even if it alone exceeds the budget.
        identity_text = self._identity_anchor
        result_parts = [f"## [IDENTITY]\n{identity_text}"]
        used = len(result_parts[0])

        for section in ("VOICE", "VALUES", "BOUNDARIES"):
            text = self._extract_section(section)
            if not text:
                continue
            block = f"\n\n## [{section}]\n{text}"
            if used + len(block) <= max_chars:
                result_parts.append(block)
                used += len(block)
            else:
                break

        if used > max_chars:
            # Identity alone exceeds budget — truncate gracefully, keep first sentence.
            full = "".join(result_parts)
            return full[:max_chars].rstrip() + "\n[Soul compacted — identity anchor preserved]"

        return "".join(result_parts)


@dataclass
class UserProfileEngine(ContextEngine):
    """Loads Me.md — a portable identity file describing the user.

    Sits just below the Identity Guard so Xochitl knows who she is talking to
    before processing any other context. Never compacted — the file is small
    by design (50-80 lines) and load-bearing for every interaction.
    """

    def __init__(self):
        super().__init__(name="user_profile")

    def ingest(self) -> None:  # type: ignore[override]
        # Implements NFR-ORCH-002 — warn when Me.md exceeds the 80-line target.
        profile_path = _first_existing(_persona_search_paths("Me.md", "Me.md.example"))
        if profile_path:
            self._content = profile_path.read_text(encoding="utf-8")
            line_count = self._content.count("\n") + 1
            if line_count > 80:
                print(
                    f"\033[2m[Me.md] {line_count} lines — target is ≤80. "
                    "Lower sections may compact under token pressure.\033[0m"
                )
        else:
            self._content = ""
        self._loaded_at = time.time()

    def assemble(self) -> str:
        if not self._content:
            return ""
        return f"## About the User\n{self._content}"

    def compact(self, max_tokens: int) -> str:
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        # Keep top sections (identity, domains) — truncate from bottom
        lines = text.split("\n")
        kept, total = [], 0
        for line in lines:
            if total + len(line) > max_chars:
                kept.append("\n[User profile compacted — core identity preserved]")
                break
            kept.append(line)
            total += len(line) + 1
        return "\n".join(kept)


@dataclass
class ConversationConfigEngine(ContextEngine):
    """Loads tunable conversation behavior from conversation.config.yaml.

    Implements FR-ORCH-012 and AC-CR004-013.
    """

    def __init__(self):
        super().__init__(name="conversation_config")

    def ingest(self) -> None:  # type: ignore[override]
        config_path = _first_existing(_persona_search_paths("conversation.config.yaml", "conversation.config.example.yaml"))
        if not config_path:
            self._content = ""
            return
        try:
            from src.skills._yaml_helpers import yaml_load
            data = yaml_load(config_path.read_text(encoding="utf-8"))
            self._content = _format_conversation_config(data)
        except Exception:
            self._content = config_path.read_text(encoding="utf-8")
        self._loaded_at = time.time()

    def assemble(self) -> str:
        if not self._content:
            return ""
        return f"## Conversation Config\n{self._content}"

    def compact(self, max_tokens: int) -> str:
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n[Conversation config compacted]"


def _format_conversation_config(data: dict) -> str:
    """Render selected behavior config as compact prompt text."""
    lines: list[str] = []
    persona = data.get("persona", {})
    if persona:
        lines.append(f"Persona: {persona.get('name', 'Xochitl')} - {persona.get('archetype', '')}")
        cultural = persona.get("cultural_voice")
        if cultural:
            lines.append(f"Cultural voice: {cultural}")

    tone = data.get("tone_by_context", {})
    if tone:
        lines.append("Tone by context:")
        for key, value in tone.items():
            lines.append(f"- {key}: {value}")

    spanish = data.get("spanish_blending", {})
    if spanish:
        examples = ", ".join(spanish.get("allowed_examples", []))
        lines.append(f"Spanish blending: {spanish.get('level', 'A1-A2')} examples: {examples}")
        avoid = spanish.get("avoid", [])
        if avoid:
            lines.append("Spanish blending avoids: " + "; ".join(avoid))

    disagreement = data.get("disagreement_style", {})
    if disagreement:
        lines.append("Disagreement style:")
        for key, value in disagreement.items():
            lines.append(f"- {key}: {value}")

    curiosity = data.get("intellectual_curiosity", {})
    if curiosity:
        max_q = curiosity.get("max_followup_questions_per_turn")
        if max_q is not None:
            lines.append(f"Max follow-up questions per turn: {max_q}")

    context_policy = data.get("context_policy", {})
    if context_policy:
        lines.append("Context policy:")
        for key in ("default_scope", "prefer_small_context", "read_only_actions_auto_allowed", "mutations_require_plan_and_approval"):
            if key in context_policy:
                lines.append(f"- {key}: {context_policy[key]}")

    stability = data.get("character_stability", {})
    if stability:
        lines.append("Character stability:")
        for key, value in stability.items():
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def _load_system_prompt_template() -> str:
    """Load the central system prompt template for FR-ORCH-012."""
    template_path = _first_existing([
        Path.cwd() / ".xochitl" / "prompts" / "system_xochitl.txt",
        Path.home() / ".xochitl" / "prompts" / "system_xochitl.txt",
        _PROJECT_ROOT / "prompts" / "system_xochitl.txt",
    ])
    if template_path:
        return template_path.read_text(encoding="utf-8")
    return "{{IDENTITY_GUARD}}\n\n{{SOUL}}\n\n{{CONVERSATION_CONFIG}}"


def _render_system_prompt_template(
    *,
    identity_guard: str,
    soul: str,
    conversation_config: str,
) -> str:
    template = _load_system_prompt_template()
    return (
        template
        .replace("{{IDENTITY_GUARD}}", identity_guard)
        .replace("{{SOUL}}", soul)
        .replace("{{CONVERSATION_CONFIG}}", conversation_config)
    )


@dataclass
class MemoryEngine(ContextEngine):
    """Loads profile memory and selective semantic memory excerpts."""

    def __init__(self):
        super().__init__(name="memory")

    def ingest(self, query: str = "", project: Optional[str] = None) -> None:  # type: ignore[override]
        # Implements DATA-DATA-005: preload only relevant semantic memories.
        try:
            from src.memory import read_memory, recall
            parts = [read_memory() or ""]
            if query:
                memories = recall(query, n_results=3, project=project)
                if memories:
                    lines = ["## Relevant Semantic Memories"]
                    for memory in memories[:3]:
                        topic = memory.get("topic", "memory")
                        summary = memory.get("summary", "")
                        if summary:
                            lines.append(f"- {topic}: {summary[:500]}")
                    parts.append("\n".join(lines))
            self._content = "\n\n".join(p for p in parts if p)
        except Exception:
            self._content = ""
        self._loaded_at = time.time()

    def assemble(self) -> str:
        if not self._content:
            return ""
        return f"## Memory\n{self._content}"

    def compact(self, max_tokens: int) -> str:
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        # Keep most recent memory entries (end of file)
        truncated = text[-max_chars:]
        first_nl = truncated.find("\n")
        if first_nl > 0:
            truncated = truncated[first_nl + 1:]
        return f"[Memory compacted — showing most recent entries]\n{truncated}"


@dataclass
class PreferenceEngine(ContextEngine):
    """Loads structured user preferences separately from semantic memory."""

    _rows: list = field(default_factory=list, init=False)

    def __init__(self):
        super().__init__(name="preferences")

    def ingest(self, query: str = "", project: Optional[str] = None) -> None:  # type: ignore[override]
        # Implements DATA-DATA-004: recall relevant preferences at turn start.
        try:
            from src import database as db
            with db.get_connection() as conn:
                self._rows = db.search_preferences(conn, query, project_id=project, limit=5)
                db.mark_preferences_used(conn, [int(row["id"]) for row in self._rows])
        except Exception:
            self._rows = []
        self._loaded_at = time.time()

    def assemble(self) -> str:
        """Return preferences as natural background context.

        Implements FR-CONV-004 (A4 — natural memory reference). Frames stored
        preferences as silently-applied background context rather than raw
        ``[scope/category] value`` data. The instruction "do not cite them
        explicitly" prevents the model from producing "I see in your preferences
        that…" patterns (AC-CR028-005).
        """
        if not self._rows:
            return ""
        lines = [
            "[BACKGROUND CONTEXT]",
            "Apply these user preferences silently — do not cite them explicitly:",
        ]
        for row in self._rows:
            category = str(row["category"]).capitalize()
            lines.append(f"- {category}: {row['preference_value']}")
        lines.append("[/BACKGROUND CONTEXT]")
        return "\n".join(lines)

    def compact(self, max_tokens: int) -> str:
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n[Preferences compacted]"


@dataclass
class FileContextEngine(ContextEngine):
    """Resolves and injects file/directory context from router._resolve_file_context."""

    _query: str = field(default="", init=False)
    _history: list = field(default_factory=list, init=False)

    def __init__(self):
        super().__init__(name="file_context")

    def ingest(self, query: str = "", history: Optional[list] = None) -> None:  # type: ignore[override]
        self._query = query
        self._history = history or []
        try:
            from src.router import _resolve_file_context
            self._content = _resolve_file_context(query, history)
        except Exception:
            self._content = ""
        self._loaded_at = time.time()

    def assemble(self) -> str:
        return self._content

    def compact(self, max_tokens: int) -> str:
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        # Keep directory listings intact, truncate file contents
        lines = text.split("\n")
        kept = []
        total = 0
        in_code_block = False
        for line in lines:
            if line.startswith("```"):
                in_code_block = not in_code_block
            # Always keep headers and directory lines
            is_header = line.startswith("#") or line.startswith("  ")
            if total + len(line) > max_chars:
                if in_code_block:
                    kept.append("... [file content truncated for token budget]")
                    kept.append("```")
                break
            kept.append(line)
            total += len(line) + 1
        return "\n".join(kept)


# ── Skill Manifest Engine ────────────────────────────────────────────────────

@dataclass
class SkillManifestEngine(ContextEngine):
    """Formats skill tool_definitions into a system prompt section.

    Implements FR-ORCH-005 — injects a structured "## Skills You Can Invoke"
    block so the LLM knows which skills are available and how to call them
    via <skill_call name="X">{}</skill_call> markers (FR-ORCH-008).
    """

    _skill_defs: list = field(default_factory=list, init=False)

    def __init__(self):
        super().__init__(name="skill_manifest")

    def ingest(self, skills: list | None = None) -> None:  # type: ignore[override]
        self._skill_defs = [s.tool_definition() for s in (skills or [])]
        self._loaded_at = time.time()

    def assemble(self) -> str:
        if not self._skill_defs:
            return ""

        lines = [
            "## Skills You Can Invoke",
            "",
            "To invoke a skill, output this EXACT format anywhere in your response:",
            "",
            '  <skill_call name="SKILL_NAME">{"param": "value"}</skill_call>',
            "",
            "Read-only skills may execute immediately; mutating skills are staged for user approval first.",
            "Only invoke a skill when the user clearly wants that action — not for planning or discussion.",
            "",
        ]
        for d in self._skill_defs:
            lines.append(f"**{d['name']}**")
            lines.append(f"  Does: {d['description']}")
            lines.append(f"  Use when: {d['when']}")
            params = d.get("params", {})
            if params:
                param_str = ", ".join(f"`{k}`: {v}" for k, v in params.items())
                lines.append(f"  Params: {param_str}")
            lines.append("")

        return "\n".join(lines)

    def compact(self, max_tokens: int) -> str:
        text = self.assemble()
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= max_chars:
            return text
        # Keep invocation format + skill names only — drop param details
        lines = [
            "## Skills (names only — compacted)",
            '  <skill_call name="SKILL_NAME">{"param": "value"}</skill_call>',
            "  Available: " + ", ".join(d["name"] for d in self._skill_defs),
        ]
        return "\n".join(lines)


# ── Provenance Tagging ───────────────────────────────────────────────────────

def tag_message_provenance(role: str, content: str, source: str = "") -> str:
    """Wrap a message with source provenance to prevent role confusion.

    Implements FR-ORCH-004 — Provenance Tagging.
    Helps the LLM distinguish user commands from internal system logs.

    Args:
        role: 'user' | 'assistant' | 'system'
        content: Raw message content
        source: Optional extra source label (e.g., 'tool_result', 'skill_output')
    """
    if role == "user":
        label = "[SOURCE: USER]"
    elif role == "assistant":
        label = "[SOURCE: XOCHITL]"
    elif source:
        label = f"[SOURCE: SYSTEM/{source.upper()}]"
    else:
        label = "[SOURCE: SYSTEM]"
    return f"{label}\n{content}"


def apply_provenance_to_history(history: list[dict]) -> list[dict]:
    """Return a copy of history with provenance labels applied to each message.

    Implements FR-ORCH-004.
    Used when building the final message list sent to the LLM.
    """
    tagged = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        source = msg.get("source", "")  # custom field for system messages
        tagged.append({
            **msg,
            "content": tag_message_provenance(role, content, source),
        })
    return tagged


# ── ContextManager orchestrator ──────────────────────────────────────────────

class ContextManager:
    """Orchestrates all context engines with token budget enforcement.

    Implements NFR-PERF-004 — triggers compaction at 75% of model token limit.

    Usage::

        cm = ContextManager(route="local")
        cm.ingest(query=user_query, history=conversation_history, project="ZettleLib")
        system_prompt = cm.assemble_system_prompt()
        messages = cm.assemble_messages(conversation_history, user_query)
    """

    def __init__(
        self,
        route: str = "local",
        skills: list | None = None,
        milestone_block: str = "",
    ):
        self._route = route
        self._token_limit = _LOCAL_TOKEN_LIMIT if route == "local" else _CLOUD_TOKEN_LIMIT
        self._budget = int(self._token_limit * _BUDGET_RATIO)
        self._skills_list = skills or []
        # CR-035: milestone context block for progressive personalization (FR-PREF-005)
        self._milestone_block: str = milestone_block

        # Initialize engines
        self.facts        = FactsEngine()
        self.soul         = SoulEngine()
        self.user_profile = UserProfileEngine()
        self.behavior     = ConversationConfigEngine()
        self.preferences = PreferenceEngine()
        self.memory  = MemoryEngine()
        self.files   = FileContextEngine()
        self.skills  = SkillManifestEngine()  # FR-ORCH-005

        self._ingested = False

    def ingest(
        self,
        query: str = "",
        history: Optional[list] = None,
        project: Optional[str] = None,
        local_mode: bool = True,
    ) -> None:
        """Load all engine data. Call once per request."""
        self.facts.ingest(project=project, local_mode=local_mode)
        self.soul.ingest()
        self.user_profile.ingest()
        self.behavior.ingest()
        self.preferences.ingest(query=query, project=project)
        self.memory.ingest(query=query, project=project)
        self.files.ingest(query=query, history=history)
        self.skills.ingest(skills=self._skills_list)  # FR-ORCH-005
        self._ingested = True

    def _total_tokens(self, *texts: str) -> int:
        return sum(_estimate_tokens(t) for t in texts if t)

    def assemble_system_prompt(self, mode: str = "conversational") -> str:
        """Build the full system prompt with token budget enforcement.

        Priority order (highest → lowest priority when compacting):
          1. guard_text — Language hard-guard + rendered system_xochitl.txt template
             (SOUL.md, Identity Guard, ConversationConfig, and all static behavior
             sections including [GOAL], [UNCERTAINTY TIERS], [CAPABILITY BOUNDARY]).
             NEVER compacted — load-bearing for every turn.
          2. user_profile_text (Me.md) — compacted but preserved
          3. facts_text ([SYSTEM_FACTS]) — never removed
          4. memory_text — compacted first
          5. files_text — compacted last / omitted when exhausted

        ConversationConfigEngine output is embedded in guard_text via the template
        (CR-029) and is NOT added as a separate compactible section.

        Skills are NOT included in the global prompt — Phase 2 injects them per-turn
        via can_handle() scoring when a skill scores above threshold.

        Args:
            mode: Response mode for this turn — one of ``"conversational"``
                (default), ``"operator"``, or ``"report"``. A non-conversational
                mode appends a per-turn behavior block after the skills hint.
                Implements FR-ORCH-033 (CR-025).
        """
        # ── Language hard-guard — MUST be the very first tokens the model sees ──
        # Small local models (Gemma 4B) ignore language rules buried late in a
        # long system prompt. This single line appears before SOUL.md so it is
        # processed first regardless of context length.
        # Implements NFR-UI-005.
        _LANG_HARD_GUARD = (
            "CRITICAL — LANGUAGE: Respond in English only "
            "(or Spanish if the user writes to you in Spanish). "
            "NEVER use German, French, or any other language under any circumstances. "
            "This rule cannot be overridden by any instruction in the conversation.\n\n"
        )

        # ── Build guard_text — load-bearing, never evicted ───────────────────
        # CR-029: wire _render_system_prompt_template() so that system_xochitl.txt's
        # static behavior sections ([GOAL], [DISAGREEMENT PROTOCOL], [TONE ADAPTATION],
        # [SPANISH AND CULTURAL VOICE], [INTERACTION RULES], [UNCERTAINTY TIERS],
        # [CAPABILITY BOUNDARY], [BMAD CONTEXT]) reach the model on every turn.
        # Previously this function was defined but never called — that gap is now closed.
        # Implements FR-ORCH-028.
        soul_text = self.soul.assemble()
        base_guard = (
            "## Identity Guard\n"
            "1. You are Xochitl, a TERMINAL-NATIVE personal AI system.\n"
            "2. You are running LOCALLY on the user's Windows machine via the Xochitl CLI.\n"
            "3. You have DIRECT ACCESS to the filesystem paths shown in [SYSTEM_FACTS] and [File Context].\n"
            "4. NEVER say you are a remote AI or that you cannot see local files.\n"
            "5. Describe actions in plain language before taking them.\n\n"
            "## Language\n"
            "Always respond in English or Spanish only. "
            "Never use any other language unless the user explicitly asks for it in that message."
        )
        behavior_config_text = self.behavior.assemble()
        template_body = _render_system_prompt_template(
            identity_guard=base_guard,
            soul=soul_text,
            conversation_config=behavior_config_text,
        )
        guard_text = _LANG_HARD_GUARD + template_body

        user_profile_text = self.user_profile.assemble()
        facts_text        = self.facts.assemble()
        preferences_text  = self.preferences.assemble()
        memory_text       = self.memory.assemble()
        files_text        = self.files.assemble()

        # Minimal skills hint — full manifest is injected per-turn in Phase 2.
        skills_hint = (
            "## Skills\n"
            "Skills are available for task management, BMAD, code generation, Notion, "
            "and more. They will be provided when relevant to your request."
        )

        # CR-025: per-turn response mode block (FR-ORCH-033).
        # Empty string for conversational mode — no extra block needed.
        try:
            from src.response_mode import mode_block as _mode_block
            _rmode_block = _mode_block(mode)
        except ImportError:
            _rmode_block = ""

        # behavior_config_text is now part of guard_text — exclude from budget total.
        total = self._total_tokens(
            guard_text, user_profile_text, facts_text,
            preferences_text, memory_text, files_text,
        )
        budget_remaining = self._budget

        # ── Under budget: assemble without compaction ─────────────────────────
        if total <= budget_remaining:
            parts = [guard_text]
            if user_profile_text:
                parts.append(user_profile_text)
            parts.append(facts_text)
            parts.append(skills_hint)
            if preferences_text:
                parts.append(preferences_text)
            if memory_text:
                parts.append(memory_text)
            if files_text:
                parts.append(files_text)
            # CR-035: milestone personalization block (FR-PREF-005).
            # Appended last — near-recency bias strengthens its effect on local models.
            # Empty string for M1 (new users) — no block injected.
            if self._milestone_block:
                parts.append(self._milestone_block)
            if _rmode_block:
                parts.append(_rmode_block)
            return "\n\n---\n\n".join(parts)

        # ── Over budget: compact in reverse priority order ────────────────────
        # guard_text is NEVER compacted — it is load-bearing.
        # user_profile_text is small by design — give it a fixed budget and preserve it.
        profile_budget     = min(_estimate_tokens(user_profile_text), 600)
        facts_budget       = min(_estimate_tokens(facts_text), 200)
        preferences_budget = min(_estimate_tokens(preferences_text), 400)
        memory_budget      = min(_estimate_tokens(memory_text), 600)
        files_budget       = (
            budget_remaining
            - _estimate_tokens(guard_text)
            - profile_budget
            - facts_budget
            - preferences_budget
            - memory_budget
            - _estimate_tokens(skills_hint)
        )

        parts = [guard_text]
        if user_profile_text:
            parts.append(self.user_profile.compact(profile_budget))
        parts.append(self.facts.compact(facts_budget))
        parts.append(skills_hint)
        if preferences_text:
            parts.append(self.preferences.compact(preferences_budget))
        if memory_text:
            parts.append(self.memory.compact(max(memory_budget, 100)))
        if files_text and files_budget > 100:
            parts.append(self.files.compact(files_budget))
        else:
            parts.append("[File context omitted — token budget exhausted]")
        # CR-035: milestone block is small (~30 tokens) — always include even over budget.
        if self._milestone_block:
            parts.append(self._milestone_block)
        if _rmode_block:
            parts.append(_rmode_block)

        return "\n\n---\n\n".join(parts)

    def assemble_messages(
        self,
        history: list[dict],
        user_query: str,
        tag_provenance: bool = True,
    ) -> list[dict]:
        """Build the final message list for the LLM with optional provenance tagging.

        Implements FR-ORCH-004.
        Keeps the last N turns verbatim, summarizes older history in a system message.
        """
        # Keep last 8 turns verbatim; summarize older turns
        verbatim_turns = 8
        old_history = history[:-verbatim_turns] if len(history) > verbatim_turns else []
        recent_history = history[-verbatim_turns:] if history else []

        messages: list[dict] = []

        # Inject older history as a single summary system message
        if old_history:
            summary_lines = []
            for msg in old_history[-10:]:
                role = msg.get("role", "")
                content = str(msg.get("content", ""))[:120]
                summary_lines.append(f"  [{role}] {content}")
            summary = "## Earlier conversation (summarized)\n" + "\n".join(summary_lines)
            messages.append({"role": "user", "content": f"[SOURCE: SYSTEM/HISTORY]\n{summary}"})
            messages.append({"role": "assistant", "content": "[SOURCE: XOCHITL]\nUnderstood — continuing from context above."})

        # Add recent history with provenance tags
        for msg in recent_history:
            role = msg.get("role", "user")
            content = str(msg.get("content", ""))
            source = msg.get("source", "")
            if tag_provenance:
                content = tag_message_provenance(role, content, source)
            messages.append({"role": role, "content": content})

        # Add the current user query
        current_content = tag_message_provenance("user", user_query) if tag_provenance else user_query
        messages.append({"role": "user", "content": current_content})

        return messages

    @property
    def budget_used_pct(self) -> float:
        """Return the fraction of token budget consumed by current assembly."""
        if not self._ingested:
            return 0.0
        total = self._total_tokens(
            self.soul.assemble(),   # soul is now part of the guard block
            self.user_profile.assemble(),
            self.facts.assemble(),
            self.behavior.assemble(),
            self.preferences.assemble(),
            self.memory.assemble(),
            self.files.assemble(),
        )
        return total / self._token_limit
