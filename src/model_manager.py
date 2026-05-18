"""VRAM-aware tiered model selection for Xochitl's router.

Queries nvidia-smi at call time and maps free VRAM to a quality tier so the
best available model is always used without exceeding GPU budget.

Tiers (based on free VRAM at call time):
  high   >= 9 000 MB  →  14B models   (phi4:14b, qwen2.5-coder:14b)
  medium >= 5 500 MB  →   8B models   (llama3.1:8b, qwen2.5-coder:7b)
  low     < 5 500 MB  →   4B fallback (phi3.5:3.8b for everything)
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── VRAM thresholds (MB) ──────────────────────────────────────────────────────
_HIGH_MB   = 9_000   # >=  9 GB → 14B safe (7.5 GB weights + 1.5 GB KV cache headroom)
_MEDIUM_MB = 5_500   # >= 5.5 GB →  8B safe

# ── Model tiers ───────────────────────────────────────────────────────────────
# Each tier maps role → ollama model tag.
# Roles: 'thinking', 'coding', 'general', 'router'
_TIERS: dict[str, dict[str, str]] = {
    "high": {
        "thinking": "phi4:14b-q4_K_M",
        "coding":   "qwen2.5-coder:14b-instruct-q4_K_M",
        "general":  "phi3.5:3.8b-mini-instruct-q8_0",
        "router":   "gemma2:2b",
    },
    "medium": {
        "thinking": "llama3.1:8b-instruct-q5_K_M",
        "coding":   "qwen2.5-coder:7b-instruct-q5_K_M",
        "general":  "phi3.5:3.8b-mini-instruct-q8_0",
        "router":   "gemma2:2b",
    },
    "low": {
        "thinking": "phi3.5:3.8b-mini-instruct-q8_0",
        "coding":   "phi3.5:3.8b-mini-instruct-q8_0",
        "general":  "phi3.5:3.8b-mini-instruct-q8_0",
        "router":   "gemma2:2b",
    },
}

_LOG_PATH = Path(__file__).parent.parent / "logs" / "model_manager.log"


def get_free_vram_mb() -> int | None:
    """Query nvidia-smi for free VRAM on the first GPU. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if lines:
            return int(lines[0].strip())
    except Exception:
        pass
    return None


def get_tier() -> str:
    """Return 'high', 'medium', or 'low' based on current free VRAM.

    Defaults to 'high' when nvidia-smi is unavailable so the best model is
    attempted — Ollama will error visibly if it truly can't load.
    """
    free = get_free_vram_mb()
    if free is None:
        return "high"
    if free >= _HIGH_MB:
        return "high"
    if free >= _MEDIUM_MB:
        return "medium"
    return "low"


def select_model(role: str) -> str:
    """Return the appropriate Ollama model tag for a given role and current VRAM tier.

    Args:
        role: 'thinking' | 'coding' | 'general' | 'router'

    Returns the model tag string (e.g. 'phi4:14b-q4_K_M').
    Falls back to 'general' tier model if role is unrecognised.
    """
    tier = get_tier()
    tier_map = _TIERS[tier]
    model = tier_map.get(role, tier_map["general"])
    _log(tier, role, model)
    return model


def _log(tier: str, role: str, model: str) -> None:
    """Append one line to logs/model_manager.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] tier={tier} role={role} → {model}"
    try:
        _LOG_PATH.parent.mkdir(exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
