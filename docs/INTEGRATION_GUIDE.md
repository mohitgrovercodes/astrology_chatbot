<!-- docs\INTEGRATION_GUIDE.md -->
# Integration Guide for New AI Assistant

**Purpose:** Handoff documentation for new AI assistant to understand and enhance prediction logic  
**Audience:** New AI assistant working on prediction enhancement  
**Last Updated:** February 11, 2026

---

## 🎯 Your Mission

You are being brought in to enhance the **prediction logic** of the NakshatraAI astrology chatbot. The system currently has:
- ✅ Accurate calculation engines (Vedic + Western)
- ✅ Comprehensive RAG pipeline
- ✅ Robust safety framework
- ✅ Production-ready API

**What's Missing:** Sophisticated logic to synthesize multiple astrological factors into accurate, well-reasoned predictions.

---

## � Critical Configuration (Must Know)

### Backend Integration Architecture

The system operates as a **backend service** for a mobile application:

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

### Multilingual Constraints (CRITICAL)

**Strict 8-Language Lockdown:**
The system **ONLY** supports: `en`, `hi`, `mr`, `pa`, `ta`, `te`, `ml`.
- **Roman Script**: Supported for all 6 Indian languages via `-lat` suffix (e.g., `mr-lat`)
- **File Structure**: **DO NOT create `*-lat.json` files.** The system alias checks `mr-lat` → `mr.json`
- **Drift Prevention**: RAG queries are filtered by language. English queries will **NEVER** see Marathi chunks

### Environment Configuration

**Critical Variables** (must be set):
```env
OPENAI_API_KEY=sk-...                    # LLM provider
INTERNAL_SERVICE_SECRET=...              # Backend auth (64-char random)
VALID_API_KEYS=key1,key2                 # Public API auth
```

**Optional but Recommended:**
```env
REDIS_HOST=localhost                     # Session storage
REDIS_PORT=6379
MONGODB_URI=mongodb://...                # User profiles
DEBUG=false                              # Production mode
```

**Template:** Use `.env.example` as starting point.

### LLM Provider Configuration

The system supports **three LLM providers**:

| Provider | Configuration | Use Case |
|----------|---------------|----------|
| **OpenAI** (Default) | `LLM_PROVIDER=openai`<br>`LLM_MODEL=gpt-4o-mini` | Production (recommended) |
| **Google Gemini** | `LLM_PROVIDER=google`<br>`GOOGLE_CREDENTIALS_PATH=...` | Alternative cloud |
| **Ollama** | `LLM_PROVIDER=ollama`<br>`OLLAMA_BASE_URL=...` | Local development |

**Switching Providers:**
```bash
# Update .env file
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

### Semantic Router & Embeddings

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

---



## �📚 Essential Reading (Priority Order)

### 1. Start Here
1. **`docs/CURRENT_IMPLEMENTATION.md`** - Current state, gaps, and limitations
2. **`docs/CALCULATION_ENGINES.md`** - What calculations are available
3. **`docs/RAG_PIPELINE_DETAILED.md`** - How knowledge retrieval works

### 2. Understand the Architecture
1. **`docs/ARCHITECTURE.md`** - System design overview
2. **`src/orchestration/orchestrator.py`** (lines 1-200) - Main workflow
3. **`src/tools/tools.py`** - Available calculation tools

### 3. Deep Dive (As Needed)
1. **`src/engines/vedic/vedic_engine.py`** - Vedic calculation details
2. **`src/rag/rag_engine.py`** - RAG orchestration
3. **`src/safety/README.md`** - Safety constraints

---

## 🔍 Current System Flow

### How a Prediction Query is Handled Now

```
1. User Query: "When will I get married?"
   ↓
2. Safety Check: SAFE (no blocks)
   ↓
3. Intent Classification: NEEDS_RAG (requires knowledge + calculation)
   ↓
4. Orchestrator: handle_rag_with_calculation_node
   ↓
5. Calculate birth chart:
   - Lagna: Aries
   - Moon: Cancer
   - 7th house: Libra (Venus rules)
   - 7th lord (Venus): in 10th house
   ↓
6. Calculate current dasha:
   - Mahadasha: Venus (2024-2044)
   - Antardasha: Moon (2025-2027)
   - Pratyantardasha: Jupiter (Feb-Jun 2026)
   ↓
7. Calculate transits:
   - Jupiter: Taurus (transiting 2nd house)
   - Saturn: Pisces (transiting 12th house)
   ↓
8. Retrieve knowledge from RAG:
   - "Venus in 10th house indicates delayed marriage"
   - "7th lord in 10th brings career-focused spouse"
   - "Venus-Moon dasha favorable for marriage"
   ↓
9. Build prompt:
   System: You are a Vedic astrologer
   Context: [Chart + Dasha + Transits + Retrieved texts]
   Query: When will I get married?
   ↓
