# NakshatraAI — Quick Start Guide

> **Version:** 2.0  
> **Last Updated:** February 20, 2026  
> **Time to Setup:** 15 minutes

---

## 🚀 Quick Start (5 Steps)

### Step 1: Clone & Install (2 minutes)

```bash
# Clone repository
git clone <repo-url>
cd astro_chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment (2 minutes)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required variables:**
```bash
# Google Vertex AI (Primary LLM)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GOOGLE_CLOUD_PROJECT=your-project-id

# OpenAI (For embeddings)
OPENAI_API_KEY=your_openai_api_key

# Redis (Optional but recommended)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Step 3: Initialize Database (2 minutes)

```bash
# Create database and schema
python scripts/init_db.py

# Add test users
python scripts/add_test_user.py

# Verify database
sqlite3 data/astro.db "SELECT user_id, name FROM users;"
```

**Expected output:**
```
user001|Arjun Kumar
user002|Priya Sharma
user003|Sophia Anderson
```

### Step 4: Setup Vector Store (5 minutes)

```bash
# Run document ingestion (one-time)
python scripts/ingest_documents.py

# This will:
# - Extract text from PDFs in data/books/
# - Generate embeddings (OpenAI)
# - Store in ChromaDB (data/vectordb/)
# - Takes ~5 minutes for 14,508 chunks
```

**Expected output:**
```
[EXTRACTION] Processing 15 PDF files...
[CHUNKING] Generated 14,508 chunks
[EMBEDDING] Creating embeddings...
[VECTORDB] Storing in ChromaDB...
✅ Ingestion complete: 14,508 documents
```

### Step 5: Start Redis & Run (2 minutes)

```bash
# Start Redis (optional but recommended)
redis-server

# In another terminal, run chatbot
python chatbot.py

# OR start API server
uvicorn src.api.main:app --reload --port 8000
```

**Done! 🎉**

---

## 💬 First Conversation

### CLI Chatbot

```bash
$ python chatbot.py

Enter user_id: user002

✨ Namaste, Priya Sharma!

I'm NakshatraAI, your professional Vedic astrology consultant.
...

🔮 You: Hello
✨ NakshatraAI: Hello! I'm NakshatraAI, your professional astrology consultant...

🔮 You: When will I get married?
✨ NakshatraAI: Based on your chart, Jupiter's transit through your 7th house 
in March-April 2026 indicates a favorable period for marriage. Your current 
Saturn/Rahu dasha also supports relationship commitments...

[Intent: RAG_WITH_CALCULATION, Time: 2.3s]
```

### API Server

```bash
$ uvicorn src.api.main:app --reload

# In another terminal:
curl -X POST "http://localhost:8000/api/v1/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "When will I get married?",
    "user_id": "user002"
  }'
```

**Response:**
```json
{
  "answer": "Based on your chart, Jupiter's transit...",
  "intent": "RAG_WITH_CALCULATION",
  "confidence": 0.98,
  "processing_time": 2.3,
  "metadata": {
    "validation_passed": true,
    "validation_strength": 10.0
  }
}
```

---

## 🔧 Configuration Options

### LLM Provider Selection

```bash
# Use Google (default, recommended)
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash

# Use OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo

# Use local Ollama
LLM_PROVIDER=ollama
LLM_MODEL=llama2
```

### Performance Tuning

```bash
# Enable Redis for 85% performance improvement
REDIS_HOST=localhost
REDIS_PORT=6379

# Adjust token limits (in factory.py)
purpose_token_map = {
    "classification": 1024,  # Fast classification
    "chitchat": 512,         # Brief responses
    "general": 2048,         # Standard
    "prediction": 3072,      # Detailed predictions
    "rag": 3072,             # Knowledge-heavy
    "validation": 4096,      # Batch validation
}
```

### Validation Engine

```bash
# Enable/disable validation
VALIDATION_ENABLED=true

# Validation timeout
VALIDATION_TIMEOUT=30

# Batch size
VALIDATION_BATCH_SIZE=15
```

---

## 📂 Project Structure

