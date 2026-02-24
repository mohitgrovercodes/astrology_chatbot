<!-- docs\DEVELOPER_GUIDE.md -->
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
python src/tools/tools.py

# Test Safety Classifier
# (integration via chatbot.py)
```

**Expected Results**:
- Routing accuracy > 90%
- Calculations must match Swiss Ephemeris ref values.

---

## 5. Deployment

### Docker Deployment (Recommended)

**Quick Start:**
```bash
# 1. Build and start services
docker-compose up -d

# 2. Verify deployment
docker-compose ps

# 3. Check logs
docker-compose logs -f api

# 4. Test health endpoint
curl http://localhost:8000/api/v1/health
```

**Service Architecture:**
```yaml
services:
  api:          # FastAPI application (port 8000)
  redis:        # Session storage (port 6379)
```

**Docker Commands:**
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart specific service
docker-compose restart api

# View logs
docker-compose logs -f api

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

### Production Deployment

**Pre-Deployment Checklist:**
- [ ] Environment variables configured
- [ ] Secrets generated and secured
- [ ] Database connection tested
- [ ] Redis connection tested
- [ ] SSL certificates obtained (if applicable)
- [ ] Firewall rules configured

**Environment Variables (Production):**
```env
# API Configuration
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Security
INTERNAL_SERVICE_SECRET=<64-char-random-string>
VALID_API_KEYS=<comma-separated-keys>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<strong-password>

# LLM
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
```

**Generate Secrets:**
```bash
# Generate strong secrets
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 6. Localization & Language Support

**Supported Languages (Fixed List):**
- English (`en`), Hindi (`hi`), Marathi (`mr`), Punjabi (`pa`), Tamil (`ta`), Telugu (`te`), Malayalam (`ml`).

**Adding/Editing Content:**
- Edit the **Base JSON** only (e.g., `src/locales/mr.json`).
- **DO NOT** create `mr-lat.json`. The system automatically reuses `mr.json` for Roman script inputs.

---

## 7. Troubleshooting

**Issue**: `ImportError: cannot import name 'VedicEngine'`
**Fix**: Ensure `PYTHONPATH` includes project root or run from root using `python -m src...`.

**Issue**: `UnicodeEncodeError` on Windows Console
**Fix**: `chcp 65001` to enable UTF-8 or use an IDE terminal like VS Code.

**Issue**: Redis Connection Failed
**Fix**:
```bash
# Check Redis status
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# Restart Redis
docker-compose restart redis
```

**Issue**: Port Already in Use
**Fix**:
```bash
# Find process using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Linux/Mac

# Kill process or change port in .env
PORT=8001
```

---

## 📚 Additional Resources

**Documentation:**
- [CURRENT_IMPLEMENTATION.md](CURRENT_IMPLEMENTATION.md) - Complete system state
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Handoff guide for new developers
- [API_REFERENCE.md](API_REFERENCE.md) - API documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design

**For Deployment:**
- See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for detailed deployment instructions
- Docker Compose configuration in `docker-compose.yml`
- Environment template in `.env.example`

---

**Developer Guide Version:** 2.0  
**Last Updated:** February 11, 2026
