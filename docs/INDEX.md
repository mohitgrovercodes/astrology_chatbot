# NakshatraAI — Documentation Index

Welcome to the NakshatraAI documentation. This index links to all project docs.

---

## Core Documents

| Document | Audience | Description |
|---|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | All developers | System design, data flow, calculation engines, RAG pipeline, safety framework, and caching strategy |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) | Backend & AI engineers | Local setup, environment configuration, mobile app integration, extending predictions, RAG book management, cost tracking |
| [API_REFERENCE.md](./API_REFERENCE.md) | Mobile & backend integrators | All REST endpoints, authentication, request/response schemas, field names, rate limits, and error formats |

## RAG & Corpus

| Document | Audience | Description |
|---|---|---|
| [INGESTION.md](./INGESTION.md) | Data / RAG engineers | End-to-end runbook for Phase 6 (embedding) and Phase 7 (vector DB build), plus the metadata-only `update_chroma_*.py` path used after NER backfills |
| [NER_CATALOGS.md](./NER_CATALOGS.md) | RAG engineers | Reference for `planet_catalog.py` and `yoga_catalog.py` — canonical names, alias lists, Devanagari-aware regex, how to add new aliases without re-embedding |
| [EMBEDDING_STRATEGY.md](./EMBEDDING_STRATEGY.md) | RAG / orchestration | What `text_for_embedding` contains, how the retriever ranks within it, and how that interacts with the symbolic validation tier rules |
| [HEURISTICS_AND_RETRIEVAL.md](./HEURISTICS_AND_RETRIEVAL.md) | RAG / orchestration | When heuristics beat the LLM (and when they don't), intent-classifier design, hybrid retrieval modes |
| [TIERED_RULE_ANALYSIS.md](./TIERED_RULE_ANALYSIS.md) | Validation / synthesis | How `optimized/tiered_rules.json` is selected, filtered, and used by `VedicValidationEngineV2` and `ChartSynthesisEngine` |

---

## Quick Navigation

### Getting Started
- [Local setup & installation](./DEVELOPER_GUIDE.md#-quick-start-local-setup)
- [Docker deployment](./DEVELOPER_GUIDE.md#docker-deployment)
- [Environment variables reference](./DEVELOPER_GUIDE.md#environment-variables-reference)

### API Integration
- [2-step chat protocol](./API_REFERENCE.md#chat-backend-integration--correct-protocol)
- [Authentication](./API_REFERENCE.md#authentication)
- [Field name reference (critical)](./API_REFERENCE.md#field-name-reference-critical--do-not-mix-up)
- [Rate limiting](./API_REFERENCE.md#rate-limiting)
- [Response format](./API_REFERENCE.md#response-format)
- [Conversation behavior notes](./API_REFERENCE.md#conversation-behavior-notes)

### Architecture
- [Data flow overview](./ARCHITECTURE.md#data-flow--lifecycle)
- [Vedic calculation engine](./ARCHITECTURE.md#vedic-engine-srcenginesvedic)
- [Western calculation engine](./ARCHITECTURE.md#western-engine-srcengineswestern)
- [RAG pipeline](./ARCHITECTURE.md#rag-pipeline)
- [LangGraph orchestrator](./ARCHITECTURE.md#orchestrator--validation)
- [Safety framework](./ARCHITECTURE.md#safety-framework)
- [Redis caching strategy](./ARCHITECTURE.md#caching--state-architecture)

### AI Engineering
- [Extending prediction logic](./DEVELOPER_GUIDE.md#-extending-prediction-logic-for-ai-engineers)
- [Managing RAG books](./DEVELOPER_GUIDE.md#-managing--expanding-the-rag-books)
- [Cost tracking](./DEVELOPER_GUIDE.md#-cost-tracking-system)

### RAG Engineering
- [Pre-ingest checklist](./INGESTION.md#pre-ingest-checklist)
- [Phase 6 — Embedding](./INGESTION.md#phase-6--embedding-generation)
- [Phase 7 — ChromaDB build](./INGESTION.md#phase-7--vector-db-build)
- [Metadata-only updates after NER changes](./INGESTION.md#metadata-only-update-path-no-re-embed)
- [Adding new planet/yoga aliases](./NER_CATALOGS.md#how-to-extend-the-catalog)
- [Why summary-front-loaded embeddings matter](./EMBEDDING_STRATEGY.md#1-what-goes-into-a-chunks-embedding)
- [Validation tier rules vs retrieval tier](./EMBEDDING_STRATEGY.md#3-what-tier-rules-means-here-and-whether-embeddings-help)

---

## Project Stats

| Metric | Value |
|---|---|
| Python source files | 103 (src/) · 148 total (incl. tests & scripts) |
| Orchestrator size | 7,000+ lines |
| Validation rules | 16,500+ (80 evaluated per live request) |
| RAG knowledge chunks | 14,475 enriched (16 books) — 54.7% tagged with canonical planets, 4.9% with canonical yogas |
| Supported language codes | 13 (native + romanized Indian languages + English) |
| Safety gates | 3 (LLM-unified classifier) |
| Test files | 20 |
| LLM split | Gemini 2.5 Pro (synthesis/validation) + Gemini 2.5 Flash (classification/safety) |
