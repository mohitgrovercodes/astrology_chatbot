#!/usr/bin/env python3
"""
Backfill yoga metadata across every *_enriched.json file in data/raw/.

The enricher's old `extract_entities` left `metadata.entities.yogas` empty
because it had no yoga catalog. This script re-runs yoga extraction (via
src/rag/preprocessing/yoga_catalog.py) over each chunk's display_text +
text_for_embedding and updates the JSON in place. It deliberately operates on
raw dicts so it does not need pydantic — useful when running in environments
where the application stack is not installed.

Outputs:
    - Each *_enriched.json gets its chunks[].metadata.entities.yogas filled.
    - A summary report is printed to stdout with per-book yoga counts.
    - A side-car JSON (yoga_backfill_report.json) lands next to the inputs
      so you can diff runs.

Usage:
    python scripts/backfill_yogas.py                       # run over data/raw/*.json
    python scripts/backfill_yogas.py --dry-run             # report only, no writes
    python scripts/backfill_yogas.py --path some/file.json # single file
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

# Make src/ importable so we can use the yoga catalog without installing the
# package. This keeps the script runnable from a vanilla checkout.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "rag" / "preprocessing"))

from yoga_catalog import extract_yogas  # noqa: E402


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _chunk_text(chunk: dict) -> str:
    """
    Pick the best text field to scan. We prefer `display_text` because it is
    the verbatim source text (no synthesized headers from `text_for_embedding`),
    but we fall back to `text_for_embedding` and finally `combined_text` so
    older intermediate formats still work.
    """
    return (
        chunk.get("display_text")
        or chunk.get("text_for_embedding")
        or chunk.get("combined_text")
        or ""
    )


def backfill_file(path: Path, dry_run: bool = False) -> Dict:
    """
    Re-extract yogas for every chunk in `path` and write the file back.

    Returns a stats dict for the report:
        {
            "file": str,
            "source_book": str,
            "chunks_total": int,
            "chunks_with_yogas": int,
            "yoga_counts": {canonical: count},
            "previously_had_yogas": int,
        }
    """
    with path.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    chunks = doc.get("chunks", [])
    if not chunks:
        return {"file": str(path), "chunks_total": 0, "skipped": "no chunks"}

    source_book = chunks[0].get("metadata", {}).get("source_book", path.stem)

    yoga_counts: Counter = Counter()
    chunks_with_yogas = 0
    previously_had = 0

    for chunk in chunks:
        meta = chunk.setdefault("metadata", {})
        entities = meta.setdefault(
            "entities",
            {
                "planets": [],
                "houses": [],
                "signs": [],
                "nakshatras": [],
                "yogas": [],
                "concepts": [],
            },
        )

        if entities.get("yogas"):
            previously_had += 1

        text = _chunk_text(chunk)
        yogas = extract_yogas(text)

        entities["yogas"] = yogas
        if yogas:
            chunks_with_yogas += 1
            for y in yogas:
                yoga_counts[y] += 1

    stats = {
        "file": str(path),
        "source_book": source_book,
        "chunks_total": len(chunks),
        "chunks_with_yogas": chunks_with_yogas,
        "previously_had_yogas": previously_had,
        "yoga_counts": dict(yoga_counts.most_common()),
    }

    if not dry_run:
        # Write atomically: serialize to a tmp file beside the target, then rename.
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    return stats


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(all_stats: List[Dict]) -> None:
    print()
    print("=" * 78)
    print("YOGA BACKFILL REPORT")
    print("=" * 78)

    global_counter: Counter = Counter()
    grand_total_chunks = 0
    grand_chunks_with = 0

    for s in all_stats:
        if s.get("skipped"):
            print(f"\n[SKIP] {s['file']} ({s['skipped']})")
            continue
        print()
        print(f"[{s['source_book']}]")
        print(f"  file               : {Path(s['file']).name}")
        print(f"  chunks (total)     : {s['chunks_total']}")
        print(
            f"  chunks with yogas  : {s['chunks_with_yogas']}"
            f"  ({(s['chunks_with_yogas'] / s['chunks_total']) * 100:.1f}%)"
        )
        print(f"  previously had set : {s['previously_had_yogas']}")
        # Top 10 yogas per book
        top = list(s["yoga_counts"].items())[:10]
        if top:
            print("  top yogas          :")
            for name, count in top:
                print(f"      {count:>4}  {name}")
        else:
            print("  top yogas          : (none detected)")

        grand_total_chunks += s["chunks_total"]
        grand_chunks_with += s["chunks_with_yogas"]
        for name, count in s["yoga_counts"].items():
            global_counter[name] += count

    print()
    print("-" * 78)
    print("CORPUS-WIDE TOTALS")
    print("-" * 78)
    print(f"  chunks (total)         : {grand_total_chunks}")
    pct = (grand_chunks_with / grand_total_chunks * 100) if grand_total_chunks else 0
    print(f"  chunks tagged w/ yoga  : {grand_chunks_with}  ({pct:.1f}%)")
    print(f"  distinct yogas detected: {len(global_counter)}")
    print()
    print("  Top 25 yogas across corpus:")
    for name, count in global_counter.most_common(25):
        print(f"      {count:>6}  {name}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument(
        "--raw-dir",
        default=str(ROOT / "data" / "raw"),
        help="Folder containing *_enriched.json files (default: data/raw)",
    )
    parser.add_argument(
        "--path",
        help="Operate on a single enriched JSON file instead of a folder.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute stats but do not write back to disk.",
    )
    parser.add_argument(
        "--report-out",
        default=str(ROOT / "data" / "raw" / "yoga_backfill_report.json"),
        help="Where to write the machine-readable report.",
    )
    args = parser.parse_args()

    if args.path:
        files = [Path(args.path)]
    else:
        raw_dir = Path(args.raw_dir)
        if not raw_dir.exists():
            print(f"[ERROR] raw dir not found: {raw_dir}")
            return 2
        # Detect enriched files by SHAPE, not by filename. The corpus has a few
        # files that are in enriched format but happen to be named without an
        # "_enriched" suffix (e.g. Phaladeepika_by_Mantreswara.json,
        # Saravali_vol2.json). We sniff for the `chunks` key + the canonical
        # chunk fields and accept any JSON that matches.
        candidates: List[Path] = []
        for p in sorted(raw_dir.glob("*.json")):
            if p.name == "yoga_backfill_report.json":
                continue
            try:
                with p.open("r", encoding="utf-8") as f:
                    head = json.load(f)
            except Exception:
                continue
            if isinstance(head, dict) and isinstance(head.get("chunks"), list) and head["chunks"]:
                ch = head["chunks"][0]
                if isinstance(ch, dict) and "display_text" in ch and "metadata" in ch:
                    candidates.append(p)
        files = candidates

    if not files:
        print("[ERROR] no enriched JSON files found")
        return 2

    print(f"[INFO] processing {len(files)} file(s){' (dry run)' if args.dry_run else ''}")

    all_stats: List[Dict] = []
    for path in files:
        if path.name == "yoga_backfill_report.json":
            continue
        try:
            stats = backfill_file(path, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {path.name}: {exc}")
            stats = {"file": str(path), "skipped": f"error: {exc}"}
        all_stats.append(stats)

    print_report(all_stats)

    # Persist machine-readable report so future diff runs can show drift.
    if not args.dry_run:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(all_stats, f, ensure_ascii=False, indent=2)
        print(f"[OK] report written to {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
