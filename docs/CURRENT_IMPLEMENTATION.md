<!-- docs\CURRENT_IMPLEMENTATION.md -->
# NakshatraAI - Current Implementation Status

**Last Updated:** February 11, 2026  
**Purpose:** Comprehensive documentation of what is currently implemented for handoff to new AI assistant  
**Status:** Production-ready with identified gaps for enhancement

---

## 📋 Executive Summary

NakshatraAI is a production-grade AI astrology chatbot system featuring:
- ✅ **Dual Calculation Engines** (Vedic + Western)
- ✅ **RAG Pipeline** with 8-phase preprocessing
- ✅ **Multi-tier Safety Framework**
- ✅ **Semantic Intent Routing**
- ✅ **Multilingual Support** (8 languages)
- ✅ **FastAPI Backend** with Redis sessions
- ⚠️ **Prediction Logic** - Currently basic, needs enhancement

---

## 🏗️ System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         LangGraph Orchestrator (State Machine)       │   │
│  │                                                        │   │
│  │  Flow: Authenticate → Language → Safety → Intent     │   │
│  │        → Route → Execute → Validate → Format         │   │
│  │                                                        │   │
│  │  Routes:                                              │   │
│  │  • CHITCHAT → Quick response                         │   │
│  │  • CLARIFICATION → Ambiguity handling                │   │
│  │  • CALCULATION_ONLY → Raw chart data                 │   │
│  │  • RAG_WITH_CALCULATION → Personalized predictions   │   │
│  │  • RAG_ONLY → Knowledge queries                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌─────────┐          ┌─────────┐         ┌─────────┐
   │ Redis   │          │ChromaDB │         │ MongoDB │
   │Sessions │          │ RAG KB  │         │ Users   │
   └─────────┘          └─────────┘         └─────────┘
