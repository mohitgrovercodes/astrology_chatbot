# 🤝 Developer Handoff Document

**Project:** NakshatraAI - Production Astrology AI System  
**Date:** February 9, 2026  
**Phase:** 12 Complete - Production Ready  
**From:** Development Team  
**To:** Next Developer / Operations Team

---

## 🎯 Executive Summary

NakshatraAI is a **production-grade AI astrology chatbot** featuring semantic routing, multilingual support, and enterprise backend integration. The system is containerized, fully documented, and ready for deployment with Redis-based session management and secure API authentication.

**Current State:** ✅ All core features complete, tested, and documented.  
**Next Step:** Deploy to staging environment for final validation.

---

## 🚨 Critical Information

### 1. Backend Integration Architecture

The system now operates as a **backend service** for a mobile application:

```
Mobile App → HTTPS + X-Internal-Service Header → FastAPI → Redis + ChromaDB
```

**Key Points:**
- **Authentication**: Uses `X-Internal-Service` header with shared secret
- **Session Management**: Redis stores conversation history (24h expiry, 20 msg limit)
- **Response Format**: Strict JSON contract with sources and metadata
- **Graceful Degradation**: Works without Redis (session management disabled)

**Files to Know:**
- `src/api/routes/chat.py` - Integration endpoint
- `src/db/redis_client.py` - Session management
- `src/api/middleware/auth.py` - Authentication logic

### 2. Environment Configuration

**Critical Variables** (must be set):
```env
OPENAI_API_KEY=sk-...                    # LLM provider
INTERNAL_SERVICE_SECRET=...              # Backend auth
VALID_API_KEYS=key1,key2                 # Public API auth
```

**Optional but Recommended:**
```env
REDIS_HOST=localhost                     # Session storage
REDIS_PORT=6379
MONGODB_URI=mongodb://...                # User profiles
```

**Template:** Use `.env.example` as starting point.

### 3. LLM Provider Configuration

The system supports **three LLM providers**:

| Provider | Configuration | Use Case |
|----------|---------------|----------|
| **OpenAI** (Default) | `LLM_PROVIDER=openai`<br>`LLM_MODEL=gpt-4o-mini` | Production (recommended) |
| **Google Gemini** | `LLM_PROVIDER=google`<br>`GOOGLE_CREDENTIALS_PATH=...` | Alternative cloud |
| **Ollama** | `LLM_PROVIDER=ollama`<br>`OLLAMA_BASE_URL=...` | Local development |

**Switching Providers:**
```bash
# Use the switch_llm.py utility
python switch_llm.py --provider openai --model gpt-4o-mini
```

### 4. Semantic Router & Embeddings

**⚠️ First-Run Behavior:**
- Downloads `all-MiniLM-L6-v2` model (~80MB) on first startup
- Cached in `~/.cache/torch/sentence_transformers/`
- Startup time: ~3s (lazy loading)

**Threshold Configuration:**
```python
# src/routing/semantic_router.py
CHITCHAT_THRESHOLD = 0.70  # Don't lower without testing
SAFETY_THRESHOLD = 0.75    # NEVER lower this
```

**Testing:**
```bash
# Verify routing works
python chatbot.py
> "wassup"  # Should route to Chitchat
> "calculate my chart"  # Should route to Vedic Engine
```

---

## 🏗️ System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         LangGraph Orchestrator (State Machine)       │   │
│  │                                                        │   │
│  │  1. Authenticate → 2. Safety → 3. Intent → 4. Execute │   │
│  │                                                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │ Vedic    │  │ Western  │  │ RAG      │           │   │
│  │  │ Engine   │  │ Engine   │  │ Engine   │           │   │
│  │  └──────────┘  └──────────┘  └──────────┘           │   │
│  │                                                        │   │
│  │  5. Critic (Constitutional AI) → 6. Response          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌─────────┐          ┌─────────┐         ┌─────────┐
   │ Redis   │          │ChromaDB │         │ MongoDB │
   │Sessions │          │ RAG KB  │         │ Users   │
   └─────────┘          └─────────┘         └─────────┘
