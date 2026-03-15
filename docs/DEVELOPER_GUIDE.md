# NakshatraAI — Developer & Integration Guide

> **Last Updated:** March 2026
> **For:** Backend Developers, AI Engineers, & Mobile App Integrators

---

## Quick Start (Local Setup)

1. **Clone & Install**
   ```bash
   git clone <repo-url>
   cd astro_chatbot
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   Copy `.env.example` to `.env`. Minimum required variables:
   ```env
   # LLM (required)
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...

   # API security (required)
   VALID_API_KEYS=key1,key2
   INTERNAL_SERVICE_SECRET=your-shared-secret

   # Session storage (required)
   REDIS_HOST=localhost
   REDIS_PORT=6379

   # Optional: PDF extraction via Gemini Vision
   GOOGLE_CREDENTIALS_PATH=/path/to/service-account.json
   GOOGLE_PROJECT_ID=your-project-id
   ```

3. **Initialize Storage**
   ```bash
   python scripts/init_db.py
   # Optional: seed test user
   python scripts/add_test_user.py
   # Optional: ingest astrology books into vector store
   # (Place PDFs in data/books/ first)
   python scripts/ingest_documents.py
   ```

4. **Launch Application**
   ```bash
   redis-server                                          # Terminal 1
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000  # Terminal 2
   ```

   API documentation available at:
   - Swagger UI: `http://localhost:8000/api/docs`
   - ReDoc: `http://localhost:8000/api/redoc`

---

## Docker Deployment

```bash
# Edit .env first, then:
docker-compose up -d

# Verify containers are healthy
docker-compose ps

# View API logs
docker-compose logs -f api

# Stop
docker-compose down
```

The `docker-compose.yml` spins up:
- `api` service — FastAPI on port 8000
- `redis` service — Redis 7 (Alpine) with persistent volume

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `openai` | `openai` or `ollama` |
| `LLM_MODEL` | No | `gpt-4o-mini` | LLM model name |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key (LLM + embeddings) |
| `VALID_API_KEYS` | Yes | — | Comma-separated public API keys |
| `INTERNAL_SERVICE_SECRET` | Yes | — | Backend-to-backend shared secret |
| `REDIS_HOST` | Yes | `localhost` | Redis server host |
| `REDIS_PORT` | No | `6379` | Redis server port |
| `REDIS_PASSWORD` | No | — | Redis password (if set) |
| `SESSION_EXPIRY_HOURS` | No | `0` | `0` = permanent (recommended) |
| `TRANSIT_REFRESH_HOURS` | No | `24` | How often transits are recomputed |
| `DASHA_REFRESH_DAYS` | No | `30` | How often Dashas are recomputed |
| `RATE_LIMIT_PER_MINUTE` | No | `10` | API rate limit per key |
| `MAX_CONVERSATION_HISTORY` | No | `10` | Max messages kept in context |
| `ALLOWED_ORIGINS` | No | `*` | CORS origins (restrict in production) |
| `DEBUG` | No | `false` | Enable debug logging |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |
| `COST_TRACKING_ENABLED` | No | `true` | Enable SQLite cost tracking |
| `GOOGLE_CREDENTIALS_PATH` | No | — | Service account JSON for Gemini Vision |
| `GOOGLE_PROJECT_ID` | No | — | Google Cloud project ID |

---

## Integrating the Mobile App API

The chatbot exposes two primary endpoints for mobile integration (`src/api/routes/chat_stateless.py`). Strict adherence to the 2-step protocol is required.

### Step 1 — Initialize Session (once per user)

Call this once when a user registers or enters the chat for the first time.
If a session already exists for the User ID, the server safely skips initialization without overwriting existing data.

`POST /api/v1/chat/initialize`

```json
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
  "conversation_history": []
}
```

Pass previous messages in `conversation_history` when resuming an existing conversation; pass `[]` for new sessions.

### Step 2 — Send Messages

`POST /api/v1/chat/message`

```json
{
  "user_id": "unique-uuid",
  "question": "When will my career improve?"
}
```

The `user_id` must exactly match the one used in `/initialize`. All state (chart, transits, dashas, conversation history) is handled automatically from Redis.

---

## Extending Prediction Logic (For AI Engineers)

