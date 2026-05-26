"""VRAM-aware model selection for Xochitl's router.

Implements CR-043 — GPU-aware model selection.

Hardware profile is determined ONCE at module import using *total* VRAM.
Total VRAM is a stable hardware property; free VRAM fluctuates as Ollama
loads and unloads models between calls, making it a bad selector.
Ollama manages its own memory — we just tell it which model to use.

Hardware profiles (total VRAM):
  WORKSTATION  >= 20 GB  ->  qwen3:32b-q4_K_M (thinking/coding), qwen2.5:7b (general)
  DESKTOP      >= 12 GB  ->  qwen3:14b         (thinking/coding), qwen2.5:7b (general)
  LAPTOP        6-12 GB  ->  qwen3.5:9b        (all roles)
  MINIMAL       < 6 GB   ->  phi4-mini          (all roles, heavy cloud reliance)
"""
# Implements FR-GPU-001 (hardware profile detection via total VRAM)
# Implements FR-GPU-002 (profile-aware model selection per role)
# Implements FR-GPU-003 (startup report surfaced in chat banner)

import subprocess
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_LOG_PATH = Path(__file__).parent.parent / "logs" / "model_manager.log"


class HardwareProfile(str, Enum):
    """Stable hardware tier based on total GPU VRAM detected at startup."""
    WORKSTATION = "workstation"   # 20 GB+  — future-proof tier
    DESKTOP     = "desktop"       # 12-20 GB — current 16 GB desktop
    LAPTOP      = "laptop"        #  6-12 GB — current 8 GB laptop
    MINIMAL     = "minimal"       #  < 6 GB  — no GPU or very low VRAM


# ── VRAM thresholds (MB, based on *total* VRAM) ───────────────────────────────
_WORKSTATION_MB: int = 20_000   # >= 20 GB
_DESKTOP_MB:     int = 12_000   # >= 12 GB
_LAPTOP_MB:      int =  6_000   #  >= 6 GB


# ── Profile -> role -> Ollama model tag ───────────────────────────────────────
# Roles used by router.py: 'thinking', 'coding', 'general', 'router'
_PROFILES: dict[str, dict[str, str]] = {
    HardwareProfile.WORKSTATION: {
        "thinking": "qwen3:32b-q4_K_M",
        "coding":   "qwen3:32b-q4_K_M",
        "general":  "qwen2.5:7b",
        "router":   "qwen2.5:7b",
    },
    HardwareProfile.DESKTOP: {
        "thinking": "qwen3:14b",
        "coding":   "qwen3:14b",
        "general":  "qwen2.5:7b",
        "router":   "qwen2.5:7b",
    },
    HardwareProfile.LAPTOP: {
        "thinking": "qwen3.5:9b",
        "coding":   "qwen3.5:9b",
        "general":  "qwen3.5:9b",
        "router":   "qwen3.5:9b",
    },
    HardwareProfile.MINIMAL: {
        "thinking": "phi4-mini",
        "coding":   "phi4-mini",
        "general":  "phi4-mini",
        "router":   "phi4-mini",
    },
}


# ── GPU info (queried once at module import) ──────────────────────────────────

