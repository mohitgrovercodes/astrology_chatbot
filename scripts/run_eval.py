#!/usr/bin/env python
"""
scripts/run_eval.py
===================
Automated eval harness — runs golden scenarios against the live API, scores
each response on deterministic rules + LLM judge, writes JSON + Markdown
scorecards to data/eval_results/.

Prereqs:
  - Server running locally (default http://localhost:6262)
  - Server started with EVAL_TELEMETRY=1 so metadata["eval"] is populated:
      EVAL_TELEMETRY=1 uvicorn src.api.main:app --port 6262
  - Redis reachable
  - GCP creds available for the LLM judge (LLMFactory uses them)

Quick start:
  # Run everything
  python scripts/run_eval.py

  # Smoke run on 2 scenarios, no LLM judge (~1 min total)
  python scripts/run_eval.py --ids career_hinglish_anxious_01 finance_english_worried_01 --no-judge

  # Only marriage scenarios
  python scripts/run_eval.py --tags marriage

  # Label this run so it's easy to find in eval_results/
  python scripts/run_eval.py --label "post-factor-scorer-fix"

  # Compare two saved runs
  python scripts/run_eval.py --compare data/eval_results/<a>.json data/eval_results/<b>.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make src/ importable when run as a script
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.eval import (
    EvalConfig,
    run_evaluation,
    write_scorecard,
    write_markdown_summary,
    load_scorecard,
)
from src.eval.scorecard import _compute_diff


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the NakshatraAI eval harness.")
    p.add_argument("--base-url", default=os.getenv("EVAL_BASE_URL", "http://localhost:6262"),
                   help="API base URL (default: http://localhost:6262).")
    p.add_argument("--api-key", default=os.getenv("EVAL_API_KEY", "test_api_key"),
                   help="X-API-Key value (default: test_api_key).")
    p.add_argument("--scenarios", default="data/golden_scenarios.yaml",
                   help="Path to golden_scenarios.yaml.")
    p.add_argument("--results-dir", default="data/eval_results",
                   help="Directory to write scorecards.")
    p.add_argument("--ids", nargs="+",
                   help="Filter to specific scenario ids.")
    p.add_argument("--tags", nargs="+",
                   help="Filter to scenarios with ANY of these tags.")
    p.add_argument("--label", default=None,
                   help="Suffix label for the output filename (e.g. 'before-fix').")
    p.add_argument("--no-judge", action="store_true",
                   help="Disable the LLM judge (deterministic checks only).")
    p.add_argument("--pass-threshold", type=float, default=0.70,
                   help="Min aggregate score for a scenario to be marked PASS (default 0.7).")
    p.add_argument("--quiet", action="store_true",
                   help="Minimal stdout output.")
    p.add_argument("--compare", nargs=2, metavar=("A", "B"),
                   help="Compare two saved scorecards and print a diff. Skips a new run.")
    return p.parse_args()


def _print_diff(a_path: str, b_path: str) -> int:
    a = load_scorecard(a_path)
    b = load_scorecard(b_path)
    diff = _compute_diff(b, a)  # treat B as 'current', A as 'previous'

    print("=" * 72)
    print(f"DIFF: {Path(a_path).name}  →  {Path(b_path).name}")
    print("=" * 72)
    arrow = "▲" if diff["overall_delta"] > 0 else ("▼" if diff["overall_delta"] < 0 else "·")
    print(f"  Overall delta:  {arrow} {diff['overall_delta']:+.3f}")
    print(f"  Unchanged:      {diff['unchanged']}")
    print(f"  Regressed:      {len(diff['regressions'])}")
    print(f"  Improved:       {len(diff['improvements'])}")
    if diff["regressions"]:
        print("\n  Top regressions:")
        for sid, p, c, d in diff["regressions"][:10]:
            print(f"    {sid:50}  {p:.2f} → {c:.2f}  ({d:+.3f})")
    if diff["improvements"]:
        print("\n  Top improvements:")
        for sid, p, c, d in diff["improvements"][:10]:
            print(f"    {sid:50}  {p:.2f} → {c:.2f}  ({d:+.3f})")
    if diff["tag_deltas"]:
        print("\n  Tag deltas:")
        for tag, p, c, d in diff["tag_deltas"]:
            print(f"    {tag:30}  {p:.2f} → {c:.2f}  ({d:+.3f})")
    return 0


def main() -> int:
    args = _parse_args()

    # Compare mode short-circuits the run
    if args.compare:
        return _print_diff(args.compare[0], args.compare[1])

    cfg = EvalConfig(
        base_url=args.base_url,
        api_key=args.api_key,
        scenarios_path=args.scenarios,
        ids=args.ids,
        tags=args.tags,
        enable_llm_judge=not args.no_judge,
        pass_threshold=args.pass_threshold,
        verbose=not args.quiet,
    )

    print(f"Starting eval against {cfg.base_url}")
    print(f"  scenarios: {cfg.scenarios_path}")
    if cfg.ids:
        print(f"  filter ids: {cfg.ids}")
    if cfg.tags:
        print(f"  filter tags: {cfg.tags}")
    print(f"  LLM judge: {'on' if cfg.enable_llm_judge else 'off'}")
    print(f"  pass threshold: {cfg.pass_threshold}")
    print()

    try:
        scorecard = run_evaluation(cfg)
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\n[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    # Persist
    paths = write_scorecard(scorecard, results_dir=args.results_dir, label=args.label)
    md_path = write_markdown_summary(
        scorecard,
        results_dir=args.results_dir,
        current_json_path=paths["json"],
    )

    totals = scorecard["totals"]
    print()
    print("=" * 72)
    print("EVAL COMPLETE")
    print("=" * 72)
    print(f"  scenarios     : {totals['scenarios']}")
    print(f"  passed        : {totals['passed']}")
    print(f"  failed        : {totals['failed']}")
    print(f"  errored       : {totals['errored']}")
    print(f"  overall score : {totals['overall_score'] * 100:.1f}%")
    print()
    print(f"  JSON:     {paths['json']}")
    print(f"  Markdown: {md_path}")

    # Exit 1 if anything failed (useful for CI)
    return 0 if totals["failed"] == 0 and totals["errored"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
