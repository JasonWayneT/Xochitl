"""Eval harness for Xochitl skill routing quality measurement.

Implements FR-EVAL-001, FR-EVAL-002, FR-EVAL-003, NFR-EVAL-001 (CR-022).

``run_eval()`` scores every example in the golden set against the built-in
skills using only ``can_handle()`` (pure heuristic, no LLM calls), computes
per-skill precision/recall/F1, and detects regressions against the stored
baseline.

Usage::

    from src.eval.harness import run_eval
    report = run_eval()
    if report.regression:
        sys.exit(1)

CLI::

    python eval_harness.py              # compare against baseline
    python eval_harness.py --save-baseline  # overwrite baseline with current run
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.eval.golden_set import GOLDEN_SET, GoldenExample

# ── Routing threshold — mirrors src/chat.py ───────────────────────────────────
_SKILL_INJECT_THRESHOLD: float = 0.65

# Regression gate: accuracy must not drop more than this from baseline
_REGRESSION_THRESHOLD: float = 0.05

# Baseline file location
_BASELINE_PATH: Path = Path(__file__).parent / "baseline.json"


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class SkillMetrics:
    """Per-skill precision, recall, and F1 computed from the golden set.

    Attributes:
        skill_name: Class name of the skill (e.g. ``"WeatherSkill"``).
        tp:         True positives (correctly routed to this skill).
        fp:         False positives (routed here but should not have been).
        fn:         False negatives (should have routed here but did not).
        precision:  TP / (TP + FP), or 0.0 when TP + FP == 0.
        recall:     TP / (TP + FN), or 0.0 when TP + FN == 0.
        f1:         Harmonic mean of precision and recall.
    """

    skill_name: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class EvalReport:
    """Full evaluation report from a single harness run.

    Attributes:
        total:             Number of golden examples evaluated.
        correct:           Number correctly predicted.
        accuracy:          ``correct / total``.
        per_skill:         Per-skill ``SkillMetrics`` keyed by class name.
        regression:        ``True`` when accuracy drops > 5pp from baseline.
        baseline_accuracy: Stored baseline accuracy (``None`` if no baseline).
        run_timestamp:     ISO-8601 UTC timestamp of the run.
        gaps:              Utterances that failed (expected_match=True, not matched).
    """

    total: int
    correct: int
    accuracy: float
    per_skill: dict[str, SkillMetrics]
    regression: bool
    baseline_accuracy: Optional[float]
    run_timestamp: str
    gaps: list[str] = field(default_factory=list)


# ── Skill loader ──────────────────────────────────────────────────────────────


def _load_builtin_skills() -> list:
    """Instantiate the eight built-in skills without importing XochitlChat.

    Returns:
        List of skill instances with callable ``can_handle()`` methods.
    """
    from src.skills.bmad_skill import BMADSkill
    from src.skills.sdd_skill import SDDSkill
    from src.skills.code_skill import CodeSkill
    from src.skills.notion_skill import NotionSkill
    from src.skills.orchestrator_skill import OrchestratorSkill
    from src.skills.weather_skill import WeatherSkill
    from src.skills.web_lookup_skill import WebLookupSkill
    from src.skills.zettelkasten_skill import ZettelkastenSkill

    return [
        BMADSkill(),
        SDDSkill(),
        CodeSkill(),
        NotionSkill(),
        OrchestratorSkill(),
        WeatherSkill(),
        WebLookupSkill(),
        ZettelkastenSkill(),
    ]


# ── Scoring ───────────────────────────────────────────────────────────────────


def _score_example(
    example: GoldenExample,
    skills: list,
) -> tuple[bool, Optional[str], float]:
    """Score one golden example against all skills.

    Args:
        example: The golden example to evaluate.
        skills:  List of skill instances.

    Returns:
        Tuple of (is_correct, actual_top_skill_name, actual_top_score).
        ``actual_top_skill_name`` is ``None`` when all skills score 0.
    """
    ctx: dict = {}
    top_score = 0.0
    top_skill_name: Optional[str] = None

    for skill in skills:
        try:
            score = skill.can_handle(example.utterance, ctx)
        except Exception:
            score = 0.0
        if score > top_score:
            top_score = score
            top_skill_name = type(skill).__name__

    # Determine if the actual routing matches the golden expectation
    if example.expected_match:
        # Should route to expected_skill at ≥ threshold
        is_correct = (
            top_skill_name == example.expected_skill
            and top_score >= _SKILL_INJECT_THRESHOLD
        )
    else:
        # Should NOT route to expected_skill at ≥ threshold
        if example.expected_skill is None:
            # No skill should fire at all
            is_correct = top_score < _SKILL_INJECT_THRESHOLD
        else:
            # Either wrong skill wins or score below threshold
            is_correct = (
                top_skill_name != example.expected_skill
                or top_score < _SKILL_INJECT_THRESHOLD
            )

    return is_correct, top_skill_name, top_score


def _compute_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Compute precision, recall, F1 from raw counts.

    Returns:
        (precision, recall, f1) — all in [0.0, 1.0].
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return precision, recall, f1


# ── Baseline I/O ─────────────────────────────────────────────────────────────


def _load_baseline(path: Path = _BASELINE_PATH) -> Optional[float]:
    """Load the stored baseline accuracy from JSON.

    Args:
        path: Path to the baseline JSON file.

    Returns:
        Baseline accuracy as a float in [0.0, 1.0], or ``None`` if not found.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data["accuracy"])
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return None