```

---

## 📂 Project Structure

### Directory Layout

```
astro_chatbot/
├── src/
│   ├── api/                    # FastAPI REST API (8 files)
│   │   ├── main.py            # Application entry point
│   │   ├── config.py          # Settings management
│   │   ├── dependencies.py    # Dependency injection
│   │   ├── routes/            # API endpoints (5 files)
│   │   │   ├── chat.py        # Chat endpoint
│   │   │   ├── user.py        # User management
│   │   │   ├── calculation.py # Chart calculations
│   │   │   ├── health.py      # Health checks
│   │   │   └── __init__.py
│   │   ├── schemas/           # Pydantic models (5 files)
│   │   └── middleware/        # Auth, CORS (3 files)
│   │
│   ├── orchestration/         # LangGraph workflow (2 files)
│   │   └── orchestrator.py    # Main state machine (1549 lines)
│   │
│   ├── engines/               # Calculation engines (22 files)
│   │   ├── core/              # Shared utilities (6 files)
│   │   ├── vedic/             # Vedic astrology (8 files)
│   │   │   ├── vedic_engine.py       # Main engine
│   │   │   ├── dasha_systems.py      # Vimshottari dasha
│   │   │   ├── divisional_charts.py  # D1-D60 charts
│   │   │   ├── aspects_yogas.py      # Planetary yogas
│   │   │   ├── graha_stats.py        # Planetary strengths
│   │   │   ├── rashi_nakshatra.py    # Signs & nakshatras
│   │   │   └── vedic_constants.py    # Constants
│   │   └── western/           # Western astrology (7 files)
│   │       ├── western_engine.py     # Main engine
│   │       ├── western_houses.py     # House systems
│   │       ├── western_aspects.py    # Aspects
│   │       ├── western_dignities.py  # Essential dignities
│   │       └── western_constants.py  # Constants
│   │
│   ├── rag/                   # RAG pipeline (24 files)
│   │   ├── rag_engine.py      # Main RAG orchestrator (788 lines)
│   │   ├── retriever.py       # Hybrid retrieval
│   │   ├── reranker.py        # Result reranking
│   │   ├── preprocessing/     # 8-phase pipeline (12 files)
│   │   │   ├── pipeline.py              # Main pipeline
│   │   │   ├── structural_cleaner.py    # Phase 2
│   │   │   ├── page_analyzer.py         # Phase 3
│   │   │   ├── book_profiler.py         # Phase 3.5
│   │   │   ├── semantic_segmenter.py    # Phase 4
│   │   │   ├── chunk_enricher.py        # Phase 5
│   │   │   ├── embedder.py              # Phase 6
│   │   │   └── vector_db_builder.py     # Phase 7
│   │   └── extraction/        # PDF extraction (6 files)
│   │
│   ├── safety/                # Safety framework (8 files)
│   │   ├── classifier.py      # Multi-gate classifier (480 lines)
│   │   ├── models.py          # Pydantic models (240 lines)
│   │   ├── templates.py       # Response templates (380 lines)
│   │   ├── disclaimers.py     # Disclaimer texts
│   │   ├── constitution.py    # Constitutional AI
│   │   └── input_validator.py # Input validation
│   │
│   ├── routing/               # Intent routing (2 files)
│   │   └── semantic_router.py # Semantic routing with embeddings
│   │
│   ├── ai/                    # AI components (7 files)
│   │   ├── intent_classifier.py  # Intent classification
│   │   ├── personas.py           # Persona definitions
│   │   ├── persona_generator.py  # Dynamic personas
│   │   ├── prompt_builder.py     # Prompt construction
│   │   ├── hybrid_retriever.py   # Retrieval strategies
│   │   └── user_manager.py       # User profile management
│   │
│   ├── llm/                   # LLM abstraction (4 files)
│   │   ├── factory.py         # Multi-provider LLM factory
│   │   └── prompts/           # Prompt templates (3 files)
│   │
│   ├── tools/                 # Calculation tools (3 files)
│   │   ├── calculation_tools.py  # LangChain tool wrappers
│   │   └── tools.py              # Additional tools
│   │
│   ├── db/                    # Data persistence (3 files)
│   │   ├── redis_client.py    # Session management
│   │   └── sqlite_client.py   # User database
│   │
│   ├── locales/               # Multilingual (8 files)
│   │   └── language_detector.py  # Language detection
│   │
│   ├── utils/                 # Utilities (12 files)
│   │   └── localization.py    # Localization manager
│   │
│   └── integrations/          # External integrations (4 files)
│
├── docs/                      # Documentation (9 files)
├── tests/                     # Test suites
├── data/                      # Data storage
│   └── vectordb/              # ChromaDB persistence
├── config/                    # Configuration files
└── scripts/                   # Utility scripts
```

---

## 🎯 Implemented Features

### 1. Calculation Engines

#### Vedic Engine (`src/engines/vedic/`)
**Status:** ✅ Fully Implemented

**Capabilities:**
- Birth chart calculation (D1 Rashi chart)
- Divisional charts (D1-D60) - 16 standard divisional charts
- Vimshottari Dasha system (120-year cycle)
  - Mahadasha, Antardasha, Pratyantardasha calculation
  - Current period identification
- Planetary positions in signs and houses
- Nakshatra calculations (27 lunar mansions)
- Planetary aspects (Vedic aspects)
- Yogas detection (planetary combinations)
- Planetary strengths (Shadbala, Ashtakavarga)
- Ayanamsa correction (Lahiri ayanamsa)

**Key Files:**
- `vedic_engine.py` (757 lines) - Main calculation engine
- `dasha_systems.py` (400 lines) - Dasha calculations
- `divisional_charts.py` (690 lines) - D-chart calculations
- `aspects_yogas.py` (515 lines) - Yoga detection
- `graha_stats.py` (443 lines) - Planetary strengths

**Dependencies:**
- `pyswisseph` - Swiss Ephemeris for astronomical calculations
- Custom algorithms for Vedic-specific calculations

#### Western Engine (`src/engines/western/`)
**Status:** ✅ Fully Implemented

**Capabilities:**
- Tropical zodiac calculations
- House systems (Placidus, Koch, Equal, Whole Sign)
- Planetary aspects (conjunction, opposition, trine, square, sextile)
- Essential dignities (rulership, exaltation, detriment, fall)
- Aspect orbs and applying/separating aspects
- Midpoints calculation

**Key Files:**
- `western_engine.py` (645 lines) - Main engine
- `western_houses.py` (502 lines) - House calculations
- `western_aspects.py` (512 lines) - Aspect calculations
- `western_dignities.py` (490 lines) - Dignity calculations

### 2. Calculation Tools (`src/tools/`)

**LangChain Tool Wrappers:**
1. **`calculate_vedic_birth_chart`** - Complete birth chart with all planetary positions
2. **`calculate_current_dasha`** - Current Vimshottari dasha periods
3. **`calculate_current_transits`** - Real-time planetary transits

**Format:** Structured dictionaries optimized for LLM consumption

### 3. RAG Pipeline

#### Preprocessing Pipeline (`src/rag/preprocessing/`)
**Status:** ✅ 8-Phase Pipeline Implemented

**Phases:**
1. **Extraction** (Vision LLM) - PDF to Markdown using Gemini Vision
2. **Structural Cleaning** - Noise removal, normalization
3. **Cross-Page Analysis** - Continuity detection
4. **Book Profiling** (Phase 3.5) - Automated structure discovery
5. **Semantic Segmentation** - Context-aware chunking
6. **Chunk Enrichment** - Summaries, entity extraction
7. **Embedding** - OpenAI `text-embedding-3-large`
8. **Vector DB Ingestion** - ChromaDB persistence

**Key Innovation:** Book-agnostic structural discovery using LLM profiling

#### Retrieval Engine (`src/rag/rag_engine.py`)
**Status:** ✅ Implemented with Multiple Strategies

**Retrieval Strategies:**
- **Vector Search** - Semantic similarity (default)
- **Hybrid Search** - Vector + BM25 keyword search
- **HyDE** (Hypothetical Document Embeddings) - For conceptual queries
- **Query Routing** - Automatic strategy selection based on query type

**Features:**
- Follow-up query detection
- Context expansion
- Query rewriting
- Reranking (optional)
- Metadata filtering (language, source, chapter)

### 4. Safety Framework (`src/safety/`)

**Status:** ✅ Multi-Gate Production-Ready System

**Architecture:**
- **Gate 1:** Pattern matching (~70% of queries, <1ms)
- **Gate 2:** LLM classification (~30% of queries, ~200-500ms)

**Classification Categories:**
1. **HARD_BLOCK** - Death predictions, medical diagnosis, gambling
2. **SOFT_BLOCK** - Out of scope, privacy violations
3. **CONDITIONAL** - Answer with disclaimers (health, financial, relationship)
4. **REFRAME** - Transform question to be astrologically appropriate
5. **SAFE** - Proceed normally

**Components:**
- 60+ pre-written response templates
- 5-tier classification system
- Empathetic decline messages
- Constitutional AI integration

### 5. Intent Classification (`src/routing/` + `src/ai/`)

**Semantic Router (`src/routing/semantic_router.py`):**
- Model: `sentence-transformers/all-MiniLM-L6-v2` (~80MB)
- Latency: <50ms on CPU
- Use case: Fast chitchat detection

**LLM Intent Classifier (`src/ai/intent_classifier.py`):**
- Categories: CHITCHAT, NEEDS_CALCULATION, NEEDS_RAG, CLARIFICATION
- Confidence scoring
- Caching for repeated queries

### 6. Orchestration (`src/orchestration/orchestrator.py`)

**Status:** ✅ LangGraph State Machine (1549 lines)

**Nodes:**
1. `authenticate` - Load user profile (DB or session override)
2. `detect_language` - Language detection (library + LLM fallback)
3. `classify_intent` - Safety check + intent classification
4. `handle_chitchat` - Quick conversational responses
5. `handle_clarification` - Ambiguity resolution
6. `handle_calculation_only` - Raw chart data
7. `handle_rag_with_calculation` - Personalized predictions
8. `handle_rag_only` - Knowledge queries
9. `validate_response` - Constitutional AI critic
10. `format_response` - Final formatting with disclaimers

**State Management:**
- User profile (birth data, preferences)
- Conversation history
- Chart data (cached)
- Dasha data (cached)
- Transit data (calculated on-demand)
- Safety metadata
- Language detection

### 7. API Layer (`src/api/`)

**Status:** ✅ Production FastAPI Application

**Endpoints:**
- `POST /api/v1/chat` - Main chat endpoint (integration mode)
- `GET /api/v1/health` - Health check
- `GET /api/v1/user/{user_id}` - Get user profile
- `POST /api/v1/user` - Create user
- `PUT /api/v1/user/{user_id}` - Update user
- `POST /api/v1/calculate/chart` - Calculate birth chart

**Middleware:**
- CORS configuration
- Request timing
- Internal service authentication (`X-Internal-Service` header)
- Rate limiting (10 req/min per API key)

**Session Management:**
- Redis-based conversation history
- 24-hour expiration
- 20-message limit
- Graceful degradation without Redis

### 8. Multilingual Support (`src/locales/`)

**Status:** ✅ 8-Language Lockdown

**Supported Languages:**
1. English (`en`)
2. Hindi (`hi`) + Romanized (`hi-lat`)
3. Marathi (`mr`) + Romanized (`mr-lat`)
4. Punjabi (`pa`) + Romanized (`pa-lat`)
5. Tamil (`ta`) + Romanized (`ta-lat`)
6. Telugu (`te`) + Romanized (`te-lat`)
7. Malayalam (`ml`) + Romanized (`ml-lat`)

**Features:**
- Library-based detection (fasttext)
- LLM fallback for ambiguous cases
- Roman script support (single JSON file per language)
- RAG language filtering (prevents cross-language contamination)

### 9. LLM Abstraction (`src/llm/factory.py`)

**Status:** ✅ Multi-Provider Support

**Providers:**
- **OpenAI** (gpt-4o-mini, gpt-4o) - Default
- **Google Gemini** (gemini-2.0-flash-exp, gemini-2.5-flash)
- **Ollama** (local models)

**Purpose-Based Selection:**
- Fast LLM for classification/routing
- Quality LLM for generation/interpretation

---

## ⚠️ Current Limitations & Gaps

### 1. Prediction Logic - **PRIMARY GAP**

**Current State:**
The system can:
- ✅ Calculate birth charts accurately
- ✅ Calculate current dashas
- ✅ Calculate transits
- ✅ Retrieve relevant classical texts
- ✅ Generate responses using LLM

**What's Missing:**
The system does NOT have sophisticated logic to:
- ❌ **Synthesize multiple factors** (dasha + transit + natal chart + divisional charts)
- ❌ **Weight planetary influences** (which factor is most important?)
- ❌ **Time predictions accurately** (when exactly will an event occur?)
- ❌ **Consider house lords** in predictions
- ❌ **Apply classical rules systematically** (e.g., "7th lord in 10th during Venus dasha")
- ❌ **Detect contradictions** (one factor says yes, another says no)
- ❌ **Provide confidence levels** for predictions

**Current Approach:**
```python
# Simplified current flow in handle_rag_with_calculation_node:
1. Calculate chart, dasha, transits
2. Retrieve relevant text chunks from RAG
3. Pass everything to LLM with a prompt
4. LLM generates response (black box)
```

**What's Needed:**
A structured prediction engine that:
1. Identifies relevant factors for the query
2. Applies classical astrological rules
3. Weighs conflicting indications
4. Provides reasoning for predictions
5. Estimates timing windows
6. Assigns confidence scores

**Example:**
```
Query: "When will I get married?"

