# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

```bash
# Run API server (development)
uvicorn src.api.main:app --reload

# Run API server (specific port)
uvicorn src.api.main:app --host 0.0.0.0 --port 6262 --reload

# Run CLI chatbot
python intreactive_chatbot.py

# Run tests
pytest tests/

# Run a single test file

pytest tests/test_safety.py -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Lint
ruff check src/

# Format
black src/

# Type check
mypy src/

# Docker (production)
docker-compose up --build
```

### Required Environment Variables (`.env`)

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
INTERNAL_SERVICE_SECRET=...     # Backend-to-backend auth
VALID_API_KEYS=key1,key2        # Comma-separated public API keys
REDIS_HOST=localhost
REDIS_PORT=6379
```



---

## Architecture

**NakshatraAI** is a FastAPI-based Vedic/Western astrology chatbot serving a mobile app. The system fuses deterministic planetary calculations (Swiss Ephemeris) with LLM-generated interpretations grounded in classical texts via RAG.

### Request Flow

```
Mobile App → FastAPI → chat_stateless.py (context mgmt) → Orchestrator (LangGraph)
    → Safety Gates → Intent Classifier → Calculation Engines + RAG Retriever
    → Validation Engine → LLM Synthesis → Response
```

### Key Directories

- **`src/api/`** — FastAPI layer. `main.py` wires routers; `routes/chat_stateless.py` handles the two primary mobile endpoints (`/initialize`, `/message`); `config.py` holds `settings` singleton.
- **`src/orchestration/orchestrator.py`** — LangGraph state machine (`NakshatraState`). Central hub that wires intent classification, safety checks, calculations, RAG retrieval, validation, and LLM synthesis into a single deterministic pipeline.
- **`src/engines/vedic/`** — Sidereal (Lahiri ayanamsa) calculations: birth chart, D1–D60 divisional charts, Vimshottari Dasha, yogas, dignity strengths.
- **`src/engines/western/`** — Tropical zodiac: Placidus/Koch/Whole Sign houses, major/minor aspects, essential dignities.
- **`src/engines/core/`** — Shared `pyswisseph` ephemeris wrapper, coordinates, datetime utilities.
- **`src/ai/intent_classifier.py`** — LLM-based classifier routing queries to `CHITCHAT | CALCULATION_ONLY | RAG_WITH_CALCULATION | RAG_ONLY | AMBIGUOUS`. Has a fast pattern-cache for common exact-match queries.
- **`src/safety/`** — Multi-gate safety framework. Gate -1 (own-data), Gate 0 (third-party soft-block), Gate 1 (semantic routing via `SemanticRouter`), Gate 2 (LLM classifier with REFLECTION schema). Lives in `classifier.py`, `constitution.py`, `input_validator.py`, `disclaimers.py`.
- **`src/rag/`** — RAG pipeline. `retriever.py` does hybrid BM25 (30%) + vector (70%) search over ChromaDB (`data/vectordb`). `reranker.py` applies cross-encoder. `preprocessing/` contains the full PDF ingestion pipeline (extraction → segmentation → enrichment → embedding).
- **`src/validation/`** — `VedicValidationEngineV2` evaluates prediction requests against 750+ JSON rules (`optimized/tiered_rules.json`). `AgeValidator` and `ChartSynthesisEngine` augment predictions.
- **`src/llm/factory.py`** — `LLMFactory.create(purpose=...)` is the sole way to instantiate LLMs. Supports `openai` (gpt-4o-mini default) and `free` (Ollama llama3.2). Wraps all instances in `RateLimitedLLM` with exponential backoff.
- **`src/routing/semantic_router.py`** — Embedding-based semantic routing (replaces fragile regex). Used by safety classifier and orchestrator.
- **`src/locales/`** — Multilingual support (English, Hindi, Tamil, Malayalam, Marathi, Punjabi, Telugu). `language_detector.py` uses `langdetect`.
- **`src/services/`** — `cache_manager.py` wraps Redis; `astrology_service.py` orchestrates engine calls; `backend_data_adapter.py` normalizes external API data.
- **`config/config.py`** — `AppConfig` singleton (loaded via `get_config()`). Merges `config/config.yaml` with `.env` overrides.
- **`config/rag_config.py`** — Dynamic `top_k` values per query type (validation: 15, interpretation: 10).

### State Management (Redis — Permanent Storage)

All user data defaults to **permanent** Redis storage (no TTL):
- **User profile** and **birth chart** — never expires (birth geometry is immutable).
- **Conversation history** — sliding window of last 10 messages; summarization triggers every 10 items.
- **Transit data** — recomputed when `stored_at` is stale (controlled by `TRANSIT_REFRESH_HOURS=24`).
- **Dasha data** — recomputed when stale (controlled by `DASHA_REFRESH_DAYS=30`).

### Mobile API Protocol

Two endpoints in `src/api/routes/chat_stateless.py`:
1. `POST /api/v1/chat/initialize` — one-time setup with user profile; safe no-op if session exists.
2. `POST /api/v1/chat/message` — submit user questions; full state loaded from Redis internally.

Authentication via `X-API-Key` header (public) or `INTERNAL_SERVICE_SECRET` header (backend-to-backend).

### RAG Knowledge Base

14,000+ chunks from classical texts (BPHS, Saravali, Phaladeepika, etc.) embedded with `text-embedding-3-large` at 3072 dimensions into ChromaDB at `data/vectordb`. To add new books, place PDFs in `data/raw/` and run `src/rag/extraction/vision_pipeline.py` (uses Gemini Vision for extraction).

### LLM Provider Selection

Priority: function arg → `LLM_PROVIDER` env var → `config.yaml` → default `openai`. Always use `LLMFactory.create(purpose="...")` rather than instantiating LLMs directly, as it handles rate limiting and model selection automatically.