The orchestrator (`src/orchestration/orchestrator.py`) aggregates chart data, transits, dashas, RAG text, and conversation history, then passes this context to the LLM for synthesis.

### Current Prediction Stack (Recommended Mental Model)

1. **Intent + domain inference** (LLM + deterministic guards)
2. **Deterministic astro evidence build** (`Astro Intelligence Layer`)
3. **Validation rules** (tiered, domain-aware score + critical failure analysis)
4. **Prompt assembly** (voice charter + response policy + divisional context + evidence)
5. **LLM synthesis**
6. **Post-processing validator/judge** (coherence + tone/style + consistency checks)

This is the active production flow and should be preserved when extending features.

### Adding a New Prediction Domain

To add structured deterministic reasoning for a specific topic (e.g., career, finance):

1. **Identify factors**: Extract relevant lords, houses, and divisional chart positions from engine output.
2. **Apply classical rules**: Query the validation engine or create new rules in `data/optimized/tiered_rules.json`.
3. **Weight conflicting indicators**: Consider whether active Dasha overrides natal weakness.
4. **Register in orchestrator**: Add the domain's rule tier to the validation pipeline.
5. **Synthesize**: The weighted logic gets passed alongside the RAG context to the LLM.

### Accessing Calculation Tools

Within the orchestrator, tap into calculations via:

```python
from src.tools.tools import get_calculation_tools

tools = get_calculation_tools()
chart_data = tools['vedic_birth_chart'].invoke({
    "date_of_birth": "1990-05-15",
    "time_of_birth": "14:30:00",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "timezone": "Asia/Kolkata"
})
```

### Validation Rules Format

Rules live in `data/optimized/tiered_rules.json`. Each rule:
```json
{
  "rule_id": "marriage_7th_lord_001",
  "tier": 2,
  "domain": "marriage",
  "condition": "7th_lord_debilitated",
  "weight": -15,
  "description": "7th lord in debilitation indicates delay or difficulty"
}
```

Tier 1 = critical (hard-halt on failure), Tier 2 = standard, Tier 3 = enhancement.

---

## Managing & Expanding the RAG Books

NakshatraAI processes astrology books from PDFs into the ChromaDB vector store.

### Adding New Books

1. Place PDF files in `data/books/` (or `data/raw/`)
2. Run the extraction pipeline:
   ```bash
   python src/rag/extraction/batch_extract.py
   ```
3. Ingest into ChromaDB:
   ```bash
   python scripts/ingest_documents.py
   ```

**Performance note**: The pipeline uses `gemini-2.5-flash-lite` for speed (2× faster, ~60% cheaper). Pages that fail quality validation are automatically re-processed with `gemini-2.5-pro`.

### Retrieval Configuration

Per-intent retrieval parameters are configured in `config/rag_config.py`:
- Validation queries: `top_k=15`
- Interpretation queries: `top_k=10`
- Hybrid split: BM25 30% / Semantic Vector 70%
- Score threshold: `0.7`

---

## Running Tests

```bash
# Full test suite
pytest tests/ -v

# With coverage report
pytest tests/ --cov=src --cov-report=html

# Specific test modules
pytest tests/test_api.py
pytest tests/test_safety.py
pytest tests/test_multilingual_rag.py
pytest tests/test_indian_languages.py
```

---

## Multilingual Support

The system auto-detects language from user input using `langdetect` and routes accordingly.

| Language Family | Codes | Notes |
|---|---|---|
| English | `en` | Default |
| Hindi | `hi`, `hi-lat` | Native + Romanized Hinglish |
| Tamil | `ta`, `ta-lat` | Native + Romanized Tanglish |
| Telugu | `te`, `te-lat` | Native + Romanized |
| Malayalam | `ml`, `ml-lat` | Native + Romanized |
| Marathi | `mr`, `mr-lat` | Native + Romanized |
| Punjabi | `pa`, `pa-lat` | Native + Romanized |

Translations live in `src/locales/`. Disclaimers and response templates are localized per language.

---

## Interactive CLI

For local testing without a frontend:

```bash
python interactive_chatbot.py
```

This provides a REPL-style interface that collects birth details and calls the API endpoints with color-formatted output.
