# 🛠️ Developer Guide

**Welcome to the Astrology AI Checkbot Project!**

This guide covers the setup, development workflow, and testing procedures for the project.

---

## 1. Environment Setup

### Prerequisites
- Python 3.10+
- `pip`
- Google Cloud Project (for Vertex AI) OR OpenAI API Key

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd astro-chatbot

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt
```

### Configuration (.env)

Copy `.env.example` to `.env` and configure your keys:

```ini
# LLM Provider (google or openai)
DEFAULT_LLM_PROVIDER=google
DEFAULT_LLM_MODEL=gemini-2.5-flash

# Google Vertex AI Credentials
GOOGLE_APPLICATION_CREDENTIALS=credentials/video-translate-key.json
GOOGLE_CLOUD_PROJECT=nakshatraai-447814
GOOGLE_LOCATION=us-central1

# Or OpenAI
OPENAI_API_KEY=sk-...

# Vector DB
CHROMA_PERSIST_DIRECTORY=./data/vectordb
```

---

## 2. Google Cloud Setup (If using Vertex AI)

1.  **Create Service Account**:
    - Go to IAM & Admin > Service Accounts.
    - Create new account with **Vertex AI User** role.
    - Create JSON Key and save to `credentials/google-credentials.json`.
2.  **Enable APIs**:
    - Enable "Vertex AI API" in Cloud Console.

---

## 3. Development Workflow

### Project Structure
- `src/` - Source code
    - `engines/` - Deterministic calculation engines (Vedic/Western).
    - `routing/` - Semantic Router (AI Intent).
    - `orchestration/` - LangGraph workflow.
    - `safety/` - Classifier & Constitution.
- `docs/` - Documentation.
- `data/` - Local datastores (VectorDB, Profiles).

### Running Locally

**Interactive CLI Mode**:
```bash
python chatbot_phase5_1.py
```

**Run Semantic Router Test**:
```bash
python test_semantic_routing.py
# (Note: Requires sentence-transformers model download on first run)
```

---

## 4. Testing

### Core Test Suite
Run the comprehensive test suite to verify system integrity:

```bash
# Test Routing Logic
python test_routing.py

# Test Calculation Engines
python src/tools/calculation_tools.py

# Test Safety Classifier
# (integration via chatbot.py)
```

**Expected Results**:
- Routing accuracy > 90%
- Calculations must match Swiss Ephemeris ref values.

---

## 5. Troubleshooting

**Issue**: `ImportError: cannot import name 'VedicEngine'`
**Fix**: Ensure `PYTHONPATH` includes project root or run from root using `python -m src...`.

**Issue**: `UnicodeEncodeError` on Windows Console
**Fix**: `chcp 65001` to enable UTF-8 or use an IDE terminal like VS Code.
