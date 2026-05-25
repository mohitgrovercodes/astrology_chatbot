<!-- README.md -->
# NakshatraAI — Astrology AI Chatbot

> **Production-grade AI conversational system for Vedic and Western Astrology**
> Combining deterministic astronomical calculations (Swiss Ephemeris) with LLM-powered interpretations, grounded by classical astrological texts.

[![Status](https://img.shields.io/badge/status-active-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-orange)]()

---

## Quick Links

- [Documentation Index](docs/INDEX.md) — central hub for all docs
- [Developer & Integration Guide](docs/DEVELOPER_GUIDE.md) — setup, deployment, predictions, and RAG
- [Architecture](docs/ARCHITECTURE.md) — system design, engines, and orchestration
- [API Reference](docs/API_REFERENCE.md) — endpoints, protocol, and authentication

---

## Overview

**NakshatraAI** is an expert-level astrology chatbot designed for integration into mobile applications. It fuses hard mathematical calculations with AI synthesis and classical knowledge retrieval.

### Core Features

| Feature | Description |
|---|---|
| **Dual-Engine Calculations** | Vedic (Parasara/Sidereal) + Western (Tropical) via Swiss Ephemeris |
| **Divisional Charts** | Full D1–D60 varga chart computation |
| **Dasha System** | Vimshottari Dasha with Mahadasha, Antardasha & Pratyantardasha |
| **RAG Knowledge Base** | 14,475 enriched chunks from 16 classical texts (BPHS, Phaladeepika, Saravali, Jataka Parijata, Varahmihira Horasastram, …) in ChromaDB. Canonicalised NER on 11 planets and 94 yogas across English/IAST/Devanagari. See [docs/INGESTION.md](docs/INGESTION.md), [docs/NER_CATALOGS.md](docs/NER_CATALOGS.md), [docs/EMBEDDING_STRATEGY.md](docs/EMBEDDING_STRATEGY.md). |
| **750+ Validation Rules** | JSON-configured rules that score and gate predictions |
| **LangGraph Orchestration** | Deterministic state machine routing all conversation flows |
| **Permanent Session Persistence** | Redis-backed, lifetime context with no TTL for user data |
| **Smart Cache Refresh** | Transits refresh every 24h; Dashas refresh every 30 days |
| **Multilingual Support** | English, Hindi, Tamil, Punjabi + Hinglish (Romanized) |
| **Safety Guardrails** | 3-gate LLM-based classifier (keyword → LLM vulgarity → unified LLM classification) |
| **Age-Based Validation** | Age validator gates timing predictions appropriately |
| **Progressive Disclosure UX** | Concise first answer (~100-130 words, single timing window), rich detailed follow-up |
| **Astro Evidence Payload** | Optional deterministic evidence object returned with `/message` responses |
| **Language + Script Locking** | Replies mirror user language/script (native/romanized) per turn |

---

## Technology Stack

| Layer | Technology |
|---|---|
| **API Framework** | FastAPI + Uvicorn (ASGI) |
| **Orchestration** | LangGraph state machine |
| **LLM (primary)** | Google Gemini 2.5 Pro (Vertex AI) |
| **LLM (fast)** | Google Gemini 2.5 Flash (classification, safety, follow-up) |
| **Embeddings** | Gemini Embedding 001 (Vertex AI, 1536 dims) |
| **Astro Calculations** | PySwissEph (Swiss Ephemeris) |
| **Vector Store** | ChromaDB |
| **Hybrid Retrieval** | Intent-weighted Semantic + BM25 + HyDE with cross-encoder reranking |
| **Reranking** | Sentence-Transformers cross-encoder |
| **Session Storage** | Redis (permanent, no TTL) |
| **PDF Extraction** | Gemini Vision (gemini-2.5-flash / gemini-2.5-pro fallback) |
| **Language Detection** | Langdetect (50+ languages) |
| **Containerization** | Docker + Docker Compose |

---

## Installation

### Prerequisites

- Python 3.10 or 3.11
- Redis server
- Google Cloud project with Vertex AI API enabled
- Service account credentials JSON (`google_credentials.json` in project root)

### Local Setup

```bash
# Clone repository
git clone https://github.com/mohitgrovercodes/astrology_chatbot.git
cd astrology_chatbot

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — minimum required vars:
# GOOGLE_CLOUD_PROJECT=your-gcp-project-id
# GOOGLE_APPLICATION_CREDENTIALS=google_credentials.json
# VALID_API_KEYS=your-key-here
# INTERNAL_SERVICE_SECRET=your-secret-here
# REDIS_HOST=localhost
```

### Docker Deployment

```bash
# Edit .env file first, then:
docker-compose up -d

# View logs
docker-compose logs -f api

# Health check
curl http://localhost:6262/health
```

---

## Running the Application

```bash
# Terminal 1 — Start Redis (if running locally)
redis-server

# Terminal 2 — Start FastAPI server
uvicorn src.api.main:app --host 0.0.0.0 --port 6262 --reload

# API docs available at:
# http://localhost:6262/api/docs     (Swagger UI)
# http://localhost:6262/api/redoc    (ReDoc)

# Optional: CLI interactive interface
python interactive_chatbot.py
```

---

## Latest Runtime Behavior

- Progressive disclosure: first prediction response is concise (~100-130 words, one timing window, no emoji, no disclaimer appended); second-turn affirmative responses receive richer detailed analysis.
- **Fresh question detection**: if the user sends a substantive question (4+ words, includes `?` or question-words like *kab*, *kya*, *when*, *what*) while in `AWAITING_DETAIL` phase, the bot resets to a new short-answer cycle rather than waiting for an explicit "yes/no". Users can freely pivot without saying "haan".
- Language/script mirroring: replies follow the user's detected language/script for that turn (including romanized variants).
- Validation + tone judge: semantic consistency and voice-quality checks run in a unified post-processing validator. A hard guard prevents meta-review/reviewer text from leaking into the final answer.
- **Future-only timing**: all timing windows begin after today's date; active-now windows are reframed. Windows starting within the same or next month are avoided unless the user asks for immediate timing.
- **Stale dasha defense-in-depth**: if cached `dasha_data` contains `antardasha.end` / `pratyantardasha.end` already earlier than `TODAY`, the orchestrator clears the cache to force dasha recomputation; the Step 2 prompt also suppresses month-year range text for ended dasha periods to prevent past-month leakage.
- **Horizon diversity**: INITIAL responses use a per-topic horizon-combo system (NEAR/MID/BROAD) seeded deterministically to vary between short, medium, and long windows across consecutive queries. A deterministic fallback injects distinct dasha windows if LLM rewrites still fail diversity checks.
- Configurable style guardrails: tune warmth/authenticity/repetition rewrite thresholds via `.env` without code changes.
- **Long-term preference memory**: optional `voice_preferences` on `/initialize` (detail_level, remedy_preference, tone); preferences are also inferred from messages (e.g. "keep it short", "no remedies") and injected into prompts so the bot can say "As you prefer, I'll keep this practical and short."
- Deterministic evidence support: `/message` can return an optional `evidence` object with domain, signals, and timing windows.

---

## API Integration Protocol (2-Step)

All mobile/backend integrations follow a strict two-step protocol:

**Step 1 — Initialize session (once per user):**
```bash
POST /api/v1/chat/initialize
X-API-Key: your-api-key
Content-Type: application/json

{
  "user_id": "unique-uuid",
  "user_profile": {
    "name": "Arjun Sharma",
    "date_of_birth": "1990-05-15",
    "time_of_birth": "14:30:00",
    "place_of_birth": "New Delhi, India",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "timezone": "Asia/Kolkata",
    "preferred_system": "vedic"
  },
  "conversation_history": [],
  "voice_preferences": {
    "detail_level": "brief",
    "remedy_preference": "neutral",
    "tone": "balanced"
  }
}
```
Optional `voice_preferences`: `detail_level` (brief | balanced | detailed), `remedy_preference` (include | avoid | neutral), `tone` (cautious | balanced | encouraging). Omitted keys are left unchanged. Preferences can also be inferred from messages (e.g. "keep it short").

**Step 2 — Send messages:**
```bash
POST /api/v1/chat/message
X-API-Key: your-api-key
Content-Type: application/json

{
  "user_id": "unique-uuid",
  "question": "When will my career improve?"
}
```

**Response may include deterministic evidence (optional):**
```json
{
  "user_id": "unique-uuid",
  "question": "When will my career improve?",
  "answer": "...",
  "source": "gemini",
  "evidence": {
    "domain": "career",
    "signals": [],
    "timeline_windows": [],
    "confidence_band": "medium"
  }
}
```

See [API Reference](docs/API_REFERENCE.md) for complete endpoint documentation.

---

## Project Structure

```
astro_chatbot/
├── src/
│   ├── api/              # FastAPI app, routes, middleware, schemas
│   ├── engines/
│   │   ├── vedic/        # Vedic calculation engine (D1-D60, Dasha, Yogas)
│   │   └── western/      # Western calculation engine (Houses, Aspects)
│   ├── orchestration/    # LangGraph state machine (3,100+ line orchestrator)
│   ├── rag/              # Retrieval pipeline (extraction, chunking, retrieval)
│   ├── llm/              # LLM factory (Gemini / Ollama)
│   ├── safety/           # 4-gate safety framework
│   ├── validation/       # 750+ rule validation engine
│   ├── session/          # Redis session manager
│   ├── routing/          # Semantic intent router
│   ├── utils/            # Cost tracking, logging, serializers
│   └── locales/          # EN, HI, TA, PA translations
├── config/               # Pydantic config + YAML + logger
├── docs/                 # All documentation
├── tests/                # 20 test files
├── scripts/              # Ingestion, rule extraction, utility scripts
├── examples/             # Integration examples
├── data/                 # ChromaDB vector store, SQLite, conversations
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── interactive_chatbot.py
```

---

## Testing

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test
pytest tests/test_api.py -v
pytest tests/test_safety.py -v
```

---

## Documentation

All detailed documentation lives in [`docs/`](docs/):

| Document | Description |
|---|---|
| [INDEX.md](docs/INDEX.md) | Navigation hub |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, engines |
| [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Setup, integration, extending predictions |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | Endpoint specs, auth, response formats |
