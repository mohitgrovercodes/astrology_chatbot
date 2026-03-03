# NakshatraAI — Developer & Integration Guide

> **Last Updated:** February 2026
> **For:** Backend Developers, AI Engineers, & Mobile App Integrators

---

## 🚀 Quick Start (Local Setup)

1. **Clone & Install**
   ```bash
   git clone <repo-url>
   cd astro_chatbot
   python -m venv venv
   source venv/bin/activate  # Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   Duplicate `.env.example` to `.env`. Required vars:
   ```env
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...           # Required for embeddings & LLM
   INTERNAL_SERVICE_SECRET=...     # Required for backend-to-backend auth
   VALID_API_KEYS=key1,key2        # Required for public interactions
   REDIS_HOST=localhost            # Required for memory caching
   ```

3. **Initialize Storage**
   ```bash
   python scripts/init_db.py
   python scripts/add_test_user.py
   # Note: VectorDB chunks are managed via `python scripts/ingest_documents.py`
   ```

4. **Launch Application**
   ```bash
   redis-server                      # Terminal 1
   uvicorn src.api.main:app --reload # Terminal 2
   ```

---

## 🔌 Integrating the Mobile App API

The chatbot exposes two endpoints exclusively for the mobile app connection (`src/api/routes/chat_stateless.py`). Strict adherence to the 2-step protocol is required.

### 1. The `/initialize` Endpoint (One-Time Only)
Call this once when the user registers or enters the chat interface for the first time. 
*Note: If a session already exists for the User ID, the server safely aborts modifications to avoid overwriting existing chat context.*

`POST /api/v1/chat/initialize`
```json
{
  "user_id": "unique-uuid",
  "user_profile": {
    "name": "Jane Doe",
    "date_of_birth": "1990-05-15",
    "time_of_birth": "14:30:00",
    "place_of_birth": "London, UK",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "timezone": "Europe/London",
    "preferred_system": "vedic"
  },
  "conversation_history": []
}
```

### 2. The `/message` Endpoint
Submit actual user questions. State, context, transits, charts, and dashas are handled natively within Redis by the application state manager.

`POST /api/v1/chat/message`
```json
{
  "user_id": "unique-uuid",
  "question": "When will my career improve?"
}
```

---

## 🛠 Extending Prediction Logic (For AI Engineers)

Currently, the AI utilizes `src/orchestration/orchestrator.py` to aggregate Data (Chart, Transits, Dasha, RAG texts) and pass it directly to the LLM. 

### Mission Directive: 
Future Prediction integrations should introduce structured deterministic reasoning instead of LLM black-box synthesis.

**Example Structure to implement (`MarriagePredictionEngine`):**
1. **Identify Factors**: Extract 7th lord, 7th house, D9 chart status from Vedic engine output.
2. **Apply Classical Rules**: If 7th lord is debilitated, queue a delay indication.
3. **Weight Conflicting rules**: Is the Dasha overriding the debilitation?
4. **Synthesize**: Pass the weighted logic alongside the generated context to the LLM.

### Available Tools:
Within the orchestrator, you can tap into calculations via:
```python
from src.tools.tools import get_calculation_tools
tools = get_calculation_tools()
chart_data = tools['vedic_birth_chart'].invoke({"date_of_birth": "1990-05-15", ...})
```

---

## 📖 Managing & Expanding the RAG Books

NakshatraAI natively processes Astro-Books directly from PDFs to ChromaDB vectors.

### Generating PDF Chunks
We use a high-performance multithreaded Gemini Vision architecture to read tables and prose efficiently.
```bash
# Process PDFs (Ensure `data/books/` has PDFs attached)
python src/rag/extraction/batch_extract.py
```
> **Performance Tip**: Our `ExtractionConfig` prefers `gemini-2.5-flash-lite` due to its 2X speed advantage reducing costs by 60%. If a page fails quality validation, it auto-upgrades to `gemini-2.5-pro`.

---

## 💰 Cost Tracking system

NakshatraAI utilizes an auto-logging SQLite database to trace expenses for embeddings and tokens. 
- Integrated transparently into LLM workflows (`CostTrackingWrapper`).
- Generates automatic daily rollups.

**Generate Cost Reports:**
```bash
# Show today's costs
python -m src.utils.cost_report --today

# Breakdown for specific model over a week
python -m src.utils.cost_report --week --model gemini-2.5-flash

# Export metrics
python -m src.utils.cost_report --month --export january_costs.csv
```