Current: LLM reads chart + dasha + transits + texts → generates answer
Needed: 
  1. Check 7th house (marriage house)
  2. Check 7th lord position and strength
  3. Check Venus (karaka for marriage)
  4. Check current dasha (is it 7th lord dasha?)
  5. Check transits (Jupiter/Saturn to 7th house?)
  6. Check divisional charts (D9 for marriage)
  7. Apply timing rules (dasha + transit alignment)
  8. Synthesize → "High probability in Venus-Moon period (Mar-Jun 2027)"
```

### 2. Divisional Chart Integration

**Status:** Calculated but not used in predictions

- ✅ D1-D60 charts can be calculated
- ❌ Not integrated into prediction logic
- ❌ No D9 (Navamsa) analysis for marriage
- ❌ No D10 (Dasamsa) analysis for career
- ❌ No varga strength calculations

### 3. Yoga Detection

**Status:** Basic detection, no interpretation

- ✅ Can detect common yogas (Raj Yoga, Dhana Yoga, etc.)
- ❌ Not used in predictions
- ❌ No yoga strength assessment
- ❌ No timing of yoga activation

### 4. Aspect Analysis

**Status:** Calculated but underutilized

- ✅ Vedic aspects calculated
- ✅ Western aspects calculated
- ❌ Not systematically used in interpretations
- ❌ No aspect strength weighting

### 5. Planetary Strengths

**Status:** Partially implemented

- ✅ Basic dignity calculations
- ❌ No Shadbala (six-fold strength) implementation
- ❌ No Ashtakavarga (eight-fold division)
- ❌ Strengths not used in prediction weighting

### 6. Transit Analysis

**Status:** Basic calculation only

- ✅ Current planetary positions calculated
- ❌ No transit-to-natal aspect analysis
- ❌ No transit timing predictions
- ❌ No Gochara (transit) rules applied

### 7. Dasha Interpretation

**Status:** Calculation complete, interpretation basic

- ✅ Vimshottari dasha calculated accurately
- ❌ No systematic dasha lord interpretation
- ❌ No dasha-bhukti combination analysis
- ❌ No dasha timing refinement

### 8. Remedial Measures

**Status:** Not implemented

- ❌ No gemstone recommendations
- ❌ No mantra suggestions
- ❌ No charity/donation guidance
- ❌ No yantra recommendations

### 9. Compatibility Analysis

**Status:** Not implemented

- ❌ No synastry (chart comparison)
- ❌ No Kuta matching (Vedic compatibility)
- ❌ No composite charts

### 10. Progressions & Directions

**Status:** Not implemented

- ❌ No secondary progressions
- ❌ No solar arc directions
- ❌ No solar return charts

---

## 🔧 Technical Debt

### Code Quality
- ⚠️ Orchestrator.py is 1549 lines (should be refactored)
- ⚠️ Some duplicate logic between Vedic/Western engines
- ⚠️ Limited unit test coverage for calculation engines

### Performance
- ⚠️ No caching for RAG retrievals
- ⚠️ Embedding model loaded on every request (should be singleton)
- ⚠️ No connection pooling for ChromaDB

### Observability
- ⚠️ Limited structured logging
- ⚠️ No metrics collection (Prometheus)
- ⚠️ No distributed tracing

### Documentation
- ⚠️ Limited inline code documentation
- ⚠️ No API usage examples
- ⚠️ No developer onboarding guide

---

## 📊 What Works Well

### Strengths
1. ✅ **Calculation Accuracy** - Vedic/Western engines produce correct results
2. ✅ **Safety Framework** - Robust multi-gate system prevents harmful responses
3. ✅ **RAG Pipeline** - Sophisticated preprocessing produces high-quality chunks
4. ✅ **Multilingual** - Solid language detection and response generation
5. ✅ **API Design** - Clean REST API with proper authentication
6. ✅ **State Management** - LangGraph orchestrator handles complex flows well

### Production-Ready Components
- API layer (FastAPI)
- Safety classifier
- Calculation engines (Vedic/Western)
- RAG preprocessing pipeline
- Session management (Redis)
- Authentication/authorization

---

## 🎯 Recommended Next Steps for Enhancement

### Priority 1: Prediction Logic Engine
**Goal:** Build structured prediction system

**Tasks:**
1. Create `PredictionEngine` class
2. Implement factor identification (which houses/planets matter for this query?)
3. Implement classical rule application
4. Implement factor weighting and synthesis
5. Implement timing calculations
6. Add confidence scoring

**Estimated Effort:** 2-3 weeks

### Priority 2: Divisional Chart Integration
**Goal:** Use D-charts in predictions

**Tasks:**
1. Integrate D9 for marriage predictions
2. Integrate D10 for career predictions
3. Implement varga strength calculations
4. Add D-chart interpretation to prompts

**Estimated Effort:** 1 week

### Priority 3: Enhanced Dasha Interpretation
**Goal:** Systematic dasha analysis

**Tasks:**
1. Create dasha lord interpretation rules
2. Implement dasha-bhukti combination analysis
3. Add timing refinement logic
4. Integrate with prediction engine

**Estimated Effort:** 1 week

### Priority 4: Testing & Validation
**Goal:** Ensure prediction accuracy

**Tasks:**
1. Create test cases with known outcomes
2. Validate against classical texts
3. Expert review of predictions
4. A/B testing with users

**Estimated Effort:** Ongoing

---

## 📚 Key Files for New AI Assistant

### Must-Read Files
1. **`src/orchestration/orchestrator.py`** (1549 lines) - Main workflow logic
2. **`src/engines/vedic/vedic_engine.py`** (757 lines) - Vedic calculations
3. **`src/rag/rag_engine.py`** (788 lines) - RAG orchestration
4. **`src/safety/classifier.py`** (480 lines) - Safety system
5. **`src/tools/calculation_tools.py`** (486 lines) - LangChain tool wrappers

### Configuration Files
1. **`.env.example`** - Environment variables
2. **`src/api/config.py`** - API settings
3. **`config/config.yaml`** - Orchestrator config

### Documentation
1. **`docs/ARCHITECTURE.md`** - System design
2. **`docs/PROJECT_STATUS.md`** - Current state
3. **`docs/API_REFERENCE.md`** - API documentation
4. **`src/safety/README.md`** - Safety system guide

---

## 🔍 Understanding the Codebase

### Data Flow Example: Personalized Prediction

```
1. User Query: "When will I get married?"
   ↓
