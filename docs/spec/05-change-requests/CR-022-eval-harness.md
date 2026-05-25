# CR-022 — Eval Harness

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #14 (Group 5)
**Implements**: FR-EVAL-001, FR-EVAL-002, FR-EVAL-003, NFR-EVAL-001

---

## Problem

`smoke_test.py` is unit coverage — it verifies that code exists and conforms to
contracts, but it does not measure answer quality, skill selection accuracy, or
routing correctness. There is no way to detect regressions when:

- Swapping local models (e.g. gemma4-e4b → gemma3-12b)
- Adding or refactoring `can_handle()` heuristics
- Changing routing thresholds

Without a quality measurement harness, the team has no signal that routing
improved or degraded.

---

## Solution

### New: `src/eval/` package

| File | Role |
|---|---|
| `src/eval/__init__.py` | Package marker |
| `src/eval/golden_set.py` | ≥30 labeled `GoldenExample` instances covering all built-in skills |
| `src/eval/harness.py` | `run_eval()` → `EvalReport`; baseline comparison; regression detection |

### New: `eval_harness.py` (project root)

CLI runner. Prints Rich-formatted report; exits with code 1 on regression.

```bash
python eval_harness.py              # run and compare against stored baseline
python eval_harness.py --save-baseline  # run and overwrite baseline.json
```

### Design

**Golden set format** — each example is a `GoldenExample`:
```python
@dataclass
class GoldenExample:
    utterance: str
    expected_skill: Optional[str]  # "WeatherSkill" | None
    expected_match: bool           # True = should route (score ≥ 0.65)
    adversarial: bool = False      # edge case / discrimination test
    notes: str = ""
```

**Routing correctness** — an example is "correct" when:
- `expected_match=True` AND top skill == `expected_skill` AND score ≥ 0.65
- `expected_match=False` AND (top skill != `expected_skill` OR score < 0.65)

**Metrics** — per skill and overall:
- Per-skill TP / FP / FN → precision, recall, F1
- Overall accuracy = correct / total

**Baseline** — stored at `src/eval/baseline.json`. Regression = accuracy drops
> 5 percentage points from baseline. Run with `--save-baseline` to commit a
new baseline after intentional improvements.

**No LLM calls** — harness calls only `can_handle()` (pure heuristic,
< 5 ms per skill). Full golden set completes in < 2 s.

---

## Requirements

- **FR-EVAL-001** — `src/eval/golden_set.py` defines a `GOLDEN_SET` of ≥30
  `GoldenExample` instances covering WeatherSkill, WebLookupSkill,
  ZettelkastenSkill, BMADSkill, SDDSkill, CodeSkill, NotionSkill,
  OrchestratorSkill, and ≥5 no-skill cases; ≥6 adversarial examples.
- **FR-EVAL-002** — `run_eval()` returns an `EvalReport` containing per-skill
  precision, recall, and F1; overall accuracy; and a list of failing utterances
  (expected_match=True but not matched).
- **FR-EVAL-003** — `run_eval()` loads `src/eval/baseline.json` (if present)
  and sets `EvalReport.regression=True` when accuracy drops > 5 percentage
  points from the stored baseline. `--save-baseline` flag overwrites the
  baseline with the current run.
- **NFR-EVAL-001** — Harness runs without any LLM calls (`can_handle()` only);
  full golden set completes in < 30 s.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR022-001` | `src.eval.harness` importable; `run_eval()` callable and returns `EvalReport` |
| `AC-CR022-002` | `GOLDEN_SET` contains ≥30 examples covering all 8 built-in skills and ≥5 no-skill cases |
| `AC-CR022-003` | `EvalReport` has `accuracy`, `per_skill`, `regression`, and `gaps` fields |
| `AC-CR022-004` | `run_eval()` completes without any LLM/router calls (pure `can_handle()` heuristic) |
| `AC-CR022-005` | Regression detection: `regression=True` when accuracy < baseline − 0.05 |

---

## Implementation tasks

- [x] Write `CR-022-eval-harness.md`
- [x] Create `src/eval/__init__.py`
- [x] Create `src/eval/golden_set.py`
- [x] Create `src/eval/harness.py`
- [x] Create `eval_harness.py` (project root runner)
- [x] Write `docs/spec/08-test-specs/TEST-EVAL-001-eval-harness.md`
- [x] Update requirements registry
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Known gaps documented by initial run

The golden set deliberately includes desired-behavior examples for skills whose
`can_handle()` heuristics currently score below the 0.65 threshold. These are
documented as gaps in the initial baseline, giving concrete targets for
heuristic improvements:

| Skill | Utterance | Current score |
|---|---|---|
| WeatherSkill | "will it rain in Seattle this weekend?" | 0.00 |
| WebLookupSkill | "look up the current price of Bitcoin" | 0.00 |
| ZettelkastenSkill | "store this insight in my notes: …" | 0.00 |
| SDDSkill | "add requirement FR-AUTH-001: …" | 0.40 |
| SDDSkill | "list all requirements for the auth module" | 0.40 |
| SDDSkill | "generate the spec for the auth feature" | TBD |
| CodeSkill | "scaffold the REST API for my project" | 0.20 |
| CodeSkill | "generate code for user authentication" | 0.20 |
| CodeSkill | "implement the database schema from the spec" | TBD |