def get_vram_info() -> dict[str, Optional[int]]:
    """Query nvidia-smi for total and free VRAM on the first GPU.

    Returns:
        Dict with 'total_mb' and 'free_mb'; either may be None if
        nvidia-smi is unavailable or returns unexpected output.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if lines and lines[0]:
            parts = lines[0].split(",")
            return {
                "total_mb": int(parts[0].strip()),
                "free_mb":  int(parts[1].strip()),
            }
    except Exception as exc:
        logger.debug("model_manager: nvidia-smi unavailable: %s", exc)
    return {"total_mb": None, "free_mb": None}


def get_free_vram_mb() -> Optional[int]:
    """Return current free VRAM in MB, or None if unavailable.

    Kept for backward compatibility and observability. Not used for
    per-call model selection (use get_hardware_profile() instead).
    """
    info = get_vram_info()
    return info["free_mb"]


def _classify_profile(total_mb: Optional[int]) -> HardwareProfile:
    """Map total VRAM (MB) to a HardwareProfile enum value.

    Args:
        total_mb: Total GPU VRAM in megabytes, or None if not detected.

    Returns:
        HardwareProfile appropriate for the detected hardware.
    """
    if total_mb is None:
        return HardwareProfile.MINIMAL
    if total_mb >= _WORKSTATION_MB:
        return HardwareProfile.WORKSTATION
    if total_mb >= _DESKTOP_MB:
        return HardwareProfile.DESKTOP
    if total_mb >= _LAPTOP_MB:
        return HardwareProfile.LAPTOP
    return HardwareProfile.MINIMAL


# ── Module-level profile: detected once, reused for every select_model() call ─
_vram_info: dict[str, Optional[int]] = get_vram_info()
_HARDWARE_PROFILE: HardwareProfile = _classify_profile(_vram_info["total_mb"])


def get_hardware_profile() -> HardwareProfile:
    """Return the stable hardware profile detected at startup.

    Returns:
        HardwareProfile (WORKSTATION, DESKTOP, LAPTOP, or MINIMAL).
    """
    return _HARDWARE_PROFILE


def get_tier() -> str:
    """Return legacy tier string for backward compatibility.

    Maps HardwareProfile to the 'high' / 'medium' / 'low' strings used
    by older callers. Prefer get_hardware_profile() in new code.

    Returns:
        'high' for WORKSTATION/DESKTOP, 'medium' for LAPTOP, 'low' for MINIMAL.
    """
    if _HARDWARE_PROFILE in (HardwareProfile.WORKSTATION, HardwareProfile.DESKTOP):
        return "high"
    if _HARDWARE_PROFILE == HardwareProfile.LAPTOP:
        return "medium"
    return "low"


def select_model(role: str) -> str:
    """Return the Ollama model tag for a given role on the detected hardware.

    Args:
        role: One of 'thinking', 'coding', 'general', 'router'.
              Unknown roles fall back to 'general'.

    Returns:
        Ollama model tag string (e.g. 'qwen3:14b').
    """
    profile_map = _PROFILES[_HARDWARE_PROFILE]
    model = profile_map.get(role, profile_map["general"])
    _log(_HARDWARE_PROFILE.value, role, model)
    return model


def get_startup_report() -> str:
    """Return a human-readable GPU and model status for the startup banner.

    Surfaced by cli.py chat command so the user always knows which
    models Xochitl selected and how much GPU headroom remains.

    Returns:
        Multi-line plain string (no Rich markup — caller adds styling).

    Example output:
        GPU  16.0 GB total | 13.2 GB free  ->  DESKTOP
        thinking / coding  :  qwen3:14b
        general / router   :  qwen2.5:7b
    """
    total_mb = _vram_info["total_mb"]
    free_mb  = _vram_info["free_mb"]
    profile  = _HARDWARE_PROFILE
    models   = _PROFILES[profile]

    if total_mb is None:
        gpu_line = f"GPU  not detected (no nvidia-smi)  ->  {profile.value.upper()}"
    else:
        total_gb = total_mb / 1024
        free_gb  = free_mb  / 1024 if free_mb is not None else 0.0
        gpu_line = (
            f"GPU  {total_gb:.1f} GB total | {free_gb:.1f} GB free"
            f"  ->  {profile.value.upper()}"
        )

    capable = models["thinking"]
    fast    = models["general"]

    if capable == fast:
        model_lines = f"  all roles  :  {capable}"
    else:
        model_lines = (
            f"  thinking / coding  :  {capable}\n"
            f"  general / router   :  {fast}"
        )

    return f"{gpu_line}\n{model_lines}"


def _log(profile: str, role: str, model: str) -> None:
    """Append one selection event to logs/model_manager.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] profile={profile} role={role} -> {model}"
    try:
        _LOG_PATH.parent.mkdir(exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