2. API Endpoint: POST /api/v1/chat
   ↓
3. Orchestrator: authenticate_node
   - Loads user profile from Redis/MongoDB
   - Birth data: DOB, TOB, Location
   ↓
4. Orchestrator: detect_language_node
   - Detects: English (en)
   ↓
5. Orchestrator: classify_intent_node
   - Safety check: SAFE (no blocks)
   - Intent: NEEDS_RAG (requires knowledge + calculation)
   ↓
6. Orchestrator: handle_rag_with_calculation_node
   a. Calculate birth chart (VedicEngine)
      - Lagna, Moon sign, planetary positions
   b. Calculate current dasha (DashaSystem)
      - Mahadasha, Antardasha, Pratyantardasha
   c. Calculate transits (VedicEngine)
      - Current planetary positions
   d. Retrieve knowledge (RAGEngine)
      - Query: "marriage prediction 7th house Venus"
      - Returns: 5 chunks from classical texts
   e. Build prompt (PromptBuilder)
      - System: Vedic astrologer persona
      - Context: Birth chart + Dasha + Transits
      - Knowledge: Retrieved chunks
      - Query: Original question
   f. Generate response (LLM)
      - Model: gpt-4o-mini
      - Returns: Interpretation
   ↓
7. Orchestrator: validate_response_node
   - Constitutional AI check
   - Ensures ethical boundaries
   ↓
8. Orchestrator: format_response_node
   - Adds disclaimers if needed
   - Formats in user's language
   ↓
9. API Response:
   {
     "answer": "Based on your chart...",
     "sources": [...],
     "metadata": {...}
   }
```

---

## 🚀 Deployment Status

### Current Deployment
- ✅ Docker containerization
- ✅ Docker Compose orchestration
- ✅ Redis integration
- ✅ Environment-based configuration

### Not Yet Deployed
- ❌ Production server (staging/prod)
- ❌ CI/CD pipeline
- ❌ Monitoring/alerting
- ❌ Load balancing
- ❌ Auto-scaling

---

## 📞 Getting Help

### For Code Understanding
1. Read this document first
2. Review `docs/ARCHITECTURE.md`
3. Check inline code comments
4. Review test files for usage examples

### For Prediction Enhancement
1. Review classical astrology texts in RAG database
2. Consult `src/engines/vedic/` for available calculations
3. Study `src/orchestration/orchestrator.py` for current flow
4. Propose structured prediction logic

---

**Document Version:** 1.0  
**Last Updated:** February 11, 2026  
**Maintained By:** Development Team
