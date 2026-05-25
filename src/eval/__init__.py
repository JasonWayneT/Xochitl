"""Xochitl eval harness — skill routing quality measurement.

Implements FR-EVAL-001, FR-EVAL-002, FR-EVAL-003, NFR-EVAL-001 (CR-022).

Usage::

    from src.eval.harness import run_eval
    report = run_eval()
    print(f"Accuracy: {report.accuracy:.1%}")
"""