```
astro_chatbot/
├── chatbot.py                 # CLI interface (UPDATED)
├── src/
│   ├── ai/
│   │   ├── intent_classifier.py
│   │   ├── persona_generator.py
│   │   └── user_manager.py
│   ├── engines/
│   │   ├── vedic/            # 8 files
│   │   ├── western/          # 7 files
│   │   └── core/             # 6 files
│   ├── orchestration/
│   │   └── orchestrator.py   # LangGraph (UPDATED)
│   ├── safety/
│   │   ├── classifier.py     # Multi-gate (UPDATED)
│   │   ├── templates.py      # Response templates (UPDATED)
│   │   └── models.py         # Data models (UPDATED)
│   ├── llm/
│   │   └── factory.py        # Token allocation (UPDATED)
│   ├── rag/
│   │   ├── rag_engine.py
│   │   └── retriever.py
│   ├── validation/
│   │   └── vedic_validation_engine_v2.py
│   ├── cache/
│   │   └── redis_manager.py  # NEW
│   └── api/
│       └── main.py
├── data/
│   ├── astro.db              # SQLite
│   ├── vectordb/             # ChromaDB
│   └── books/                # PDFs
├── validation_rules/         # 750+ rules
└── scripts/
    ├── init_db.py
    ├── add_test_user.py
    └── ingest_documents.py
```

---

## ✅ Verification Checklist

After setup, verify everything works:

```bash
# 1. Check database
sqlite3 data/astro.db "SELECT COUNT(*) FROM users;"
# Expected: 3 (or more)

# 2. Check vector store
python -c "from langchain_chroma import Chroma; \
           from langchain_openai import OpenAIEmbeddings; \
           vs = Chroma(collection_name='vedic_astrology_books_knowledge', \
                      embedding_function=OpenAIEmbeddings(), \
                      persist_directory='./data/vectordb'); \
           print(f'Documents: {vs._collection.count()}')"
# Expected: Documents: 14508

# 3. Check Redis (if enabled)
redis-cli PING
# Expected: PONG

# 4. Test chatbot
echo "hello" | python chatbot.py --user user002
# Should return greeting without errors

# 5. Test API
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

---

## 🐛 Troubleshooting

### Issue: "No module named 'google.cloud'"

**Solution:**
```bash
pip install google-cloud-aiplatform
pip install google-auth
```

### Issue: "OpenAI API key not found"

**Solution:**
```bash
# Add to .env
OPENAI_API_KEY=sk-...your_key...
```

### Issue: "ChromaDB collection not found"

**Solution:**
```bash
# Re-run ingestion
python scripts/ingest_documents.py
```

### Issue: "Redis connection refused"

**Solution:**
```bash
# Start Redis
redis-server

# OR disable Redis (slower)
# In orchestrator.py, set:
redis_manager = None
```

### Issue: "Swiss Ephemeris files missing"

**Solution:**
```bash
# Download ephemeris files
python -c "import swisseph; print(swisseph.__file__)"
# Copy ephemeris files to that directory
```

### Issue: "User not found"

**Solution:**
```bash
# Add test user
python scripts/add_test_user.py

# OR use default test users
# user001, user002, user003
```

---

## 🚀 Next Steps

1. **Test Different Query Types:**
   ```
   - "Hello" (chitchat)
   - "What is my sun sign?" (calculation only)
   - "When will I get married?" (prediction with validation)
   - "What is a nakshatra?" (knowledge only)
   ```

2. **Check Performance:**
   ```bash
   # Without Redis: 15-20s per turn
   # With Redis: 2-3s per turn
   ```

3. **Explore API:**
   ```bash
   # Open API docs
   http://localhost:8000/docs
   ```

4. **Review Logs:**
   ```bash
   # Check what's happening under the hood
   tail -f logs/nakshatraai.log
   ```

5. **Customize:**
   - Add your own users (scripts/add_test_user.py)
   - Upload your own astrological texts (data/books/)
   - Modify personas (src/ai/personas.py)
   - Adjust safety rules (src/safety/classifier.py)

---

## 📚 Documentation

- **Full Documentation:** `PROJECT_DOCUMENTATION_V2.md`
- **Architecture:** `ARCHITECTURE_V2.md`
- **API Reference:** `http://localhost:8000/docs` (when running)
- **Fix History:** `/mnt/user-data/outputs/*FIX*.md`

---

## 🎯 Quick Commands

```bash
# Start chatbot
python chatbot.py

# Start API
uvicorn src.api.main:app --reload --port 8000

# Start Redis
redis-server

# Check health
curl http://localhost:8000/health

# Run tests
pytest tests/

# Clear Redis cache
redis-cli FLUSHDB

# View logs
tail -f logs/nakshatraai.log

# Check system status
python scripts/system_health_check.py
```

---

## 💡 Pro Tips

1. **Always start Redis** for best performance (85% faster)
2. **Use user002** for testing (complete birth data)
3. **Check logs** if queries fail - they show the exact flow
4. **Enable validation** for production use (VALIDATION_ENABLED=true)
5. **Monitor Redis** - use `redis-cli INFO` to check cache hits

---

## 🎉 You're Ready!

Your NakshatraAI system is now set up and running!

**Questions?** Check the full documentation or review the fix history in `/mnt/user-data/outputs/`.

**Happy Chatting!** 🌟
