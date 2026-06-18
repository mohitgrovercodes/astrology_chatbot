# Corpus Ingestion Runbook

> **End-to-end operational guide for getting `data/raw/*.json` into the live ChromaDB collection.**
> Covers Phase 6 (embedding generation), Phase 7 (vector DB build), the metadata-only update path used after NER/HyDE backfills, and the corruption / duplicate checks worth running before kicking off any embedding work.

---

## Status (May 2026)

| Step | State |
|---|---|
| Enriched JSONs on disk | ✅ 16 books, 14,475 chunks, NER-canonicalised across English / IAST / Devanagari |
| Mislabeled Phaladeepika duplicate | ✅ Removed (was labelled `source_book="Saravali_Vol1"` but contained Phaladeepika content) |
| Embedder dimension consistency | ✅ All seven construction sites now resolve to `settings.EMBEDDING_DIMENSIONS` (default 1536). The `src/api/dependencies.py:get_embeddings()` 768/1536 mismatch is fixed; `src/rag/memory_retriever.py` no longer hardcodes 1536 |
| Phase 6 (embed) | ⏳ Not started — corpus has `embedding=null` on every chunk |
| Phase 7 (ingest) | ⏳ Not started — `data/vectordb/` contains an empty Chroma sqlite + segment folder |
| ChromaDB collection `vedic_astrology_books_knowledge` | ⏳ Empty (0 chunks) — pending Phase 6 + 7 |

---

## Pipeline shape

```
PDFs ──► Phase 1-5 (extraction / segmentation / enrichment / NER)
            │
            ▼
        data/raw/*.json      (display_text, summary, entities, embedding=null)
            │
            │  ── Phase 6: embedder.py ──────────────────────────┐
            ▼                                                    │
        data/raw/*_embedded.json    (embedding populated)        │
            │                                                    │
            │  ── Phase 7: vector_db_builder.py ─────────────────┤
            ▼                                                    │
        data/vectordb/  (ChromaDB collection: vedic_astrology_books_knowledge)
                                                                 │
                                                                 ▼
        Updates after NER / HyDE backfills:
            scripts/backfill_*.py        →   updates JSONs in place
            scripts/update_chroma_*.py   →   pushes metadata-only diff to Chroma
```

The split matters. Embeddings are derived from `text_for_embedding` (built by the enricher in Phase 5) and are expensive to regenerate. Metadata (`entities.planets`, `entities.yogas`, `summary`, `verse_number`, …) is cheap to update and can be pushed without touching vectors.

---

## Pre-ingest checklist

Run this in the venv that backs the rest of the pipeline. None of these steps embed or write to Chroma.

```bash
# 1. Confirm every enriched JSON parses and has the fields ingestion needs.
python - <<'PY'
import json, pathlib
total = bad = no_text = no_id = 0
for p in sorted(pathlib.Path("data/raw").glob("*.json")):
    if p.name.endswith("_backfill_report.json"): continue
    doc = json.load(p.open(encoding="utf-8"))
    if not isinstance(doc, dict) or "chunks" not in doc:
        bad += 1; continue
    for c in doc["chunks"]:
        total += 1
        if not c.get("text_for_embedding"): no_text += 1
        if not c.get("chunk_id"): no_id += 1
print(dict(chunks=total, bad_files=bad, missing_text=no_text, missing_id=no_id))
PY

# 2. Look for duplicate source_book labels (the Phaladeepika trap).
python - <<'PY'
import json, pathlib
labels = {}
for p in sorted(pathlib.Path("data/raw").glob("*.json")):
    if p.name.endswith("_backfill_report.json"): continue
    doc = json.load(p.open(encoding="utf-8"))
    for c in doc.get("chunks", [])[:1]:
        labels.setdefault(c["metadata"].get("source_book"), []).append(p.name)
        break
for k, v in labels.items():
    if len(v) > 1:
        print("DUP source_book:", k, "->", v)
PY

# 3. Confirm GOOGLE_CLOUD_PROJECT / credentials are set.
python -c "import os, dotenv; dotenv.load_dotenv(); print('project=', os.getenv('GOOGLE_CLOUD_PROJECT'), 'cred=', bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')))"
```

Resolve any duplicate labels (delete the wrong file) before embedding — Chroma `upsert` only dedupes on `chunk_id`, so two files with non-overlapping IDs but identical content get embedded twice.

---

## Phase 6 — Embedding generation

`src/rag/preprocessing/embedder.py` calls **Vertex AI `gemini-embedding-001`** at 1536 dimensions, batched (default 100) with exponential backoff on 429s and dynamic batch shrinking when quotas tighten.

```bash
# One file
python -m src.rag.preprocessing.embedder data/raw/<file>.json
# → writes data/raw/<file>_embedded.json

# Whole corpus
for f in data/raw/*.json; do
  case "$f" in *_backfill_report.json|*_embedded.json) continue ;; esac
  python -m src.rag.preprocessing.embedder "$f"
done
```

Notes:
- The embedder writes a sibling `*_embedded.json` rather than mutating in place. Originals stay safe.
- Without `GOOGLE_CLOUD_PROJECT` it falls back to zero-vectors and logs a `WARN`. Always re-check `os.getenv("GOOGLE_CLOUD_PROJECT")` before a long run.
- Quotas: tune `EMBEDDING_BATCH_SIZE` in `.env` if you see sustained 429s; the embedder will halve the batch size itself but starting smaller saves wall-clock.

---

## Phase 7 — Vector DB build