10. LLM generates response (BLACK BOX):
    "Based on your chart, marriage is likely during..."
```

**The Problem:** Step 10 is a black box. The LLM makes predictions without systematic application of astrological rules.

---

## ❌ What's Missing (Your Task)

### The Gap: Structured Prediction Logic

The system needs a **PredictionEngine** that:

1. **Identifies Relevant Factors**
   - Which houses matter for this query?
   - Which planets are significators?
   - Which divisional charts should be checked?

2. **Applies Classical Rules**
   - 7th lord position rules
   - Dasha timing rules
   - Transit activation rules
   - Yoga activation rules

3. **Weighs Conflicting Indications**
   - One factor says "yes", another says "no"
   - How to resolve contradictions?
   - Which factor is most important?

4. **Estimates Timing**
   - When is the event most likely?
   - What is the confidence level?
   - What are the time windows?

5. **Provides Reasoning**
   - Why this prediction?
   - What factors support it?
   - What factors contradict it?

---

## 🎯 Concrete Example: Marriage Prediction

### Current Approach (Insufficient)

```python
# In handle_rag_with_calculation_node (line 770)
prompt = f"""
You are a Vedic astrologer.

USER'S CHART:
{chart_data}

CURRENT DASHA:
{dasha_data}

TRANSITS:
{transit_data}

KNOWLEDGE:
{retrieved_chunks}

QUERY: When will I get married?

Provide a prediction.
"""

response = llm.invoke(prompt)
# LLM generates answer (black box)
```

**Problem:** No systematic analysis. LLM might miss important factors or apply rules incorrectly.

### Desired Approach (Structured)

```python
# Proposed PredictionEngine

class MarriagePredictionEngine:
    def predict_marriage_timing(self, chart, dasha, transits, rag_knowledge):
        # Step 1: Identify relevant factors
        factors = self.identify_marriage_factors(chart)
        # {
        #   '7th_house': 'Libra',
        #   '7th_lord': 'Venus',
        #   '7th_lord_position': '10th house',
        #   'venus_sign': 'Capricorn',
        #   'venus_strength': 'Debilitated',
        #   'marriage_karaka': 'Venus',
        #   'd9_7th_house': 'Pisces',  # Navamsa
        #   'd9_7th_lord': 'Jupiter'
        # }
        
        # Step 2: Apply classical rules
        indications = []
        
        # Rule 1: 7th lord in 10th house
        if factors['7th_lord_position'] == '10th house':
            indications.append({
                'rule': '7th lord in 10th house',
                'indication': 'delayed marriage, career-focused spouse',
                'timing_impact': 'delay',
                'source': 'BPHS Chapter 7, Verse 42'
            })
        
        # Rule 2: Venus debilitated
        if factors['venus_strength'] == 'Debilitated':
            indications.append({
                'rule': 'Venus debilitated',
                'indication': 'challenges in marriage, need for remedies',
                'timing_impact': 'delay',
                'source': 'Jataka Parijata Chapter 5'
            })
        
        # Rule 3: Current dasha
        if dasha['mahadasha']['planet'] == 'Venus':
            indications.append({
                'rule': 'Venus Mahadasha',
                'indication': 'favorable for marriage',
                'timing_impact': 'favorable',
                'source': 'Dasha timing principles'
            })
        
        # Rule 4: Jupiter transit to 7th house
        if self.is_jupiter_transiting_7th(transits, chart):
            indications.append({
                'rule': 'Jupiter transiting 7th house',
                'indication': 'marriage likely within 1 year',
                'timing_impact': 'activation',
                'source': 'Gochar (transit) principles'
            })
        
        # Step 3: Weigh indications
        favorable_count = sum(1 for i in indications if i['timing_impact'] == 'favorable')
        delay_count = sum(1 for i in indications if i['timing_impact'] == 'delay')
        
        # Step 4: Synthesize timing
        if favorable_count > delay_count:
            timing = self.calculate_favorable_timing(dasha, transits)
            confidence = 0.7
        else:
            timing = self.calculate_delayed_timing(dasha, transits)
            confidence = 0.5
        
        # Step 5: Build structured prediction
        return {
            'prediction': f"Marriage likely in {timing['period']}",
            'timing_window': timing['window'],
            'confidence': confidence,
            'supporting_factors': [i for i in indications if i['timing_impact'] == 'favorable'],
            'challenging_factors': [i for i in indications if i['timing_impact'] == 'delay'],
            'reasoning': self.build_reasoning(indications, timing),
            'recommendations': self.get_remedies(factors)
        }
