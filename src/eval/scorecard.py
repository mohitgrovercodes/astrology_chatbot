# src/eval/scorecard.py
"""
Scorecard persistence + Markdown summary writers.

JSON layout (schema_version: 1):
{
  schema_version, started_at, finished_at, config,
  totals: {scenarios, passed, failed, errored, overall_score},
  by_tag: {<tag>: {count, mean_score}},
  scenarios: [
    {id, tags, aggregate_score, passed, error, elapsed_s, turns: [...]},
    ...
  ]
}

Diff strategy:
  - Pair scenarios by id
  - Per scenario: report Δaggregate_score (sign-coded)
  - Per check: count regressions (passing→failing) vs improvements (failing→passing)
  - Per tag: report Δmean_score
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Writers
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_results_dir(results_dir: str) -> Path:
    p = Path(results_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_scorecard(
    scorecard: Dict[str, Any],
    results_dir: str = "data/eval_results",
    label: Optional[str] = None,
) -> Dict[str, str]:
    """
    Persist a scorecard to disk. Writes:
      - <timestamp>[_label].json — full record
      - latest.json              — copy of most recent run
    Returns paths written.
    """
    rdir = _ensure_results_dir(results_dir)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    stem = f"{ts}_{label}" if label else ts
    json_path = rdir / f"{stem}.json"
    latest_path = rdir / "latest.json"

    blob = json.dumps(scorecard, indent=2, default=str, ensure_ascii=False)
    json_path.write_text(blob, encoding="utf-8")
    latest_path.write_text(blob, encoding="utf-8")

    return {"json": str(json_path), "latest_json": str(latest_path)}


def load_scorecard(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_previous_scorecard(results_dir: str, current_path: str) -> Optional[str]:
    """Return the most recent JSON in results_dir other than `current_path`."""
    rdir = Path(results_dir)
    if not rdir.exists():
        return None
    cur = Path(current_path).resolve()
    candidates = []
    for p in rdir.glob("*.json"):
        if p.name == "latest.json":
            continue
        if p.resolve() == cur:
            continue
        candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0])


# ──────────────────────────────────────────────────────────────────────────────
# Markdown summary
# ──────────────────────────────────────────────────────────────────────────────

def _pct(score: float) -> str:
    return f"{score * 100:.1f}%"


def _badge(passed: bool, errored: bool = False) -> str:
    if errored:
        return "ERROR"
    return "PASS" if passed else "FAIL"


def _format_table(rows: List[List[str]], headers: List[str]) -> str:
    """Tiny Markdown table builder (no external deps)."""
    sizes = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
    fmt_row = lambda cells: "| " + " | ".join(c.ljust(sizes[i]) for i, c in enumerate(cells)) + " |"
    out = [
        fmt_row(headers),
        "| " + " | ".join("-" * sizes[i] for i in range(len(headers))) + " |",
    ]
    for r in rows:
        out.append(fmt_row(r))
    return "\n".join(out)


def _compute_diff(
    cur: Dict[str, Any],
    prev: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two scorecards by scenario id and per-check pass/fail flips."""
    cur_map = {s["id"]: s for s in cur.get("scenarios", [])}
    prev_map = {s["id"]: s for s in prev.get("scenarios", [])}

    regressions: List[Tuple[str, float, float, float]] = []  # (id, prev, cur, Δ)
    improvements: List[Tuple[str, float, float, float]] = []
    unchanged: int = 0
    only_cur: List[str] = []
    only_prev: List[str] = []

    for sid, s_cur in cur_map.items():
        if sid not in prev_map:
            only_cur.append(sid)
            continue
        s_prev = prev_map[sid]
        cs = float(s_cur.get("aggregate_score", 0.0))
        ps = float(s_prev.get("aggregate_score", 0.0))
        delta = round(cs - ps, 3)
        if abs(delta) < 0.01:
            unchanged += 1
        elif delta < 0:
            regressions.append((sid, ps, cs, delta))
        else:
            improvements.append((sid, ps, cs, delta))
    for sid in prev_map:
        if sid not in cur_map:
            only_prev.append(sid)

    regressions.sort(key=lambda x: x[3])      # most negative first
    improvements.sort(key=lambda x: -x[3])    # most positive first

    # Per-tag mean delta
    cur_tags = cur.get("by_tag", {}) or {}
    prev_tags = prev.get("by_tag", {}) or {}
    tag_deltas = []
    for t, c in cur_tags.items():
        p = prev_tags.get(t)
        if not p:
            continue
        d = round(c.get("mean_score", 0) - p.get("mean_score", 0), 3)
        tag_deltas.append((t, p.get("mean_score", 0), c.get("mean_score", 0), d))
    tag_deltas.sort(key=lambda x: x[3])  # worst first

    # Overall delta
    overall_delta = round(
        cur.get("totals", {}).get("overall_score", 0)
        - prev.get("totals", {}).get("overall_score", 0),
        3,
    )

    return {
        "overall_delta": overall_delta,
        "unchanged": unchanged,
        "regressions": regressions,
        "improvements": improvements,
        "only_cur": only_cur,
        "only_prev": only_prev,
        "tag_deltas": tag_deltas,
    }


