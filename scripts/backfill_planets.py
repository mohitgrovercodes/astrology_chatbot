#!/usr/bin/env python3
"""
Backfill canonicalized planet metadata across every enriched JSON in data/raw.

The old enricher used a substring match against a flat planet list, so a
chunk that wrote "Shani" got tagged "Shani" while another that wrote "Saturn"
got tagged "Saturn" — separate strings, even though they are the same planet.
This script re-extracts planets through planet_catalog.extract_planets() which
collapses every Sanskrit alias to its English canonical (Sun / Moon / Mars /
... / Mandi).

It also canonicalizes any existing planet entries (Surya -> Sun, Chandra ->
Moon, etc.) so a chunk that already had English+Sanskrit duplicates collapses
correctly even if no fresh text scan matches.

Runs offline on raw dicts — no pydantic, no LLM.

Usage:
    python scripts/backfill_planets.py
    python scripts/backfill_planets.py --dry-run
    python scripts/backfill_planets.py --path some/file.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "rag" / "preprocessing"))

from planet_catalog import extract_planets, canonicalize_planet_list  # noqa: E402


def _chunk_text(chunk: dict) -> str:
    return (
        chunk.get("display_text")
        or chunk.get("text_for_embedding")
        or chunk.get("combined_text")
        or ""
    )


def backfill_file(path: Path, dry_run: bool = False) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    chunks = doc.get("chunks", [])
    if not chunks:
        return {"file": str(path), "chunks_total": 0, "skipped": "no chunks"}

    source_book = chunks[0].get("metadata", {}).get("source_book", path.stem)

    planet_counts: Counter = Counter()
    chunks_with_planets = 0
    canonicalised_only = 0  # chunks where text scan returned [] but the
                            # existing aliases still mapped to something
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

        existing = entities.get("planets") or []
        if existing:
            previously_had += 1

        # Primary: re-scan the chunk text with word-boundary regex.
        from_text = extract_planets(_chunk_text(chunk))

        # Secondary: salvage existing aliases like "Surya" or "Chandra" that
        # the legacy substring matcher recorded but the new regex sweep might
        # have missed (e.g. a chunk where the only planet name is in a
        # pure-Devanagari verse but the old enricher tagged it from the
        # transliterated header).
        from_existing = canonicalize_planet_list(existing) if existing else []

        # Merge stable-ordered: scan results first, then any existing
        # canonicals not already present.
        merged: List[str] = list(from_text)
        seen = set(merged)
        for p in from_existing:
            if p not in seen:
                merged.append(p)
                seen.add(p)

        if not from_text and merged:
            canonicalised_only += 1

        entities["planets"] = merged
        if merged:
            chunks_with_planets += 1
            for p in merged:
                planet_counts[p] += 1

    stats = {
        "file": str(path),
        "source_book": source_book,
        "chunks_total": len(chunks),
        "chunks_with_planets": chunks_with_planets,
        "previously_had_planets": previously_had,
        "canonicalised_only": canonicalised_only,
        "planet_counts": dict(planet_counts.most_common()),
    }

    if not dry_run:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    return stats


def print_report(all_stats: List[Dict]) -> None:
    print()
    print("=" * 78)
    print("PLANET BACKFILL REPORT")
    print("=" * 78)

    global_counter: Counter = Counter()
    grand_total_chunks = 0
    grand_chunks_with = 0
    grand_canonicalised_only = 0

    for s in all_stats:
        if s.get("skipped"):
            print(f"\n[SKIP] {s['file']} ({s['skipped']})")
            continue
        print()
        print(f"[{s['source_book']}]")
        print(f"  file                 : {Path(s['file']).name}")
        print(f"  chunks (total)       : {s['chunks_total']}")
        pct = (s['chunks_with_planets'] / s['chunks_total']) * 100 if s['chunks_total'] else 0
        print(f"  chunks with planets  : {s['chunks_with_planets']}  ({pct:.1f}%)")
        print(f"  previously had set   : {s['previously_had_planets']}")
        print(f"  rescued via canon.   : {s['canonicalised_only']}")
        for name, count in list(s["planet_counts"].items())[:11]:
            print(f"      {count:>5}  {name}")
        grand_total_chunks += s["chunks_total"]
        grand_chunks_with += s["chunks_with_planets"]
        grand_canonicalised_only += s["canonicalised_only"]
        for name, count in s["planet_counts"].items():
            global_counter[name] += count

    print()
    print("-" * 78)
    print("CORPUS-WIDE TOTALS")
    print("-" * 78)
    print(f"  chunks (total)          : {grand_total_chunks}")
    pct = (grand_chunks_with / grand_total_chunks * 100) if grand_total_chunks else 0
    print(f"  chunks tagged w/ planet : {grand_chunks_with}  ({pct:.1f}%)")
    print(f"  rescued via canonical.  : {grand_canonicalised_only}")
    print(f"  distinct planets        : {len(global_counter)}")
    print()
    print("  Per-planet totals:")
    for name, count in global_counter.most_common():
        print(f"      {count:>6}  {name}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument(
        "--raw-dir",
        default=str(ROOT / "data" / "raw"),
        help="Folder containing enriched JSON files (default: data/raw)",
    )
    parser.add_argument(
        "--path",
        help="Operate on a single enriched JSON file instead of a folder.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report-out",
        default=str(ROOT / "data" / "raw" / "planet_backfill_report.json"),
    )
    args = parser.parse_args()

    if args.path:
        files = [Path(args.path)]
    else:
        raw_dir = Path(args.raw_dir)
        if not raw_dir.exists():
            print(f"[ERROR] raw dir not found: {raw_dir}")
            return 2
        candidates: List[Path] = []
        for p in sorted(raw_dir.glob("*.json")):
            if p.name in ("yoga_backfill_report.json", "planet_backfill_report.json"):
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
        try:
            stats = backfill_file(path, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {path.name}: {exc}")
            stats = {"file": str(path), "skipped": f"error: {exc}"}
        all_stats.append(stats)

    print_report(all_stats)

    if not args.dry_run:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(all_stats, f, ensure_ascii=False, indent=2)
        print(f"[OK] report written to {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