```

---

## 🛠️ Where to Start

### Phase 1: Understand Current System (Week 1)

**Tasks:**
1. Read all documentation in `docs/`
2. Run the chatbot locally and test queries
3. Trace through `orchestrator.py` for a prediction query
4. Understand what calculations are available
5. Review classical texts in RAG database

**Deliverable:** Document your understanding of current flow

### Phase 2: Design Prediction Engine (Week 1-2)

**Tasks:**
1. Study classical astrological rules (BPHS, Jataka Parijata)
2. Identify key factors for common queries:
   - Marriage: 7th house, 7th lord, Venus, D9 chart
   - Career: 10th house, 10th lord, Sun, D10 chart
   - Wealth: 2nd house, 11th house, Jupiter, D2 chart
3. Design `PredictionEngine` class structure
4. Define rule application logic
5. Define factor weighting system

**Deliverable:** Design document for `PredictionEngine`

### Phase 3: Implement Core Logic (Week 2-3)

**Tasks:**
1. Create `src/prediction/` directory
2. Implement `PredictionEngine` base class
3. Implement `MarriagePredictionEngine`
4. Implement factor identification
5. Implement rule application
6. Implement timing calculations

**Deliverable:** Working `MarriagePredictionEngine`

### Phase 4: Integrate with Orchestrator (Week 3)

**Tasks:**
1. Modify `handle_rag_with_calculation_node`
2. Call `PredictionEngine` instead of direct LLM
3. Use LLM only for final formatting
4. Test with real queries

**Deliverable:** Integrated prediction system

### Phase 5: Extend to Other Domains (Week 4+)

**Tasks:**
1. Implement `CareerPredictionEngine`
2. Implement `WealthPredictionEngine`
3. Implement `HealthPredictionEngine`
4. Generalize common logic

**Deliverable:** Complete prediction system

---

## 📋 Available Resources

### Calculation Capabilities

**Birth Chart:**
```python
from src.tools.tools import get_calculation_tools

tools = get_calculation_tools()
chart = tools['vedic_birth_chart'].invoke({
    'date_of_birth': '1990-05-15',
    'time_of_birth': '14:30:00',
    'latitude': 28.6139,
    'longitude': 77.2090
})

# Available data:
# - chart['lagna'] - Ascendant sign
# - chart['moon_sign'] - Moon sign
# - chart['planets']['Venus']['rashi'] - Venus sign
# - chart['planets']['Venus']['house'] - Venus house
# - chart['planets']['Venus']['degrees'] - Venus degrees
# - chart['planets']['Venus']['nakshatra'] - Venus nakshatra
```

**Dasha:**
```python
dasha = tools['current_dasha'].invoke({
    'date_of_birth': '1990-05-15',
    'time_of_birth': '14:30:00',
    'latitude': 28.6139,
    'longitude': 77.2090
})

# Available data:
# - dasha['mahadasha']['planet'] - Current major period
# - dasha['antardasha']['planet'] - Current sub-period
# - dasha['pratyantardasha']['planet'] - Current sub-sub-period
# - dasha['mahadasha']['end_date'] - When major period ends
```

**Transits:**
```python
transits = tools['current_transits'].invoke({})

# Available data:
# - transits['planets']['Jupiter']['rashi'] - Jupiter's current sign
# - transits['planets']['Saturn']['rashi'] - Saturn's current sign
# - transits['date'] - Date of transit calculation
```

**Divisional Charts:**
```python
from src.engines.vedic import VedicEngine

engine = VedicEngine()
chart = engine.generate_chart(...)

# Calculate D9 (Navamsa)
d9_chart = engine.calculate_divisional_chart(chart, division=9)

# Available divisional charts: D1-D60
```

### Knowledge Retrieval

**RAG Engine:**
```python
from src.rag import RAGEngine

rag = RAGEngine()

# Retrieve relevant knowledge
chunks = rag.hybrid_retriever.retrieve(
    query="Venus in 10th house marriage timing",
    intent="RAG_WITH_CALCULATION",
    top_k=5,
    language='en'
)

# Each chunk contains:
# - chunk.content - Text from classical book
# - chunk.metadata - Source, chapter, page, verse
# - chunk.score - Relevance score
```

### Classical Texts Available

**In RAG Database:**
1. Brihat Parashara Hora Shastra (BPHS)
2. Jataka Parijata
3. Phaladeepika
4. Saravali
5. Uttara Kalamrita

**Access via RAG:**
```python
# Search for specific topics
marriage_texts = rag.retrieve(query="7th house marriage timing", top_k=10)
career_texts = rag.retrieve(query="10th house career success", top_k=10)
```

---

## 🚨 Important Constraints

### Safety Boundaries

**Never Predict:**
- ❌ Death timing
- ❌ Medical diagnosis
- ❌ Gambling outcomes
- ❌ Legal case results
- ❌ Harm to others

**Always Include Disclaimers For:**
- ⚠️ Health tendencies
- ⚠️ Financial advice
- ⚠️ Relationship predictions

**Safety Check:**
```python
from src.safety import create_safety_classifier

