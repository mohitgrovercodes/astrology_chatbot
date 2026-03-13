# NakshatraAI — Master System Architecture

> **Last Updated:** March 2026
> **Status:** Production Architecture

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Flow & Lifecycle](#data-flow--lifecycle)
3. [Calculation Engines (Vedic & Western)](#calculation-engines-vedic--western)
4. [RAG Pipeline](#rag-pipeline)
5. [Orchestrator & Validation](#orchestrator--validation)
6. [Safety Framework](#safety-framework)
7. [Caching & State Architecture](#caching--state-architecture)
8. [Module Map](#module-map)

---

## Architecture Overview

**NakshatraAI** is a production-grade AI-powered astrology chatbot backing a mobile application via FastAPI. It fuses deterministic astronomical calculations (Swiss Ephemeris) with dynamic AI interpretation grounded in classical astrological knowledge.

### Core Design Principles

1. **Determinism over Probability** — Hard calculations (charts, transits, dashas) are computed in Python via Swiss Ephemeris, never estimated by the LLM.
2. **Safety-First** — A multi-tiered guardrail system runs before any query reaches the main LLM.
3. **Stateless Scalability** — A shared Redis instance stores all user data permanently, enabling context continuity across indefinite gaps in usage.
4. **Authoritative Knowledge** — LLM interpretations are grounded using Retrieval-Augmented Generation (RAG) over classical astrological texts (BPHS, etc.).
5. **Validation Before Synthesis** — 750+ JSON-configured rules score and gate predictions before the LLM synthesizes an answer.

---

## Data Flow & Lifecycle

```
User Query from Mobile App
    |
+---v-----------------------------------------+
|  FastAPI Layer (src/api/)                   |
|  - API key authentication (X-API-Key)       |
|  - Rate limiting (10 req/min per key)       |
|  - /initialize  or  /message routing       |
+---+-----------------------------------------+
    |
+---v-----------------------------------------+
|  Session Manager (Redis)                    |
|  - Load user profile (permanent)            |
|  - Load conversation history (permanent)    |
|  - Load/refresh birth chart (permanent)     |
|  - Load/refresh transits (24h staleness)    |
|  - Load/refresh dashas (30d staleness)      |
+---+-----------------------------------------+
    |
+---v-----------------------------------------+
|  LangGraph Orchestrator                     |
|  (src/orchestration/orchestrator.py)        |
|  - Language detection                       |
|  - Intent classification (embeddings)       |
|  - Safety gates (-1, 0, 1, 2)              |
|  - Route: CHITCHAT / RAG / CALC / HYBRID   |
+---+---------+----------+--------------------+
    |         |          |
+---v---+ +---v----+ +---v-------------------+
| Calc  | |  RAG   | |  Validation Engine    |
| Engine| |Retriever| |  750+ rules (JSON)   |
| Vedic | |BM25+Vec| |  Strength scoring     |
| Western|Reranker | |  Hard-halt on invalid |
+---+---+ +---+----+ +---+-------------------+
    |         |          |
+---v---------v----------v-------------------+
|  LLM Synthesis (GPT-4o-mini)               |
|  - Chart data + RAG chunks + rules         |
|  - Conversation history (last 10 msgs)     |
|  - Append domain disclaimers               |
|  - Localize output (EN/HI/TA/PA)          |
+---+-----------------------------------------+
    |
Response to Mobile App
```

---

## Calculation Engines (Vedic & Western)

All astronomical computation uses `pyswisseph` (Python bindings for Swiss Ephemeris), ensuring arc-second precision.

### Vedic Engine (`src/engines/vedic/`)

- **Zodiac**: Sidereal with Lahiri (Chitrapaksha) Ayanamsa
- **Planets**: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu (+ Ascendant)
- **Divisional Charts**: Full D1–D60 varga chart computation (`divisional_charts.py`)
- **Dasha System**: Vimshottari Dasha — Mahadasha, Antardasha, and Pratyantardasha with exact date ranges
- **Yogas**: Raj Yoga, Dhana Yoga, Kendra–Trikona combinations, and more (`aspects_yogas.py`)
- **Dignities**: Exaltation, Debilitation, Moolatrikona, Own Sign
- **Graha Stats**: Speed, retrograde status, combustion detection (`graha_stats.py`)

### Western Engine (`src/engines/western/`)

- **Zodiac**: Tropical
- **Planets**: Sun through Pluto + Chiron
- **House Systems**: Placidus, Koch, Whole Sign, Equal House (configurable)
- **Aspects**: Major (Conjunction, Trine, Square, Opposition, Sextile) and minor aspects with configurable orbs
- **Essential Dignities**: Rulership, Exaltation, Detriment, Fall (`western_dignities.py`)

---

## RAG Pipeline

The RAG system prevents hallucinations on astrology philosophy, classical rules, and timing techniques by injecting relevant text from authoritative sources into the LLM context.

### Pipeline Stages

1. **Extraction** (`src/rag/extraction/batch_extract.py`)
   - PDFs processed through Gemini Vision
   - Primary model: `gemini-2.5-flash-lite` (2× faster, 60% lower cost)
   - Auto-upgrade to `gemini-2.5-pro` on low-confidence pages

2. **Preprocessing & Segmentation** (`src/rag/preprocessing/`)
   - Structural normalization (removes headers, footers, page artifacts)
   - Semantic segmentation respecting verse boundaries (e.g., `॥ 42 ॥`)
   - LLM-assisted intelligent book profiling

3. **Enrichment**
   - Each chunk generates a summary
   - Named entity extraction (Planets, Houses, Signs)

4. **Vector Store**
   - 14,000+ chunks embedded with OpenAI `text-embedding-3-large` (3072 dimensions)
   - Stored in ChromaDB at `data/vectordb/`
   - Collection: `vedic_astrology_books_knowledge`

5. **Retrieval** (`src/rag/retriever.py`)
   - Hybrid: BM25 keyword (30%) + Semantic vector (70%)
   - HyDE (Hypothetical Document Embeddings) for conceptual queries
   - Cross-encoder reranking via Sentence-Transformers (`src/rag/reranker.py`)
   - Per-intent top-k configuration (validation: 15; interpretation: 10)

---

## Orchestrator & Validation

### LangGraph Orchestrator (`src/orchestration/orchestrator.py`)

NakshatraAI uses LangGraph to construct a deterministic state machine for all conversation flows (~3,100 lines).

**Routing states:**
- `CHITCHAT` — General conversation; no calculation needed
- `CALCULATION_ONLY` — Pure chart/transit/dasha retrieval
- `RAG_ONLY` — Knowledge lookup from classical texts
- `RAG_WITH_CALCULATION` — Full pipeline: calculate + retrieve + synthesize

**Key nodes:**
- Language detector (auto-detect from `langdetect`)
- Intent classifier (embedding-based semantic routing)
- Safety gates
- Chart loader/refresher
- Dasha loader/refresher
- Transit loader/refresher
- RAG retriever
- Validation engine runner
- LLM synthesis
- Response formatter + disclaimer injection + localization

### Runtime Behavior (Current)

- **Progressive disclosure phases:** `INITIAL` -> `AWAITING_DETAIL` -> `FOLLOWUP_LOOP`
  - Initial turn stays concise and asks whether the user wants deeper astrological reasoning.
  - Detailed turn provides richer explanation with explicit factors (house-lord logic, dasha windows, yogas, divisional support).
- **Language/script mirroring:** response language is enforced from the user's original text per turn (native script vs romanized).
- **Validation + Judge merge:** post-processing validator performs semantic coherence checks and tone/voice quality checks in one LLM pass.
- **Domain unification:** `intent_analysis.domain` is used as hint for `query_type` selection to reduce double-classification drift.
- **Divisional chart plumbing:** Vedic vargas are exposed via `divisional_charts_simple`; Navamsa is mirrored into validation payload as both `D9` and `navamsa`.

### Validation Engine (`src/validation/vedic_validation_engine_v2.py`)

- **750+ rules** organized in JSON across 3 tiers:
  - **Tier 1** (critical): Birth time required, chart integrity checks
  - **Tier 2** (standard): 7th lord position, D9 chart, Dasha strength, house occupancy
  - **Tier 3** (enhancement): Yoga combinations, special conditions
- Returns a **strength score (0–10)** for each prediction domain
- **Hard-halt** on invalid data (missing birth time, incomplete profile)
- **Age validator** (`src/validation/age_validator.py`) gates timing predictions based on the user's current age

---

## Safety Framework

A multi-gate safety system (`src/safety/`) prevents harmful or unethical astrological responses.

| Gate | Name | Description |
|---|---|---|
| Gate -1 | Own-Data Detection | Confirms the user is asking about their own chart, not fabricated data |
| Gate 0 | Third-Party Soft-Block | Blocks inquiries about specific third parties ("When will my friend die?") |
| Gate 1 | Semantic Routing | Hard-blocks medical diagnoses, legal advice, death/suicide predictions |
| Gate 2 | LLM Classifier | Nuanced handling — pivots harmful framing to empowering alternatives (e.g., "Will I divorce?" → "What do planetary periods indicate about relationship dynamics?") |

Additional components:
- **Input validator** (`src/safety/input_validator.py`) — sanitizes and validates all inputs
- **Output disclaimers** (`src/safety/disclaimers.py`) — domain-specific (health, finance, relationships)
- **System constitution** (`src/safety/constitution.py`) — injected into every LLM prompt

---

## Caching & State Architecture

All data defaults to **permanent storage** in Redis (no TTL). This ensures users can return after weeks of inactivity and have their full context restored instantly.

| Data | Storage | TTL / Refresh Policy |
|---|---|---|
| User Profile | `redis.set()` | Permanent (no TTL) |
| Birth Chart | `redis.set()` | Permanent — birth geometry never changes |
| Conversation History | `redis.set()` | Permanent — sliding window of last 10 messages |
| Transits Data | `redis.set()` | Application-level refresh when `stored_at` is > `TRANSIT_REFRESH_HOURS=24` |
| Dasha Data | `redis.set()` | Application-level refresh when `stored_at` is > `DASHA_REFRESH_DAYS=30` |

This application-level eviction model ensures Redis never prunes data for inactive users, while guaranteeing astronomically correct transits and periods when they return.

---

## Module Map

```
src/
├── api/                    FastAPI application, routes, middleware, schemas
│   ├── routes/
│   │   ├── chat_stateless.py   Main chat endpoints (/initialize, /message)
│   │   ├── calculation.py      Birth chart endpoint
│   │   ├── health.py           Health check
│   │   └── user.py             User CRUD
│   └── middleware/
│       ├── auth.py             X-API-Key authentication
│       └── rate_limit.py       Rate limiting (10 req/min)
├── engines/
│   ├── core/               Swiss Ephemeris wrapper, coordinates, datetime utils
│   ├── vedic/              Vedic engine: D1-D60, Dasha, Yogas, Aspects
│   └── western/            Western engine: Houses, Aspects, Dignities
├── orchestration/          LangGraph state machine (~3,100 lines)
├── rag/                    Extraction, preprocessing, retrieval, reranking
├── llm/                    LLM factory (OpenAI primary, Ollama fallback)
├── safety/                 4-gate safety framework
├── validation/             750+ rule validation + age validator + synthesis
├── session/                Redis session lifecycle manager
├── routing/                Embedding-based semantic intent router
├── utils/                  Cost tracking, logging, serializers, formatters
└── locales/                EN, HI, TA, PA translation templates
```