def _save_baseline(report: "EvalReport", path: Path = _BASELINE_PATH) -> None:
    """Overwrite the baseline JSON with the current report's accuracy.

    Args:
        report: The completed eval report to persist.
        path:   Path to write the baseline JSON file.
    """
    data = {
        "accuracy": report.accuracy,
        "total": report.total,
        "correct": report.correct,
        "per_skill_f1": {
            name: round(m.f1, 4)
            for name, m in report.per_skill.items()
        },
        "saved_at": report.run_timestamp,
        "golden_set_size": len(GOLDEN_SET),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Main entry point ──────────────────────────────────────────────────────────


def run_eval(
    skills: Optional[list] = None,
    save_baseline: bool = False,
    baseline_path: Path = _BASELINE_PATH,
    golden_set: Optional[list[GoldenExample]] = None,
) -> "EvalReport":
    """Run the full eval harness and return a structured report.

    No LLM calls are made — routing is evaluated using ``can_handle()``
    heuristics only (NFR-EVAL-001).

    Args:
        skills:        Skill instances to evaluate. Defaults to all 8 built-in
                       skills if ``None``.
        save_baseline: If ``True``, overwrite the baseline JSON with this run's
                       accuracy after evaluation.
        baseline_path: Path to the baseline JSON (default: ``src/eval/baseline.json``).
        golden_set:    Examples to evaluate. Defaults to ``GOLDEN_SET`` if ``None``.

    Returns:
        ``EvalReport`` with accuracy, per-skill metrics, regression flag, and
        list of failing utterances.
    """
    if skills is None:
        skills = _load_builtin_skills()
    if golden_set is None:
        golden_set = GOLDEN_SET

    # Build per-skill metric accumulators
    all_skill_names = [type(s).__name__ for s in skills]
    metrics: dict[str, SkillMetrics] = {
        name: SkillMetrics(skill_name=name) for name in all_skill_names
    }

    correct = 0
    gaps: list[str] = []

    for example in golden_set:
        is_correct, actual_skill, actual_score = _score_example(example, skills)

        if is_correct:
            correct += 1
        else:
            if example.expected_match:
                gaps.append(example.utterance)

        # Update per-skill TP / FP / FN
        expected = example.expected_skill

        if example.expected_match and expected:
            if is_correct:
                # TP: expected this skill and got it
                if expected in metrics:
                    metrics[expected].tp += 1
            else:
                # FN: expected this skill but did not get it
                if expected in metrics:
                    metrics[expected].fn += 1
                # FP: if wrong skill fired, credit that skill with a FP
                if actual_skill and actual_skill != expected and actual_skill in metrics:
                    if actual_score >= _SKILL_INJECT_THRESHOLD:
                        metrics[actual_skill].fp += 1

        elif not example.expected_match:
            if not is_correct:
                # A skill fired when it shouldn't have (or wrong skill)
                if actual_skill and actual_skill in metrics and actual_score >= _SKILL_INJECT_THRESHOLD:
                    metrics[actual_skill].fp += 1

    # Compute F1 for each skill
    for m in metrics.values():
        m.precision, m.recall, m.f1 = _compute_f1(m.tp, m.fp, m.fn)

    total = len(golden_set)
    accuracy = correct / total if total > 0 else 0.0
    baseline_accuracy = _load_baseline(baseline_path)

    regression = (
        baseline_accuracy is not None
        and accuracy < baseline_accuracy - _REGRESSION_THRESHOLD
    )

    report = EvalReport(
        total=total,
        correct=correct,
        accuracy=accuracy,
        per_skill=metrics,
        regression=regression,
        baseline_accuracy=baseline_accuracy,
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        gaps=gaps,
    )

    if save_baseline:
        _save_baseline(report, baseline_path)

    return report