classifier = create_safety_classifier()
result = classifier.classify(query)

if result.is_blocked:
    # Do not proceed with prediction
    return refusal_message
```

### Ethical Guidelines

1. **Empowerment over Fatalism**
   - Focus on growth opportunities
   - Highlight free will
   - Provide actionable guidance

2. **Humility**
   - Acknowledge uncertainty
   - Provide confidence levels
   - Explain limitations

3. **Cultural Sensitivity**
   - Respect user's beliefs
   - Adapt language to culture
   - Avoid imposing values

---

## 📊 Success Metrics

### How to Measure Success

1. **Accuracy**
   - Test against known outcomes
   - Expert review of predictions
   - User feedback

2. **Reasoning Quality**
   - Are factors correctly identified?
   - Are rules applied correctly?
   - Is timing logical?

3. **User Satisfaction**
   - Do users find predictions helpful?
   - Do they trust the reasoning?
   - Do they return for more queries?

4. **Safety**
   - No harmful predictions
   - Appropriate disclaimers
   - Ethical boundaries maintained

---

## 💡 Design Principles

### 1. Transparency
- Show which factors were considered
- Explain why certain factors matter more
- Cite classical sources

### 2. Modularity
- Separate factor identification from rule application
- Separate timing calculation from synthesis
- Easy to add new rules

### 3. Testability
- Each component should be unit-testable
- Predictions should be reproducible
- Rules should be verifiable against texts

### 4. Extensibility
- Easy to add new prediction domains
- Easy to add new astrological systems
- Easy to incorporate user feedback

---

## 🔧 Development Setup

### Local Environment

```bash
# 1. Clone repository
cd d:\AI\IMGProjects\astro_chatbot\astro_chatbot

# 2. Activate environment
conda activate astro_chatbot

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with your API keys

# 5. Run chatbot
python chatbot_phase5_1.py
```

### Testing Predictions

```bash
# Test a query
python -c "
from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
# ... initialize orchestrator
result = orchestrator.process_query('When will I get married?', user_id='test_user')
print(result['answer'])
"
```

---

## 📞 Getting Help

### Questions About:

**Calculations:**
- Read `docs/CALCULATION_ENGINES.md`
- Check `src/engines/vedic/vedic_engine.py`
- Review `src/tools/tools.py`

**RAG System:**
- Read `docs/RAG_PIPELINE_DETAILED.md`
- Check `src/rag/rag_engine.py`
- Review `src/rag/retriever.py`

**Orchestration:**
- Read `docs/ARCHITECTURE.md`
- Check `src/orchestration/orchestrator.py`
- Review `src/ai/intent_classifier.py`

**Safety:**
- Read `src/safety/README.md`
- Check `src/safety/classifier.py`
- Review `src/safety/templates.py`

---

## 🎯 Quick Start Checklist

- [ ] Read `CURRENT_IMPLEMENTATION.md`
- [ ] Read `CALCULATION_ENGINES.md`
- [ ] Read `RAG_PIPELINE_DETAILED.md`
- [ ] Set up local development environment
- [ ] Run chatbot and test queries
- [ ] Trace through orchestrator for a prediction query
- [ ] Review classical texts in RAG database
- [ ] Design `PredictionEngine` structure
- [ ] Implement `MarriagePredictionEngine` prototype
- [ ] Test with real queries
- [ ] Iterate based on feedback

---

## � Deployment & Running Locally

### Docker Deployment (Recommended)

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

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Redis (separate terminal)
redis-server

# 4. Start API server
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing the System

```bash
# Test chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Internal-Service: your-secret-here" \
  -d '{
    "user_id": "test_user",
    "message": "What is my sun sign?",
    "session_id": "test_session"
  }'

# Test calculation endpoint
curl -X POST http://localhost:8000/api/v1/calculate/chart \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "date_of_birth": "1990-05-15",
    "time_of_birth": "14:30:00",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "timezone": "Asia/Kolkata"
  }'
```

### Common Issues

**Redis Connection Failed:**
```bash
# Check Redis status
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# Restart Redis
docker-compose restart redis
```

**Missing Environment Variables:**
```bash
# Verify .env file exists
ls -la .env

# Check required variables
grep -E "OPENAI_API_KEY|INTERNAL_SERVICE_SECRET" .env
```

**Port Already in Use:**
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process or change port in .env
PORT=8001
```

---

## �📝 Next Steps

1. **Read all documentation** (this guide + referenced docs)
2. **Set up development environment**
3. **Run and test current system**
4. **Design prediction engine**
5. **Implement prototype**
6. **Integrate and test**
7. **Extend to other domains**

---

**Welcome aboard! Your work will significantly enhance the predictive capabilities of NakshatraAI. Good luck! 🚀**

---

**Document Version:** 1.0  
**Last Updated:** February 11, 2026  
**Maintained By:** Development Team
