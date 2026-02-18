# NakshatraAI — Project Status Report

> **Last Updated:** 2026-02-17  
> **Project Name:** NakshatraAI — Expert Astrology AI Chatbot  
> **Phase:** Active Development (Post-MVP)

---

## Executive Summary

NakshatraAI is a production-grade AI chatbot for Vedic and Western astrology, designed for integration into a mobile application. The system combines **deterministic astronomical calculations** (Swiss Ephemeris) with **LLM-powered interpretation** (RAG + persona-driven responses) and a robust **safety/guardrails layer**.

The project has matured past the MVP stage. Core components — calculation engines, orchestration, RAG pipeline, safety classifier, API layer, and multilingual support — are **implemented and functional**. Current work focuses on refinement, validation rule engineering, and preparation for fine-tuning.

---

## Component Status Overview

| Component | Status | Maturity | Key Files |
|---|---|---|---|
| **Vedic Calculation Engine** | ✅ Complete | Production | `src/engines/vedic/` (8 files, ~141 KB) |
| **Western Calculation Engine** | ✅ Complete | Production | `src/engines/western/` (7 files, ~100 KB) |
| **Core Ephemeris Layer** | ✅ Complete | Production | `src/engines/core/` (6 files, ~55 KB) |
| **LangGraph Orchestrator** | ✅ Complete | Production | `src/orchestration/orchestrator.py` (1,693 lines) |
| **Intent Classifier** | ✅ Complete | Production | `src/ai/intent_classifier.py` (482 lines) |
| **RAG Engine** | ✅ Complete | Production | `src/rag/rag_engine.py` (876 lines) |
| **Retriever (Hybrid)** | ✅ Complete | Production | `src/rag/retriever.py` (391 lines) |
| **LLM Factory** | ✅ Complete | Production | `src/llm/factory.py` (348 lines) |
| **Safety Classifier** | ✅ Complete | Production | `src/safety/classifier.py` (491 lines) |
| **FastAPI REST API** | ✅ Complete | Production | `src/api/` (5 routes, middleware, schemas) |
| **Multilingual Support** | ✅ Complete | Production | `src/locales/` (6 languages + detector) |
| **PDF Extraction Pipeline** | ✅ Complete | Production | `src/rag/extraction/` (6 files, ~117 KB) |
| **Text Preprocessing Pipeline** | ✅ Complete | Production | `src/rag/preprocessing/` (11 files, ~162 KB) |
| **Cost Tracking & Logging** | ✅ Complete | Production | `src/utils/cost_*.py` (3 files, ~53 KB) |
| **Vedic Validation Engine** | 🔄 In Progress | Beta | `src/prediction/vedic_validation_engine_v2.py` (35 KB) |
| **Validation Rule Sets** | 🔄 In Progress | Beta | Root-level JSON files (~92 MB total) |
| **User Persona System** | ✅ Complete | Production | `src/ai/persona_generator.py`, `personas.py` |
| **Conversation Memory** | ✅ Complete | Production | `src/rag/memory_retriever.py`, `scripts/conversation_store.py` |
| **Backend Data Adapter** | ✅ Complete | Production | `src/services/backend_data_adapter.py` |
| **Astrology Data Service** | ✅ Complete | Production | `src/services/astrology_service.py` |
| **Docker Deployment** | ✅ Complete | Ready | `Dockerfile`, `docker-compose.yml` |

---

## Detailed Module Status

### 1. Calculation Engines (✅ Complete)

Deterministic astronomical computation — the foundation of the system.

**Vedic Engine** (`src/engines/vedic/`):
- `vedic_engine.py` — Main engine: birth chart, lagna, planetary positions
- `rashi_nakshatra.py` — Rashi (zodiac sign) and Nakshatra calculations
- `dasha_systems.py` — Vimshottari dasha period calculations
- `aspects_yogas.py` — Aspect and yoga detection
- `divisional_charts.py` — Navamsa and other divisional charts
- `graha_stats.py` — Planetary strength (Shadbala)
- `vedic_constants.py` — Constants, ayanamsa definitions

**Western Engine** (`src/engines/western/`):
- `western_engine.py` — Main engine: tropical chart calculations
- `western_aspects.py` — Aspect pattern detection
- `western_dignities.py` — Essential and accidental dignities
- `western_houses.py` — House system calculations
- `western_signs.py` — Sign characteristics and rulerships

**Core Layer** (`src/engines/core/`):
- `ephemeris.py` — Swiss Ephemeris wrapper (sidereal + tropical)
- `datetime_utils.py` — Julian Day conversions, timezone handling
- `coordinates.py` — Geographic positioning
- `celestial_bodies.py` — Planet/point enumerations
- `exceptions.py` — Custom exception hierarchy

### 2. LangGraph Orchestrator (✅ Complete)

The central nervous system — `src/orchestration/orchestrator.py` (1,693 lines).

