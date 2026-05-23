#!/usr/bin/env python3
"""
Metadata-only update: push the new `yogas` metadata onto the existing
ChromaDB collection without re-embedding anything.

Why a separate script:
    The chunks already have embeddings in ChromaDB, computed by Phase 6
    (embedder.py + vector_db_builder.py). The only thing that changed is
    metadata.entities.yogas — previously hardcoded to [], now populated by
    yoga_catalog.extract_yogas() in chunk_enricher.py. Re-running the entire
    pipeline would be wasteful (LLM summaries, embeddings, etc.) when all
    we want is to set one metadata field.

What it does:
    1. Walks every *_enriched.json under data/raw/ and builds a map of
       chunk_id -> [yoga canonical names].
    2. Opens the existing ChromaDB collection (default
       `vedic_astrology_books_knowledge`).
    3. For each chunk_id present in both, fetches the current metadata,
       merges the new `yogas` field in (stored as a comma-separated string
       to satisfy ChromaDB's scalar-only metadata rule), and calls
       collection.update() in batches.
    4. Refuses to add yoga metadata for chunks that aren't in the collection,
       and prints how many such "stranded" chunks were skipped.

Run after scripts/backfill_yogas.py has updated the JSONs on disk.

Usage:
    python scripts/update_chroma_yogas.py
    python scripts/update_chroma_yogas.py --collection my_collection
    python scripts/update_chroma_yogas.py --db-path data/vectordb
    python scripts/update_chroma_yogas.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Silence ChromaDB telemetry to keep logs clean.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "vectordb"
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_COLLECTION = "vedic_astrology_books_knowledge"


# ---------------------------------------------------------------------------
# Build chunk_id -> yogas map from enriched JSONs
# ---------------------------------------------------------------------------

def load_yogas_from_disk(raw_dir: Path) -> Dict[str, List[str]]:
    """
    Return {chunk_id: [yoga canonical names]} for every chunk in every
    enriched-format JSON under `raw_dir`. Includes chunks with empty yoga
    lists too, so we can normalise stale entries in the collection.
    """
    mapping: Dict[str, List[str]] = {}
    for p in sorted(raw_dir.glob("*.json")):
        if p.name == "yoga_backfill_report.json":
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as exc:
            print(f"[WARN] skipping unreadable JSON {p.name}: {exc}")
            continue
        if not isinstance(doc, dict) or "chunks" not in doc:
            continue
        for ch in doc["chunks"]:
            cid = ch.get("chunk_id")
            if not cid:
                continue
            entities = (ch.get("metadata") or {}).get("entities") or {}
            mapping[cid] = list(entities.get("yogas") or [])
    return mapping


# ---------------------------------------------------------------------------
# Push to ChromaDB
# ---------------------------------------------------------------------------

def push_updates(
    collection,
    chunk_yogas: Dict[str, List[str]],
    dry_run: bool = False,
    batch_size: int = 200,
) -> Dict[str, int]:
    """
    Update the `yogas` field on every chunk in `chunk_yogas` that exists in
    the collection. Existing metadata fields are preserved.
    """
    # Fetch the collection's known ids + their existing metadatas.
    print("[INFO] reading collection contents...")
    snapshot = collection.get(include=["metadatas"])
    db_ids: List[str] = snapshot["ids"]
    db_metas: List[dict] = snapshot["metadatas"]
    db_map = dict(zip(db_ids, db_metas))
    print(f"[INFO] collection has {len(db_ids)} chunks")

    in_both = [cid for cid in chunk_yogas if cid in db_map]
    stranded_disk = [cid for cid in chunk_yogas if cid not in db_map]
    stranded_db = [cid for cid in db_map if cid not in chunk_yogas]

    print(f"[INFO] chunks on disk     : {len(chunk_yogas)}")
    print(f"[INFO] chunks in DB       : {len(db_map)}")
    print(f"[INFO] chunks in both     : {len(in_both)}")
    print(f"[INFO] on disk but not DB : {len(stranded_disk)}")
    print(f"[INFO] in DB but not disk : {len(stranded_db)}")

    # Build the actual updates. Skip chunks whose stored value is already
    # equal to the new one — keeps the update idempotent and cheap on re-runs.
    updates_ids: List[str] = []
    updates_metas: List[dict] = []
    changed = 0
    unchanged = 0
    cleared = 0
    set_new = 0

    for cid in in_both:
        new_yogas = chunk_yogas[cid]
        new_value = ",".join(new_yogas) if new_yogas else ""
        existing_meta = dict(db_map[cid] or {})
        existing_value = existing_meta.get("yogas", "")

        if existing_value == new_value:
            unchanged += 1
            continue

        if new_value:
            existing_meta["yogas"] = new_value
            set_new += 1
        else:
            # Remove the key so empty-yoga chunks don't carry a stale value.
            existing_meta.pop("yogas", None)
            cleared += 1

        updates_ids.append(cid)
        updates_metas.append(existing_meta)
        changed += 1

    print(f"[INFO] updates planned    : {changed}  (set: {set_new}, cleared: {cleared}, unchanged: {unchanged})")

    if dry_run:
        print("[DRY RUN] no writes performed")
        return {
            "planned": changed, "unchanged": unchanged,
            "set": set_new, "cleared": cleared,
        }

    # Batch the writes. collection.update() takes parallel id/metadata arrays.
    for i in range(0, len(updates_ids), batch_size):
        batch_ids = updates_ids[i:i + batch_size]
        batch_metas = updates_metas[i:i + batch_size]
        try:
            collection.update(ids=batch_ids, metadatas=batch_metas)
            print(f"  [OK] batch {i // batch_size + 1}/{(len(updates_ids) + batch_size - 1) // batch_size}"
                  f"  ({len(batch_ids)} chunks)")
        except Exception as exc:
            print(f"  [ERROR] batch {i // batch_size + 1} failed: {exc}")

    return {
        "planned": changed, "unchanged": unchanged,
        "set": set_new, "cleared": cleared,
    }


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(collection, chunk_yogas: Dict[str, List[str]], sample_size: int = 20) -> None:
    """Pull a random sample and confirm the yogas field round-trips."""
    import random

    candidates = [cid for cid, ys in chunk_yogas.items() if ys]
    if not candidates:
        print("[VERIFY] no chunks-with-yogas to sample")
        return

    sample = random.sample(candidates, k=min(sample_size, len(candidates)))
    got = collection.get(ids=sample, include=["metadatas"])
    by_id = dict(zip(got["ids"], got["metadatas"]))

    print()
    print(f"[VERIFY] sampling {len(sample)} chunks with yogas...")
    bad = 0
    for cid in sample:
        expected = ",".join(chunk_yogas[cid])
        actual = (by_id.get(cid) or {}).get("yogas", "")
        ok = actual == expected
        if not ok:
            bad += 1
            print(f"  [MISS] {cid}: expected {expected!r}, got {actual!r}")
    print(f"[VERIFY] {len(sample) - bad}/{len(sample)} matched")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--db-path", default=str(DEFAULT_DB),
                        help=f"Path to ChromaDB persistent storage (default: {DEFAULT_DB})")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION,
                        help=f"Collection name (default: {DEFAULT_COLLECTION})")
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW),
                        help=f"Folder with enriched JSONs (default: {DEFAULT_RAW})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute updates but do not write back to ChromaDB.")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="Update batch size (default: 200)")
    parser.add_argument("--skip-verify", action="store_true",
                        help="Skip the post-update sampling verification.")
    args = parser.parse_args()

    # Lazy-import chromadb so the script can at least be type-checked in
    # environments where the dependency isn't installed.
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        print("[ERROR] chromadb not installed in this environment. "
              "Run from the same venv used to build the vector DB.")
        return 2

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        print(f"[ERROR] raw dir not found: {raw_dir}")
        return 2

    chunk_yogas = load_yogas_from_disk(raw_dir)
    if not chunk_yogas:
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
        print("Hint: list collections with `client.list_collections()`")
        return 2

    print(f"[OK] connected to collection: {args.collection}")
    print(f"[OK] db path: {db_path}")

    summary = push_updates(
        collection,
        chunk_yogas,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )

    if not args.dry_run and not args.skip_verify:
        verify(collection, chunk_yogas)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:>10s}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