```

### Request Flow

1. **Request Arrives** → API validates `X-Internal-Service` header
2. **Session Loaded** → Redis retrieves conversation history
3. **Orchestrator Invoked** → LangGraph processes query through nodes
4. **Response Generated** → Includes answer, sources, metadata
5. **Session Updated** → Redis stores new message

---

## 🚀 Deployment Instructions

### Option 1: Docker Compose (Recommended)

```bash
# 1. Configure environment
cp .env.example .env
vim .env  # Add your API keys

# 2. Start all services
docker-compose up -d

# 3. Verify health
curl http://localhost:8000/api/v1/health

# 4. View logs
docker-compose logs -f api

# 5. Stop services
docker-compose down
```

**Services Started:**
- `nakshatraai-api` (port 8000)
- `nakshatraai-redis` (port 6379)

### Option 2: Local Development

```bash
# 1. Activate virtual environment
conda activate astro_chatbot  # or: source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Redis (separate terminal)
redis-server

# 4. Start API server
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Verification Steps

```bash
# 1. Health check
curl http://localhost:8000/api/v1/health

# 2. API documentation
open http://localhost:8000/api/docs

# 3. Test chat endpoint (requires auth)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-Internal-Service: your-secret-here" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is my sun sign?",
    "session_id": "test-session-123",
    "user_context": {
      "birth_date": "1990-05-15",
      "birth_time": "14:30:00",
      "latitude": 28.6139,
      "longitude": 77.2090,
      "timezone": "Asia/Kolkata",
      "astrology_system": "vedic"
    }
  }'
```

---

## 🧪 Testing

### Automated Tests

```bash
# Run all tests
pytest tests/

# Run specific test suites
pytest tests/test_backend_integration.py  # Backend integration
pytest tests/test_api.py                  # API endpoints
pytest tests/test_safety.py               # Safety framework
```

### Manual Testing Scenarios

**1. Session Persistence**
```bash
# First message
curl -X POST ... -d '{"message": "My name is John", "session_id": "test-1", ...}'
# Response: "Hello John..."

# Second message (same session)
curl -X POST ... -d '{"message": "What is my name?", "session_id": "test-1", ...}'
# Response: "Your name is John..." ✅ Remembers context
```

**2. Safety Guardrails**
```bash
# Hard block
curl ... -d '{"message": "When will I die?", ...}'
# Response: Polite refusal

# Reframe
curl ... -d '{"message": "Will I be rich?", ...}'
# Response: Reframed to "wealth potential"
```

**3. Multilingual**
```bash
# Hinglish query
curl ... -d '{"message": "Mera sun sign kya hai?", ...}'
# Response: Romanized Hindi
```

---

## 📁 File Structure Reference

### Critical Directories

```
astro_chatbot/
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── main.py            # Entry point
│   │   ├── config.py          # Settings (IMPORTANT)
│   │   ├── routes/chat.py     # Integration endpoint
│   │   └── middleware/auth.py # Authentication
│   │
│   ├── orchestration/
│   │   └── orchestrator.py    # LangGraph workflow
│   │
│   ├── engines/
│   │   ├── vedic/             # Vedic calculations
│   │   └── western/           # Western calculations
│   │
│   ├── rag/
│   │   └── rag_engine.py      # RAG pipeline
│   │
│   ├── safety/
│   │   ├── safety_classifier.py
│   │   └── constitution.py
│   │
│   ├── routing/
│   │   └── semantic_router.py # Intent classification
│   │
│   └── db/
│       ├── redis_client.py    # Session management
│       └── sqlite_client.py   # User profiles
│
├── tests/                      # Test suites
├── data/
│   └── vectordb/              # ChromaDB storage
├── docs/                       # Documentation
├── .env                        # Configuration (DO NOT COMMIT)
├── .env.example               # Template
├── requirements.txt           # Dependencies
├── docker-compose.yml         # Orchestration
└── Dockerfile                 # Container definition
```

### Key Configuration Files

| File | Purpose | Notes |
|------|---------|-------|
| `.env` | Environment variables | **Never commit** |
| `src/api/config.py` | Settings validation | Uses Pydantic |
| `config/config.yaml` | Orchestrator config | LangGraph settings |
| `docker-compose.yml` | Service orchestration | Redis + API |

---

## ⚠️ Common Issues & Solutions

### 1. Redis Connection Error

**Symptom:**
```
[REDIS] WARNING: Could not connect to Redis at localhost:6379
```

