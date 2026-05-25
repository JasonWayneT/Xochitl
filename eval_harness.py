#!/usr/bin/env python3
"""Xochitl eval harness CLI runner.

Implements FR-EVAL-001–003, NFR-EVAL-001 (CR-022).

Evaluates skill routing accuracy against the golden set, reports per-skill
F1, and detects regressions against the stored baseline.

Usage::

    python eval_harness.py                   # compare against baseline
    python eval_harness.py --save-baseline   # run and overwrite baseline
    python eval_harness.py --no-color        # plain output (CI-friendly)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ is importable when run from project root
sys.path.insert(0, str(Path(__file__).parent))


def _plain_report(report: object) -> None:
    """Print a plain-text report (no Rich dependency required)."""
    print(f"\n=== Xochitl Eval Harness ===\n")
    print(f"  Total examples : {report.total}")
    print(f"  Correct        : {report.correct}")
    print(f"  Accuracy       : {report.accuracy:.1%}")
    if report.baseline_accuracy is not None:
        delta = report.accuracy - report.baseline_accuracy
        sign = "+" if delta >= 0 else ""
        print(f"  Baseline       : {report.baseline_accuracy:.1%}  ({sign}{delta:.1%})")
    print()

    # Per-skill table
    print(f"  {'Skill':<25}  {'TP':>4}  {'FP':>4}  {'FN':>4}  {'P':>6}  {'R':>6}  {'F1':>6}")
    print(f"  {'-'*25}  {'--':>4}  {'--':>4}  {'--':>4}  {'------':>6}  {'------':>6}  {'------':>6}")
    for name, m in report.per_skill.items():
        print(
            f"  {name:<25}  {m.tp:>4}  {m.fp:>4}  {m.fn:>4}"
            f"  {m.precision:>5.0%}  {m.recall:>5.0%}  {m.f1:>5.0%}"
        )

    if report.gaps:
        print(f"\n  Failing utterances ({len(report.gaps)}):")
        for g in report.gaps:
            print(f"    FAIL: {g}")

    if report.regression:
        print(f"\n  !! REGRESSION DETECTED -- accuracy dropped > 5pp from baseline\n")
    else:
        print(f"\n  OK  No regression detected.\n")


def _rich_report(report: object) -> None:
    """Print a Rich-formatted report (preferred output)."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        from rich.panel import Panel
        from rich.text import Text
    except ImportError:
        _plain_report(report)
        return

    console = Console()
    console.print()

    # Header
    acc_color = "green" if not report.regression else "red"
    delta_str = ""
    if report.baseline_accuracy is not None:
        delta = report.accuracy - report.baseline_accuracy
        sign = "+" if delta >= 0 else ""
        delta_color = "green" if delta >= 0 else "red"
        delta_str = f"  [dim]vs baseline:[/dim] [{delta_color}]{sign}{delta:.1%}[/{delta_color}]"

    header = Text()
    header.append("Xochitl Eval Harness\n", style="bold cyan")
    header.append(f"  {report.correct}/{report.total} correct  ", style="")
    header.append(f"{report.accuracy:.1%}", style=f"bold {acc_color}")
    if delta_str:
        console.print(Panel(header, expand=False))
        console.print(f"  [dim]baseline {report.baseline_accuracy:.1%}[/dim]{delta_str}\n")
    else:
        console.print(Panel(header, expand=False))
        console.print()

    # Per-skill table
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("Skill", style="cyan", width=26)
    table.add_column("TP", justify="right", width=4)
    table.add_column("FP", justify="right", width=4)
    table.add_column("FN", justify="right", width=4)
    table.add_column("Precision", justify="right", width=9)
    table.add_column("Recall", justify="right", width=7)
    table.add_column("F1", justify="right", width=6)

    for name, m in report.per_skill.items():
        f1_color = "green" if m.f1 >= 0.9 else ("yellow" if m.f1 >= 0.6 else "red")
        table.add_row(
            name,
            str(m.tp),
            str(m.fp),
            str(m.fn),
            f"{m.precision:.0%}",
            f"{m.recall:.0%}",
            f"[{f1_color}]{m.f1:.0%}[/{f1_color}]",
        )
    console.print(table)

    if report.gaps:
        console.print(f"  [dim]Failing utterances ({len(report.gaps)}):[/dim]")
        for g in report.gaps:
            console.print(f"    [dim red]✗[/dim red] [dim]{g}[/dim]")
        console.print()

    if report.regression:
        console.print(
            "[bold red]⚠  REGRESSION DETECTED[/bold red] — "
            "accuracy dropped > 5pp from baseline\n"
        )
    else:
        console.print("[green]✓  No regression detected.[/green]\n")


def main() -> int:
    """Run the eval harness. Returns exit code (0 = OK, 1 = regression)."""
    parser = argparse.ArgumentParser(description="Xochitl skill routing eval harness")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Overwrite baseline.json with this run's accuracy",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Plain text output (CI-friendly, no Rich)",
    )
    args = parser.parse_args()

    from src.eval.harness import run_eval

    report = run_eval(save_baseline=args.save_baseline)

    if args.no_color:
        _plain_report(report)
    else:
        _rich_report(report)

    if args.save_baseline:
        print(f"  Baseline saved to src/eval/baseline.json\n")

    return 1 if report.regression else 0


if __name__ == "__main__":
    sys.exit(main())
