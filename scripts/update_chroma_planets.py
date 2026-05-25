#!/usr/bin/env python3
"""
Metadata-only update: push canonicalized planet metadata onto the existing
ChromaDB collection without re-embedding anything. Mirror of
update_chroma_yogas.py but for the `planets` field.

Why a separate script:
    The embeddings haven't changed — only `metadata.entities.planets` has.
    Re-running the full pipeline would re-charge LLM tokens and re-embed
    all 15K+ chunks for a single metadata field update.

What it does:
    1. Walks every enriched JSON under data/raw and builds a map
       chunk_id -> [canonical planet names].
    2. Opens the existing ChromaDB collection.
    3. Fetches current metadatas, merges the new `planets` field in (stored
       as comma-separated string per vector_db_builder._prepare_metadata),
       and updates in batches. Existing metadata fields are preserved.
    4. Idempotent — re-runs skip chunks whose stored value already matches.
    5. After writes, samples 20 chunks and confirms the round-trip.

Run after scripts/backfill_planets.py has updated the JSONs on disk.

Usage:
    python scripts/update_chroma_planets.py
    python scripts/update_chroma_planets.py --collection my_collection
    python scripts/update_chroma_planets.py --db-path data/vectordb
    python scripts/update_chroma_planets.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "vectordb"
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_COLLECTION = "vedic_astrology_books_knowledge"


def load_planets_from_disk(raw_dir: Path) -> Dict[str, List[str]]:
    """Return {chunk_id: [canonical planet names]} for every chunk."""
    mapping: Dict[str, List[str]] = {}
    for p in sorted(raw_dir.glob("*.json")):
        if p.name in ("yoga_backfill_report.json", "planet_backfill_report.json"):
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as exc:
            print(f"[WARN] skipping {p.name}: {exc}")
            continue
        if not isinstance(doc, dict) or "chunks" not in doc:
            continue
        for ch in doc["chunks"]:
            cid = ch.get("chunk_id")
            if not cid:
                continue
            entities = (ch.get("metadata") or {}).get("entities") or {}
            mapping[cid] = list(entities.get("planets") or [])
    return mapping


def push_updates(
    collection,
    chunk_planets: Dict[str, List[str]],
    dry_run: bool = False,
    batch_size: int = 200,
) -> Dict[str, int]:
    """Update the `planets` field on every chunk in the map that exists in
    the collection. Existing metadata fields are preserved."""
    print("[INFO] reading collection contents...")
    snapshot = collection.get(include=["metadatas"])
    db_ids: List[str] = snapshot["ids"]
    db_metas: List[dict] = snapshot["metadatas"]
    db_map = dict(zip(db_ids, db_metas))
    print(f"[INFO] collection has {len(db_ids)} chunks")

    in_both = [cid for cid in chunk_planets if cid in db_map]
    stranded_disk = [cid for cid in chunk_planets if cid not in db_map]
    stranded_db = [cid for cid in db_map if cid not in chunk_planets]

    print(f"[INFO] chunks on disk     : {len(chunk_planets)}")
    print(f"[INFO] chunks in DB       : {len(db_map)}")
    print(f"[INFO] chunks in both     : {len(in_both)}")
    print(f"[INFO] on disk but not DB : {len(stranded_disk)}")
    print(f"[INFO] in DB but not disk : {len(stranded_db)}")

    updates_ids: List[str] = []
    updates_metas: List[dict] = []
    unchanged = set_new = cleared = 0

    for cid in in_both:
        new_planets = chunk_planets[cid]
        new_value = ",".join(new_planets) if new_planets else ""
        existing_meta = dict(db_map[cid] or {})
        existing_value = existing_meta.get("planets", "")

        if existing_value == new_value:
            unchanged += 1
            continue

        if new_value:
            existing_meta["planets"] = new_value
            set_new += 1
        else:
            existing_meta.pop("planets", None)
            cleared += 1

        updates_ids.append(cid)
        updates_metas.append(existing_meta)

    changed = len(updates_ids)
    print(f"[INFO] updates planned    : {changed}  (set: {set_new}, cleared: {cleared}, unchanged: {unchanged})")

    if dry_run:
        print("[DRY RUN] no writes performed")
        return {"planned": changed, "unchanged": unchanged, "set": set_new, "cleared": cleared}

    for i in range(0, len(updates_ids), batch_size):
        batch_ids = updates_ids[i:i + batch_size]
        batch_metas = updates_metas[i:i + batch_size]
        try:
            collection.update(ids=batch_ids, metadatas=batch_metas)
            print(f"  [OK] batch {i // batch_size + 1}/{(len(updates_ids) + batch_size - 1) // batch_size}"
                  f"  ({len(batch_ids)} chunks)")
        except Exception as exc:
            print(f"  [ERROR] batch {i // batch_size + 1} failed: {exc}")

    return {"planned": changed, "unchanged": unchanged, "set": set_new, "cleared": cleared}


def verify(collection, chunk_planets: Dict[str, List[str]], sample_size: int = 20) -> None:
    import random
    candidates = [cid for cid, ps in chunk_planets.items() if ps]
    if not candidates:
        print("[VERIFY] no chunks-with-planets to sample")
        return
    sample = random.sample(candidates, k=min(sample_size, len(candidates)))
    got = collection.get(ids=sample, include=["metadatas"])
    by_id = dict(zip(got["ids"], got["metadatas"]))

    print()
    print(f"[VERIFY] sampling {len(sample)} chunks with planets...")
    bad = 0
    for cid in sample:
        expected = ",".join(chunk_planets[cid])
        actual = (by_id.get(cid) or {}).get("planets", "")
        if actual != expected:
            bad += 1
            print(f"  [MISS] {cid}: expected {expected!r}, got {actual!r}")
    print(f"[VERIFY] {len(sample) - bad}/{len(sample)} matched")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--db-path", default=str(DEFAULT_DB))
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        print("[ERROR] chromadb not installed. Run from the venv used to build the vector DB.")
        return 2

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        print(f"[ERROR] raw dir not found: {raw_dir}")
        return 2

    chunk_planets = load_planets_from_disk(raw_dir)
    if not chunk_planets:
        print("[ERROR] no chunks discovered in enriched JSONs")
        return 2

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"[ERROR] ChromaDB path not found: {db_path}")
        return 2

    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False, allow_reset=False),
    )
    try:
        collection = client.get_collection(name=args.collection)
    except Exception as exc:
        print(f"[ERROR] could not open collection {args.collection!r}: {exc}")
        return 2

    print(f"[OK] connected to collection: {args.collection}")
    print(f"[OK] db path: {db_path}")

    summary = push_updates(collection, chunk_planets, dry_run=args.dry_run, batch_size=args.batch_size)

    if not args.dry_run and not args.skip_verify:
        verify(collection, chunk_planets)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:>10s}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