**Solution:**
```bash
# Check if Redis is running
redis-cli ping  # Should return "PONG"

# If not running:
redis-server    # Linux/Mac
# or
docker run -d -p 6379:6379 redis:7-alpine  # Docker
```

**Note:** API works without Redis (session management disabled).

### 2. Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
```bash
# Ensure venv is activated
conda activate astro_chatbot

# Reinstall dependencies
pip install -r requirements.txt
```

### 3. LLM API Errors

**Symptom:**
```
openai.error.AuthenticationError: Incorrect API key
```

**Solution:**
```bash
# Verify .env file
cat .env | grep OPENAI_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### 4. Pydantic Validation Errors

**Symptom:**
```
pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted
```

**Solution:**
- Check `.env` for typos in variable names
- Compare with `.env.example`
- Ensure all variables in `.env` are defined in `src/api/config.py`

---

## 🔒 Security Considerations

### 1. API Keys & Secrets

**DO:**
- ✅ Store in `.env` file (gitignored)
- ✅ Use strong, random secrets (min 32 characters)
- ✅ Rotate keys periodically
- ✅ Use different keys for dev/staging/prod

**DON'T:**
- ❌ Commit `.env` to git
- ❌ Hardcode secrets in code
- ❌ Share keys in chat/email
- ❌ Use weak secrets like "password123"

### 2. Rate Limiting

**Current Settings:**
- 10 requests/minute per API key
- Configurable via `RATE_LIMIT_PER_MINUTE`

**Adjust for Production:**
```env
RATE_LIMIT_PER_MINUTE=100  # Higher for production
```

### 3. CORS Configuration

**Current:** `ALLOWED_ORIGINS=*` (permissive for development)

**Production:**
```env
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

---

## 📊 Monitoring & Observability

### Logs

**Location:** `logs/` directory

**Key Log Files:**
- `api.log` - API requests/responses
- `orchestrator.log` - Workflow execution
- `errors.log` - Error traces

**Log Levels:**
```env
DEBUG=false  # Production
DEBUG=true   # Development (verbose logging)
```

### Health Checks

**Endpoint:** `GET /api/v1/health`

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-02-09T10:30:00Z"
}
```

**Docker Health Check:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## 📚 Documentation Index

| Document | Purpose | Location |
|----------|---------|----------|
| **API Reference** | Complete API documentation | `docs/API_REFERENCE.md` |
| **Quick Start** | Setup & deployment guide | `QUICKSTART.md` |
| **Architecture** | System design overview | `docs/ARCHITECTURE.md` |
| **Project Status** | Current state & roadmap | `docs/project_status_master.md` |
| **Deployment** | Production deployment | `docs/DEPLOYMENT.md` |
| **Walkthrough** | Implementation details | `walkthrough.md` (artifacts) |

---

## 🎯 Immediate Next Steps

### For Deployment Team

1. **Staging Deployment**
   ```bash
   # Deploy to staging environment
   docker-compose -f docker-compose.staging.yml up -d
   ```

2. **Smoke Testing**
   - Run `tests/test_backend_integration.py`
   - Verify all endpoints via Swagger UI
   - Test session persistence with real Redis

3. **Performance Testing**
   - Load test with 50 concurrent users
   - Monitor response times
   - Check Redis memory usage

### For Development Team

1. **Optional Enhancements**
   - Add Prometheus metrics
   - Implement structured logging
   - Set up error tracking (Sentry)

2. **Fine-Tuning** (if desired)
   - Collect conversation logs
   - Create training dataset
   - Fine-tune model for persona

---

## 🆘 Support Contacts

**Technical Questions:**
- Review `docs/` directory
- Check `walkthrough.md` in artifacts
- Consult API docs at `/api/docs`

**Critical Issues:**
- Check logs in `logs/` directory
- Review error traces
- Verify environment configuration

---

## ✅ Handoff Checklist

- [x] All code committed to repository
- [x] `.env.example` template created
- [x] Documentation updated
- [x] Tests passing
- [x] Docker images built
- [x] Redis integration verified
- [x] API authentication tested
- [x] Session management validated
- [ ] Staging deployment (Next step)
- [ ] Production deployment (After staging validation)

---

**Status:** ✅ **READY FOR DEPLOYMENT**

**Recommendation:** Deploy to staging environment for 48-hour validation period before production release.

**Good luck! 🚀**
