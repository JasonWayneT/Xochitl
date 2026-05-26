# CR-043 — GPU-Aware Model Selection

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 18 (Group 7 — Hardware Adaptability)
**Source**: User request — optimize Xochitl for local models, auto-select based on available GPU

---

## Problem statement

Xochitl's `model_manager.py` used stale model names (phi4:14b, llama3.1:8b,
phi3.5:3.8b) that no longer matched what was installed, and it selected models
based on *free* VRAM — which fluctuates as Ollama loads and unloads models
between calls, making selection unstable and unpredictable.

More fundamentally, there was no concept of a stable hardware profile: a 16 GB
desktop and an 8 GB laptop would pick different models on the same call depending
on what happened to be loaded at that moment.

The user also has two machines with different VRAM budgets:
- Desktop: 16 GB GPU (room for 14B models with headroom)
- Laptop:   8 GB GPU (fits 9B models, needs emergency fallback)

Xochitl should detect the machine she is running on and choose the best
available model automatically — and tell the user what she picked.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-GPU-001` | At module import, query `nvidia-smi` for total VRAM; classify into `HardwareProfile` (WORKSTATION >= 20 GB / DESKTOP >= 12 GB / LAPTOP >= 6 GB / MINIMAL < 6 GB); cache result for the process lifetime |
| `FR-GPU-002` | `select_model(role)` returns the Ollama model tag appropriate for the detected `HardwareProfile` and requested role (`thinking`, `coding`, `general`, `router`); unknown roles fall back to `general` |
| `FR-GPU-003` | `get_startup_report()` returns a plain-text summary of detected GPU and selected models; `cli.py chat` prints it in dim styling before the conversational loop starts |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-GPU-001` | GPU detection must never raise to the caller; all `nvidia-smi` failures are caught and logged at DEBUG; MINIMAL profile is the safe default when no GPU is detected |

---

## Model assignments by profile

| Profile | Total VRAM | thinking / coding | general / router |
|---|---|---|---|
| WORKSTATION | >= 20 GB | qwen3:32b-q4_K_M | qwen2.5:7b |
| DESKTOP | >= 12 GB | qwen3:14b | qwen2.5:7b |
| LAPTOP | 6–12 GB | qwen3.5:9b | qwen3.5:9b |
| MINIMAL | < 6 GB | phi4-mini | phi4-mini |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR043-001` | `_classify_profile(16_384)` | `HardwareProfile.DESKTOP` |
| `AC-CR043-002` | `_classify_profile(8_192)` | `HardwareProfile.LAPTOP` |
| `AC-CR043-003` | `_classify_profile(None)` | `HardwareProfile.MINIMAL` |
| `AC-CR043-004` | `select_model('thinking')` with DESKTOP profile | `'qwen3:14b'` |
| `AC-CR043-005` | `get_startup_report()` contains profile name and model name | report string includes `DESKTOP` and `qwen3:14b` |
| `AC-CR043-006` | `python smoke_test.py` | 151 passed, 0 failed |

---

## Implementation tasks

- [x] `src/model_manager.py` — `HardwareProfile` enum, `_PROFILES` dict with new model names, `get_vram_info()`, `_classify_profile()`, `get_hardware_profile()`, `get_startup_report()`, updated `select_model()`, kept `get_free_vram_mb()` and `get_tier()` for backward compat
- [x] `src/cli.py` — print `get_startup_report()` in chat startup banner (FR-GPU-003)
- [x] `smoke_test.py` — 5 tests (AC-CR043-001 through AC-CR043-005)
- [x] `docs/spec/02-requirements-registry.md` — FR-GPU-001, FR-GPU-002, FR-GPU-003, NFR-GPU-001
- [x] `docs/spec/06-traceability/traceability-matrix.md`
