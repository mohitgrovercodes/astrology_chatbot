# src/eval/__init__.py
"""
Automated evaluation harness for NakshatraAI.

Public API:
    from src.eval import run_evaluation, EvalConfig, write_scorecard, load_scenarios

The harness runs golden scenarios from data/golden_scenarios.yaml against the
live API (per-scenario fresh session), scores each response on deterministic
rules + an LLM tone judge, and emits a JSON scorecard plus a Markdown summary.

Intended cadence: run before every meaningful change. Diff the JSON scorecards
to detect regressions.
"""

from src.eval.runner import EvalConfig, run_evaluation, load_scenarios
from src.eval.scorecard import write_scorecard, write_markdown_summary, load_scorecard

__all__ = [
    "EvalConfig",
    "run_evaluation",
    "load_scenarios",
    "write_scorecard",
    "write_markdown_summary",
    "load_scorecard",
]