def write_markdown_summary(
    scorecard: Dict[str, Any],
    results_dir: str = "data/eval_results",
    current_json_path: Optional[str] = None,
    prev_json_path: Optional[str] = None,
) -> str:
    """
    Build a human-readable Markdown digest of the scorecard.
    Writes data/eval_results/latest.md. Returns the path.

    If a previous scorecard exists (either explicit prev_json_path or the
    most recent file in results_dir other than the current one), emits a
    regression diff section.
    """
    rdir = _ensure_results_dir(results_dir)
    out_path = rdir / "latest.md"

    totals = scorecard.get("totals", {})
    by_tag = scorecard.get("by_tag", {}) or {}
    scenarios = scorecard.get("scenarios", []) or []
    cfg = scorecard.get("config", {})

    started = datetime.utcfromtimestamp(scorecard.get("started_at", 0)).strftime("%Y-%m-%d %H:%M UTC")
    duration = scorecard.get("finished_at", 0) - scorecard.get("started_at", 0)

    lines: List[str] = []
    lines.append(f"# NakshatraAI Eval Scorecard — {started}")
    lines.append("")
    lines.append(f"- **Server**: {cfg.get('base_url', 'unknown')}")
    lines.append(f"- **Scenarios run**: {totals.get('scenarios', 0)}  "
                 f"(passed: **{totals.get('passed', 0)}**, "
                 f"failed: {totals.get('failed', 0)}, "
                 f"errored: {totals.get('errored', 0)})")
    lines.append(f"- **Overall score**: **{_pct(totals.get('overall_score', 0.0))}**  "
                 f"(threshold {cfg.get('pass_threshold', 0.7) * 100:.0f}%)")
    lines.append(f"- **LLM judge enabled**: {cfg.get('llm_judge_enabled', False)}")
    lines.append(f"- **Duration**: {duration:.1f}s")
    lines.append("")

    # ─── Score by tag ────────────────────────────────────────────────────
    if by_tag:
        lines.append("## Score by tag")
        lines.append("")
        rows = []
        for tag, info in sorted(by_tag.items(), key=lambda kv: kv[1]["mean_score"]):
            rows.append([tag, str(info.get("count", 0)), _pct(info.get("mean_score", 0.0))])
        lines.append(_format_table(rows, ["tag", "count", "mean score"]))
        lines.append("")

    # ─── Per-scenario table ──────────────────────────────────────────────
    lines.append("## Scenarios")
    lines.append("")
    rows = []
    for s in scenarios:
        rows.append([
            s.get("id", ""),
            ",".join(s.get("tags", []))[:40],
            _badge(s.get("passed", False), errored=bool(s.get("error"))),
            _pct(s.get("aggregate_score", 0.0)),
            f"{s.get('elapsed_s', 0):.1f}s",
            (s.get("error") or "")[:60],
        ])
    lines.append(_format_table(
        rows,
        ["id", "tags", "result", "score", "time", "error"],
    ))
    lines.append("")

    # ─── Failing-check inventory ─────────────────────────────────────────
    lines.append("## Failing deterministic checks (across all turns)")
    lines.append("")
    check_failures: Dict[str, int] = {}
    for s in scenarios:
        for t in s.get("turns", []):
            for c in t.get("deterministic", []):
                if not c.get("passed"):
                    check_failures[c["name"]] = check_failures.get(c["name"], 0) + 1
    if check_failures:
        rows = [
            [name, str(count)]
            for name, count in sorted(check_failures.items(), key=lambda x: -x[1])
        ]
        lines.append(_format_table(rows, ["check", "failures"]))
    else:
        lines.append("All deterministic checks passed across all turns.")
    lines.append("")

    # ─── Diff vs previous run ────────────────────────────────────────────
    prev_path = prev_json_path
    if prev_path is None and current_json_path:
        prev_path = _find_previous_scorecard(results_dir, current_json_path)
    if prev_path and Path(prev_path).exists():
        try:
            prev = load_scorecard(prev_path)
            diff = _compute_diff(scorecard, prev)
            lines.append(f"## Diff vs previous run ({Path(prev_path).name})")
            lines.append("")
            arrow = "▲" if diff["overall_delta"] > 0 else ("▼" if diff["overall_delta"] < 0 else "·")
            lines.append(f"- **Overall delta**: {arrow} {diff['overall_delta']:+.3f}")
            lines.append(f"- Unchanged: {diff['unchanged']}  · "
                         f"Regressed: {len(diff['regressions'])}  · "
                         f"Improved: {len(diff['improvements'])}")
            if diff["only_cur"]:
                lines.append(f"- New scenarios: {', '.join(diff['only_cur'][:5])}"
                             + (f" (+{len(diff['only_cur'])-5})" if len(diff["only_cur"]) > 5 else ""))
            if diff["only_prev"]:
                lines.append(f"- Removed scenarios: {', '.join(diff['only_prev'][:5])}"
                             + (f" (+{len(diff['only_prev'])-5})" if len(diff["only_prev"]) > 5 else ""))
            lines.append("")
            if diff["regressions"]:
                lines.append("### Top regressions")
                lines.append("")
                rows = [
                    [sid, _pct(p), _pct(c), f"{d:+.3f}"]
                    for sid, p, c, d in diff["regressions"][:10]
                ]
                lines.append(_format_table(rows, ["scenario", "prev", "current", "Δ"]))
                lines.append("")
            if diff["improvements"]:
                lines.append("### Top improvements")
                lines.append("")
                rows = [
                    [sid, _pct(p), _pct(c), f"{d:+.3f}"]
                    for sid, p, c, d in diff["improvements"][:10]
                ]
                lines.append(_format_table(rows, ["scenario", "prev", "current", "Δ"]))
                lines.append("")
            if diff["tag_deltas"]:
                lines.append("### Tag deltas")
                lines.append("")
                rows = [
                    [tag, _pct(p), _pct(c), f"{d:+.3f}"]
                    for tag, p, c, d in diff["tag_deltas"]
                ]
                lines.append(_format_table(rows, ["tag", "prev", "current", "Δ"]))
                lines.append("")
        except Exception as exc:
            lines.append(f"## Diff vs previous run")
            lines.append("")
            lines.append(f"_Could not compute diff: {type(exc).__name__}: {exc}_")
            lines.append("")
    else:
        lines.append("_No previous scorecard found — this is the first run for this directory._")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