**Routing Architecture (4-way):**
1. **CHITCHAT** → Quick conversational response (no calculations, no RAG)
2. **CALCULATION_ONLY** → Raw chart data via VedicEngine (no LLM interpretation)
3. **RAG_WITH_CALCULATION** → Personalized predictions (chart + RAG + LLM)
4. **RAG_ONLY** → General astrology theory (RAG + LLM, no chart)

**Processing Pipeline (node sequence):**
```
authenticate → detect_language → classify_intent → [route] → validate_response → format_response
```

**Key Features:**
- Stateless production mode (chart data injected via API)
- Clarification node for ambiguous queries
- Critic/verification loop against safety constitution
- Streaming response generation
- Validation engine integration (optional, graceful fallback)

### 3. RAG Pipeline (✅ Complete)

**Retrieval** (`src/rag/retriever.py`):
- Semantic search (ChromaDB + OpenAI embeddings)
- BM25 keyword search
- Hybrid search (Reciprocal Rank Fusion)
- HyDE (Hypothetical Document Embedding)
- Context expansion (adjacent chunk fetching)
- Language-aware filtering

**RAG Engine** (`src/rag/rag_engine.py`):
- Automatic query routing (keyword/conceptual/general strategies)
- Follow-up query detection and expansion
- Persona-driven prompt building
- Conversation history integration
- Session management and persistent storage

**Extraction** (`src/rag/extraction/`):
- Vision LLM pipeline for PDF-to-text extraction
- Structured extraction schemas (chapters, verses, tables)
- Gemini API integration for batch processing

**Preprocessing** (`src/rag/preprocessing/`):
- 6-phase pipeline: Structural Cleaning → Cross-page Analysis → Semantic Segmentation → Chunk Enrichment → Sub-chunking → Embedding/Ingestion
- Book profiler for source-specific processing
- LLM-assisted enrichment (metadata, topics, relationships)
- Vector DB builder for ChromaDB ingestion

### 4. LLM Factory (✅ Complete)

Centralized LLM management — `src/llm/factory.py`:
- **Providers:** OpenAI, Ollama (with purpose-based model selection)
- **Rate limiting:** Built-in `RateLimitedLLM` wrapper with retry logic
- **Purpose-based selection:** Different models for `general`, `classification`, `safety`
- **Prompt templates:** Persona-driven templates in `src/llm/prompts/`

### 5. Safety & Guardrails (✅ Complete)

Multi-gate safety system — `src/safety/`:
- **Classifier** (`classifier.py`) — LLM + semantic route matching
- **Input Validator** (`input_validator.py`) — Pattern-based pre-screening
- **Constitution** (`constitution.py`) — Astrologer behavior rules
- **Disclaimers** (`disclaimers.py`) — Domain-specific disclaimer engine
- **Templates** (`templates.py`) — Safety prompt templates

**Safety Categories:** SAFE, DISCLAIMER, BLOCK, REFRAME  
**Blocked Topics:** Death prediction, medical diagnosis, legal advice  
**Disclaimer Topics:** Health tendencies, financial trends, relationship compatibility

### 6. API Layer (✅ Complete)

FastAPI REST API — `src/api/`:
- **Routes:** Chat, User, Calculation, Health
- **Auth:** User authentication via dependency injection
- **Schemas:** Pydantic models for request/response validation
- **Middleware:** CORS, request timing, global exception handling
- **Config:** Environment-based settings with `.env` support

### 7. Multilingual Support (✅ Complete)

`src/locales/` — 6 Indian languages + English:
- English (`en.json`), Hindi (`hi.json`), Tamil (`ta.json`)
- Marathi (`mr.json`), Telugu (`te.json`), Malayalam (`ml.json`), Punjabi (`pa.json`)
- `language_detector.py` — Library-based detection with LLM fallback

### 8. Supporting Services

- **User Manager** (`src/ai/user_manager.py`) — Profile management, birth data storage
- **Astrology Service** (`src/services/astrology_service.py`) — 3rd-party API orchestration with Redis caching
- **Backend Data Adapter** (`src/services/backend_data_adapter.py`) — Mobile app integration layer
- **Cache Manager** (`src/services/cache_manager.py`) — Redis-based caching with TTL
- **Cost Tracking** (`src/utils/cost_logger.py`, `cost_tracking.py`, `cost_report.py`) — LLM usage monitoring

---

## Test Coverage

**20 test files** in `tests/`:

