# CLAUDE.md — Project Orientation

This is the root of the **NakshatraAI** astrology chatbot — a production-grade Vedic + Western astrology RAG system. Read this file first; everything else is linked from here.

## What this project is

A FastAPI service that fuses:
- **Deterministic astronomical calculations** (Swiss Ephemeris via `src/engines/vedic/` and `src/engines/western/`).
- **LLM synthesis** (Gemini 2.5 Pro for answers, Gemini 2.5 Flash for classification/safety) orchestrated by a LangGraph state machine (`src/orchestration/orchestrator.py`, ~8k lines).
- **RAG over 16 classical astrology books** (`data/raw/*_enriched.json`, embedded into ChromaDB at `data/vectordb/`).
- **Symbolic chart-validation rules** (`optimized/tiered_rules.json`, 16.5k rules across 4 tiers).

## Where things live

```
src/
  ai/               # SemanticFrame, intent classification, hybrid_retriever
  engines/          # Vedic + Western calculation engines (Swiss Ephemeris wrappers)
  orchestration/    # LangGraph orchestrator + helpers (tier selection, validation router)
  prediction/       # FactorScorer, AnswerPlanner, accuracy gate
  rag/
    preprocessing/  # Phase 1-7 pipeline (extraction -> ChromaDB)
    extraction/     # PDF -> JSON via Gemini Vision
    retriever.py    # Baseline AstrologyRetriever (semantic + BM25 + HyDE)
    ingest_local.py # Legacy ingest path -- DO NOT USE (different metadata convention)
  validation/       # VedicValidationEngineV2, ChartSynthesisEngine
  safety/           # 3 safety gates
  eval/             # Eval harness
scripts/
  backfill_planets.py        # NER backfill -- planets
  backfill_yogas.py          # NER backfill -- yogas
  update_chroma_planets.py   # Metadata-only push (no re-embed)
  update_chroma_yogas.py     # Metadata-only push (no re-embed)
data/
  raw/              # 16 enriched JSONs, currently ~14,475 chunks
  vectordb/         # ChromaDB persistent store (currently empty pending Phase 6/7)
optimized/
  tiered_rules.json # 16,526 chart-validation rules in 4 tiers
config/             # YAML + Python configs
docs/               # Start with docs/INDEX.md
```

## Read these before doing RAG work

| Doing | Read |
|---|---|
| Any embedding / ingestion task | [docs/INGESTION.md](docs/INGESTION.md) |
| Editing or extending NER catalogs | [docs/NER_CATALOGS.md](docs/NER_CATALOGS.md) |
| Tuning the retriever / tier rules | [docs/EMBEDDING_STRATEGY.md](docs/EMBEDDING_STRATEGY.md), [docs/HEURISTICS_AND_RETRIEVAL.md](docs/HEURISTICS_AND_RETRIEVAL.md), [docs/TIERED_RULE_ANALYSIS.md](docs/TIERED_RULE_ANALYSIS.md) |
| End-to-end architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Setup / local dev / cost | [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) |
| Mobile / backend integration | [docs/API_REFERENCE.md](docs/API_REFERENCE.md) |

## Conventions worth knowing immediately

- **Metadata convention**: `vector_db_builder._prepare_metadata` stores entity lists as comma-joined strings: `metadata["planets"] = "Sun,Saturn,Moon"`. The retriever filters with `$contains` against this exact shape. The alternative `src/rag/ingest_local.py` uses `entity_planets` keys with `", "` separators that **do not match the retriever** -- never use it.
- **Two "tier" concepts**: `optimized/tiered_rules.json` holds *symbolic chart-validation* tiers (1-4, selected by `determine_validation_tier`). The retriever has a separate *intent-keyed `top_k`* tier (`PREDICTION->15, INTERPRETATION->12, ...`). They are independent. See `docs/EMBEDDING_STRATEGY.md` section 3.
- **Multilingual corpus**: chunks may be English, IAST, Devanagari, or mixed. `text_for_embedding` prepends an English LLM summary so even pure Sanskrit chunks embed in English-shaped space. NER catalogs handle Latin word-boundary AND Devanagari Unicode-range lookbehind.
- **Phaladeepika landmine**: there were two files for the same book with different `source_book` labels. The mislabelled one (`Paladeepika_enriched.json`, labelled `Saravali_Vol1`) was deleted. Watch for this pattern when ingesting any new file.
- **Sandbox / Windows mount quirk**: file deletes and large `Write` operations on the Windows-mounted `data/raw/` can fail or truncate. Prefer `Edit` for surgical changes; fall back to `bash` heredoc / `python -c "open(...).write(...)"` for full file rewrites. Backfill scripts already do atomic `*.tmp -> *.json` renames.
