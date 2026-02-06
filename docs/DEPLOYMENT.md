# 🚀 Deployment Guide

This guide outlines the steps to deploy the Astrology AI Chatbot.

---

## 🏗️ Deployment Checklist

- [ ] **Tests Pass**: `python test_routing.py` yields >90% accuracy.
- [ ] **Credentials**: Service account JSON is present in `credentials/`.
- [ ] **Environment**: `.env` file is configured with API keys.
- [ ] **Data**: `data/vectordb` is populated.

---

## ⚡ Quick Deployment (Local/VM)

### 1. Update Tools & Engines
Ensure your latest calculation tools are in place:

```bash
# Windows
copy src\tools\calculation_tools.py src\tools\calculation_tools.py.bak
# Linux
cp src/tools/calculation_tools.py src/tools/calculation_tools.py.bak
```

### 2. Verify Orchestrator
Check that `src/orchestration/orchestrator.py` is the latest version integrated with `SemanticRouter`.

```bash
python test_semantic_routing.py
# Should pass 8/8 tests.
```

### 3. Start the Chatbot
Run the main interface:

```bash
python chatbot_phase5_1.py
```

---

## 🐳 Docker Deployment (Planned Phase 12)

(Coming Soon)

1. Build Image:
   ```bash
   docker build -t astro-chatbot .
   ```
2. Run Container:
   ```bash
   docker run -p 8000:8000 --env-file .env astro-chatbot
   ```

---

## 🌐 API Deployment (FastAPI)

To run the API server (once Phase 12 is complete):

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Health Check**:
GET `http://localhost:8000/health`