| Test File | Coverage Area |
|---|---|
| `test_api.py` | API endpoint testing |
| `test_safety.py` | Safety classifier validation |
| `test_cost_logger.py` | Cost tracking accuracy |
| `test_cost_integration.py` | End-to-end cost flow |
| `test_dynamic_personas.py` | Persona generation |
| `test_indian_languages.py` | Indian language support |
| `test_language_detection.py` | Language detection accuracy |
| `test_language_switching.py` | Mid-conversation language switch |
| `test_multilingual_rag.py` | Cross-lingual RAG retrieval |
| `test_pdf_extraction.py` | PDF processing pipeline |
| `test_preprocessing.py` | Text preprocessing phases |
| `test_hybrid_priority.py` | Hybrid retrieval priority |
| `test_conversation_context.py` | Context management |
| `test_session_context.py` | Session persistence |
| `test_persistence_caching.py` | Cache layer testing |
| `test_stateless_architecture.py` | Stateless mode verification |
| `test_backend_integration.py` | Backend adapter testing |
| `test_marriage_prediction_fix.py` | Specific prediction fix |

---

## Data Assets

| Asset | Size | Purpose |
|---|---|---|
| `final_vedic_astro_rules.json` | 28.5 MB | Master validation rule set |
| `vedic_astro_validation_rules.json` | 27.8 MB | Active validation rules |
| `consolidated_final.json` | 25.9 MB | Consolidated extracted rules |
| `Brihat_Parasara_Hora_Vol1_enriched.json` | 2.7 MB | BPHS Vol 1 extracted rules |
| `Brihat_Parasara_Hora_Vol2_enriched.json` | 7.7 MB | BPHS Vol 2 extracted rules |
| `Phaladeepika_rules.json` | 2.0 MB | Phaladeepika extracted rules |
| `checkpoint_rules.json` | 7.5 MB | Extraction checkpoint |
| `data/vectordb/` | — | ChromaDB persistent storage |

---

## Infrastructure & Deployment

- **Runtime:** Python 3.x with venv
- **LLM Providers:** OpenAI (primary), Ollama (local dev)
- **Embeddings:** OpenAI `text-embedding-3-large` (3072 dims)
- **Vector DB:** ChromaDB (persistent)
- **Cache:** Redis (optional, for production)
- **User DB:** MongoDB (production) / SQLite dummy (dev)
- **API Framework:** FastAPI + Uvicorn
- **Containerization:** Docker + docker-compose
- **Ephemeris:** Swiss Ephemeris (pyswisseph)
- **Config:** Pydantic Settings + YAML + .env

---

## What's Working (End-to-End)

1. ✅ CLI chatbot with full conversational flow (`chatbot.py`)
2. ✅ FastAPI REST API with all endpoints
3. ✅ Vedic birth chart calculation → LLM interpretation pipeline
4. ✅ RAG retrieval from ingested astrology books
5. ✅ 4-way intent routing with LLM classification
6. ✅ Safety classification with blocking, disclaimers, and reframing
7. ✅ Multilingual responses (6 Indian languages)
8. ✅ PDF extraction and text preprocessing for new books
9. ✅ Cost tracking and logging
10. ✅ Streaming response generation

---

## What's In Progress / Pending

### 🔄 In Progress
1. **Vedic Validation Engine V2** — Rule-based validation of chart strength before prediction
2. **Validation Rule Engineering** — Refining extracted rules from classical texts (~92 MB of JSON rules being processed)
3. **Rule Indexing & Optimization** — Scripts for tier classification, consolidation, and index building

### 📋 Planned / Not Yet Started
1. **Fine-tuning** — Dataset preparation from validated responses, LoRA/QLoRA training
2. **Western Engine Integration** — Western engine exists but is not yet wired into the orchestrator routing
3. **Production Deployment** — Docker deployment to cloud (currently local dev only)
4. **Monitoring & Observability** — Production-grade logging, metrics, alerting
5. **User Feedback Loop** — Collect user ratings to improve responses
6. **A/B Testing Framework** — Compare model versions and prompt strategies
7. **Advanced Persona Customization** — User-selectable astrologer personas

---

## File Statistics

| Category | Count | Total Size |
|---|---|---|
| Source Python files (`src/`) | ~95 | ~850 KB |
| Test files (`tests/`) | 20 | ~143 KB |
| Config files | 4 | ~42 KB |
| Utility scripts (`scripts/`) | 6 | ~53 KB |
| Root-level tool scripts | ~12 | ~192 KB |
| Documentation (`.md`) | ~20 | ~180 KB |
| Data/Rule JSON files | ~8 | ~92 MB |

---

## Key Entry Points

| Purpose | File | Command |
|---|---|---|
| CLI Chatbot | `chatbot.py` | `python chatbot.py --user_id test_user` |
| REST API Server | `src/api/main.py` | `uvicorn src.api.main:app --reload` |
| PDF Extraction | `scripts/extract_pdf.py` | `python scripts/extract_pdf.py` |
| Preprocessing | `scripts/run_preprocessing_phases.py` | `python scripts/run_preprocessing_phases.py` |
| Add Test User | `scripts/add_dummy_user.py` | `python scripts/add_dummy_user.py` |
| LLM Factory Test | `src/llm/factory.py` | `python -m src.llm.factory` |