`src/rag/preprocessing/vector_db_builder.py` upserts every chunk with a non-zero embedding into ChromaDB.

```bash
# Single book
python -m src.rag.preprocessing.vector_db_builder \
  data/raw/<file>_embedded.json \
  --db-path data/vectordb \
  --collection vedic_astrology_books_knowledge

# Whole corpus — same command, repeated. Upsert is idempotent.
for f in data/raw/*_embedded.json; do
  python -m src.rag.preprocessing.vector_db_builder "$f" \
    --db-path data/vectordb \
    --collection vedic_astrology_books_knowledge
done

# Inspect the result
python -m src.rag.preprocessing.vector_db_builder \
  --stats --collection vedic_astrology_books_knowledge
```

Metadata serialisation (handled by `_prepare_metadata`):

| Field | Type in JSON | Stored as |
|---|---|---|
| `entities.planets` (list) | `["Sun","Moon"]` | `metadata["planets"] = "Sun,Moon"` |
| `entities.yogas` (list) | `["Gajakesari"]` | `metadata["yogas"] = "Gajakesari"` |
| `entities.houses` / `signs` / `nakshatras` / `concepts` | list | comma-joined string |
| `source_pages` (list[int]) | `[12, 13]` | `json.dumps([12, 13])` |
| Everything else (`chunk_id`, `source_book`, `chapter`, `verse_number`, `tradition`, `token_count`, `has_verse`) | scalar | scalar |

This convention matters: the retriever's `_build_where_clause` uses `$contains` on the comma-joined strings, so a query filter like `planets=Saturn` will match `"Sun,Saturn,Moon"`. **Do not** use `src/rag/ingest_local.py` instead — it writes under `entity_planets` / `entity_yogas` keys with `", "` separators that the retriever's filters never check.

---

## Metadata-only update path (no re-embed)

Use this whenever an NER catalog, HyDE prompt, or summary changes but the embedding text does not.

```bash
# 1. Update the JSON on disk
python scripts/backfill_planets.py        # or backfill_yogas.py
# → mutates data/raw/*.json atomically (tmp + rename), writes a per-book report

# 2. Push the diff to Chroma — preserves all other metadata fields
python scripts/update_chroma_planets.py   # or update_chroma_yogas.py
# → batched update, idempotent, 20-chunk sample verification at the end
```

Each `update_chroma_*.py` script prints the four bookkeeping numbers worth eyeballing:

```
[INFO] chunks on disk     : 14475
[INFO] chunks in DB       : 14475
[INFO] updates planned    : 174  (set: 142, cleared: 32, unchanged: 14269)
[VERIFY] 20/20 matched
```

The `cleared` counter is how many chunks were stripped of a stale value (e.g. a yoga the new regex no longer matches). `unchanged` means the stored value already equals the new value — re-runs after a successful push should converge to `planned: 0`.

---

## Common pitfalls

- **Empty collection, scripts report "0/20 matched"** — the push script is finding nothing to update because Phase 6/7 was never run. Check `collection.count()` first.
- **Sandbox/Windows timeout strands a `.tmp` file** in `data/raw/`. The backfill scripts atomically rename `*.json.tmp → *.json`; a strand means the rename was killed mid-flight. Re-run the script on the affected file (or delete the orphan `.tmp` manually) and continue.
- **Wrong `source_book` label** — duplicate-content files with mismatched `source_book` labels (the Phaladeepika / Saravali bug) will not deduplicate by `chunk_id` because the IDs are derived per-file. Catch with the pre-ingest check above before embedding.
- **Devanagari coverage gap** — the planet/yoga catalogs ship Devanagari roots for the high-volume cases. Pure Devanagari shlokas with no transliteration still go through the Latin-script fast prefilter; that path is bypassed on non-ASCII text via an `isascii()` check. If you see a Devanagari book with surprisingly low NER coverage, see `docs/NER_CATALOGS.md#how-to-extend-the-catalog`.
- **Embedding-dimension mismatch (the 768-vs-1536 trap)** — `gemini-embedding-001` returns 768-d vectors *unless* `output_dimensionality` is explicitly passed. Every site that constructs `VertexAIEmbeddings(...)` MUST pass `output_dimensionality=settings.EMBEDDING_DIMENSIONS`, otherwise the API's query path embeds at 768-d while the ChromaDB index is at 1536-d and every query fails. As of May 2026 this is fixed in `src/api/dependencies.py:get_embeddings()` and `src/rag/memory_retriever.py`; the higher-level `Embedder` wrapper (`src/rag/preprocessing/embedder.py`) reads the same setting. If you add a new embedding site, do not hardcode the dimension — pull from `settings.EMBEDDING_DIMENSIONS` so an `.env` change is a one-line edit.

---

## Operational quick reference

| Task | Command |
|---|---|
| Pre-ingest sanity check | the `python - <<PY ... PY` snippets above |
| Embed one book | `python -m src.rag.preprocessing.embedder data/raw/<book>.json` |
| Build ChromaDB | `python -m src.rag.preprocessing.vector_db_builder <book>_embedded.json` |
| Inspect collection | `python -m src.rag.preprocessing.vector_db_builder --stats --collection vedic_astrology_books_knowledge` |
| Re-NER planets / yogas | `python scripts/backfill_planets.py` / `scripts/backfill_yogas.py` |
| Push NER diff to ChromaDB | `python scripts/update_chroma_planets.py` / `scripts/update_chroma_yogas.py` |
