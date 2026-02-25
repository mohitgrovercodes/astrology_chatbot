# NakshatraAI — System Architecture v2.0

> **Last Updated:** February 20, 2026  
> **Architecture Version:** 2.0 (Post-Redis, Post-UX Fixes)  
> **Status:** Production Architecture

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Diagram](#component-diagram)
3. [Data Flow](#data-flow)
4. [Caching Architecture](#caching-architecture)
5. [Safety Framework](#safety-framework)
6. [Orchestration Engine](#orchestration-engine)
7. [RAG Pipeline](#rag-pipeline)
8. [Validation Engine](#validation-engine)
9. [API Layer](#api-layer)
10. [Deployment Architecture](#deployment-architecture)

---

## Architecture Overview

### Design Principles

1. **Modularity** - Independent, swappable components
2. **Determinism** - Calculations produce identical results
3. **Safety-First** - Multi-layer guardrails before LLM
4. **Performance** - Multi-tier caching for speed
5. **Scalability** - Stateless design, shared cache
6. **Observability** - Comprehensive logging at each layer

### System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   CLI Chat   │  │  FastAPI     │  │  Mobile App  │     │
│  │  (chatbot.py)│  │   REST API   │  │   (Future)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         LangGraph Orchestrator (orchestrator.py)       │ │
│  │                                                        │ │
│  │  [Auth] → [Lang] → [Safety] → [Intent] → [Routing]  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                      INTELLIGENCE LAYER                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  Intent    │  │  Safety    │  │  Persona   │           │
│  │ Classifier │  │ Classifier │  │  System    │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │    RAG     │  │ Validation │  │    LLM     │           │
│  │   Engine   │  │   Engine   │  │  Factory   │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                       DATA LAYER                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Redis    │  │  ChromaDB  │  │   SQLite   │           │
│  │   Cache    │  │  Vector DB │  │  User DB   │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    CALCULATION LAYER                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Vedic    │  │  Western   │  │Swiss       │           │
│  │   Engine   │  │   Engine   │  │Ephemeris   │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Diagram

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                    EnhancedLangGraphOrchestrator         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Manages conversation flow through LangGraph nodes:     │
│                                                          │
│  1. _authenticate_node                                  │
│     ├─ Load user profile                                │
│     └─ Inject session data                              │
│                                                          │
│  2. _detect_language_node                               │
│     ├─ Detect: hi|en|ta|te|kn|ml                       │
│     └─ Set persona language                             │
│                                                          │
│  3. _handle_safety_check_node                           │
│     ├─ Run multi-gate classifier                        │
│     ├─ Block harmful queries                            │
│     ├─ REFRAME sensitive queries                        │
│     └─ Add conditional disclaimers                      │
│                                                          │
│  4. _classify_intent_node                               │
│     ├─ Pattern cache check (instant)                    │
│     ├─ LLM classification                               │
│     └─ Return: CHITCHAT | CALCULATION_ONLY |            │
│        RAG_WITH_CALCULATION | RAG_ONLY                  │
│                                                          │
│  5. Intent-Specific Handlers:                           │
│     ├─ _handle_chitchat_node                            │
│     │   ├─ Semantic routing                             │
│     │   ├─ Context-aware greetings                      │
│     │   └─ Persona-driven responses                     │
│     │                                                    │
│     ├─ _handle_calculation_only_node                    │
│     │   ├─ Check for profile data queries               │
│     │   ├─ Calculate/load chart                         │
│     │   └─ LLM extraction of requested data             │
│     │                                                    │
│     ├─ _handle_rag_with_calculation_node                │
│     │   ├─ Calculate chart + dasha + transits           │
│     │   ├─ Run validation engine (if prediction)        │
│     │   ├─ Retrieve knowledge chunks                    │
│     │   └─ Generate LLM response with context           │
│     │                                                    │
│     └─ _handle_rag_only_node                            │
│         ├─ Retrieve knowledge chunks                    │
│         └─ Generate conceptual response                 │
│                                                          │
│  6. _format_response_node                               │
│     ├─ Add disclaimers (if needed)                      │
│     ├─ Localize response                                │
│     └─ Format for output                                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Component Interactions

```
User Query: "When will I get married?"
    ↓
┌─────────────────────────────────────────────┐
│  1. Authentication                           │
│  ├─ Load user002 profile                    │
│  ├─ Birth data: ✓ Complete                  │
│  └─ Check Redis for cached chart            │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  2. Language Detection                       │
│  ├─ Detect: hi-lat (Hinglish)               │
│  └─ Set persona: Vedic + Hindi               │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  3. Safety Check                             │
│  ├─ Own-data check: ✓ "my marriage"         │
│  ├─ Third-party check: ✗ No third party     │
│  ├─ Semantic route: marriage → CONDITIONAL  │
│  ├─ Category: REFRAME                        │
│  ├─ Reframed: "What astrological periods..."│
│  └─ Add disclaimer: RELATIONSHIP             │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  4. Intent Classification                   │
│  ├─ Pattern check: ✗ Not in cache           │
│  ├─ LLM classification                      │
│  ├─ Intent: RAG_WITH_CALCULATION            │
│  └─ Confidence: 0.98                        │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  5. RAG_WITH_CALCULATION Handler            │
│  │                                          │
│  ├─ Step 1: Calculate Chart                 │
│  │   ├─ Check Redis session cache           │
│  │   ├─ If miss: Calculate from ephemeris   │
│  │   ├─ Calculate dasha (SATURN/RAHU/MARS)  │
│  │   ├─ Calculate transits (2026-02-20)     │
│  │   └─ Cache in Redis (1h TTL)             │
│  │                                          │
│  ├─ Step 2: Validation                      │
│  │   ├─ Detect query type: marriage         │
│  │   ├─ Check Redis validation cache        │
│  │   ├─ If miss: Run validation engine      │
│  │   ├─ Tier 1: 3 rules checked             │
│  │   ├─ Result: STRONG (10.0/10)            │
│  │   └─ Cache result (30d TTL)              │
│  │                                          │
│  ├─ Step 3: RAG Retrieval                   │
│  │   ├─ Check Redis RAG cache               │
│  │   ├─ If miss: Hybrid search              │
│  │   ├─ BM25 + Vector retrieval             │
│  │   ├─ Retrieved: 10 chunks                │
│  │   └─ Cache results (7d TTL)              │
│  │                                          │
│  └─ Step 4: LLM Generation                  │
│      ├─ Build prompt with:                  │
│      │   - Chart data                       │
│      │   - Dasha periods                    │
│      │   - Transits                         │
│      │   - Knowledge chunks                 │
│      │   - Validation result                │
│      ├─ Use LLM (3072 tokens)               │
│      └─ Generate response                   │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  6. Format Response                         │
│  ├─ Add RELATIONSHIP disclaimer             │
│  ├─ Localize for hi-lat                     │
│  └─ Return formatted response               │
└─────────────────────────────────────────────┘
    ↓
Response: "Astrologically, Jupiter's transit..."
```

---

## Data Flow

### Request Flow Diagram

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ POST /api/v1/chat/query
     ↓
┌────────────────┐
│   FastAPI      │
│   Middleware   │
│  - Auth check  │
│  - Rate limit  │
│  - Logging     │
└────┬───────────┘
     │
     ↓
┌────────────────────────────────────────────┐
│         Orchestrator.process_query         │
│                                            │
│  Redis Check:                              │
│  ├─ Session cache (chart/dasha/transit)   │
│  ├─ Intent cache (classification)         │
│  └─ Validation cache (if prediction)      │
│                                            │
│  On Cache Miss:                            │
│  ├─ Invoke LangGraph                      │
│  ├─ Process through nodes                 │
│  └─ Cache results                         │
└────┬───────────────────────────────────────┘
     │
     ↓
┌────────────────┐
│   Response     │
│   Formatter    │
│  - Add metadata│
│  - Disclaimers │
│  - Localization│
└────┬───────────┘
     │
     ↓
┌────────────────┐
│   Client       │
│   Receives     │
│   JSON         │
└────────────────┘
```

### Data Storage

```
┌─────────────────────────────────────────────┐
│               Data Storage Layer            │
├─────────────────────────────────────────────┤
│                                             │
│  SQLite (data/astro.db)                     │
│  ├─ users                                   │
│  │   ├─ user_id (PK)                        │
│  │   ├─ name, dob, birth_time, birth_place  │
│  │   └─ birth_chart_cache (JSON)            │
│  │                                          │
│  └─ conversation_history                    │
│      ├─ id (PK)                             │
│      ├─ user_id (FK)                        │
│      ├─ role (user/assistant)               │
│      ├─ content                             │
│      └─ timestamp                           │
│                                             │
│  ChromaDB (data/vectordb)                   │
│  ├─ Collection: vedic_astrology_knowledge   │
│  ├─ Documents: 14,508 chunks                │
│  ├─ Embeddings: 3072-dimensional            │
│  └─ Metadata: source, page, topic           │
│                                             │
│  Redis (5 Layers)                           │
│  ├─ session:{user_id}:chart_data (1h)      │
│  ├─ session:{user_id}:dasha_data (1h)      │
│  ├─ session:{user_id}:transit_data (1h)    │
│  ├─ intent:{query_hash} (24h)               │
│  ├─ chart:{user_id} (30d)                   │
│  ├─ rag:{query_hash} (7d)                   │
│  └─ validation:{user_id}:{type} (30d)      │
│                                              │
│  File System                                 │
│  ├─ validation_rules/ (~92 MB JSON)         │
│  ├─ data/books/ (Source PDFs)               │
│  └─ logs/ (Application logs)                │
│                                              │
└─────────────────────────────────────────────┘
```

---

## Caching Architecture

### 5-Layer Redis Cache

```
┌─────────────────────────────────────────────────────────┐
│                    REDIS CACHE LAYERS                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Layer 1: SESSION CACHE (TTL: 1 hour)                  │
│  Purpose: Eliminate recalculation within conversation   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ session:{user_id}:chart_data                    │   │
│  │ session:{user_id}:dasha_data                    │   │
│  │ session:{user_id}:transit_data                  │   │
│  │ session:{user_id}:conversation                  │   │
│  └─────────────────────────────────────────────────┘   │
│  Impact: 3-5s → 0.01s per turn (99% reduction)         │
│                                                          │
│  Layer 2: INTENT CACHE (TTL: 24 hours)                 │
│  Purpose: Fast classification for repeat queries        │
│  ┌─────────────────────────────────────────────────┐   │
│  │ intent:{md5(query)} → {intent, confidence, ...} │   │
│  └─────────────────────────────────────────────────┘   │
│  Impact: 0.5s → 0.001s (99.8% reduction)               │
│  Scope: Shared across all users                        │
│                                                          │
│  Layer 3: CHART CACHE (TTL: 30 days)                   │
│  Purpose: Long-term chart storage                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │ chart:{user_id} → {full_chart_json}             │   │
│  └─────────────────────────────────────────────────┘   │
│  Impact: 3-5s → 0.01s (99% reduction)                  │
│  Invalidation: On profile update only                   │
│                                                          │
│  Layer 4: RAG CACHE (TTL: 7 days)                      │
│  Purpose: Cache retrieved knowledge                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │ rag:{md5(query)} → [chunks]                     │   │
│  └─────────────────────────────────────────────────┘   │
│  Impact: 2-3s → 0.01s (99% reduction)                  │
│  Scope: Shared across similar queries                  │
│                                                          │
│  Layer 5: VALIDATION CACHE (TTL: 30 days)              │
│  Purpose: Cache expensive validation results            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ validation:{user_id}:{query_type} → result      │   │
│  └─────────────────────────────────────────────────┘   │
│  Impact: 8s → 0.01s (99.8% reduction)                  │
│  Scope: User-specific, per query type                  │
│                                                          │
└─────────────────────────────────────────────────────────┘

Total Impact: 15-20s → 2-3s per turn (85% improvement)
```

### Cache Hit Flow

```
User Query → Check Redis Layers
    ↓
Layer 1 Check: session:{user_id}:chart_data
    ├─ HIT: Return cached chart (0.01s) ✅
    └─ MISS: Continue to calculation ↓
    
Layer 3 Check: chart:{user_id}
    ├─ HIT: Return long-term chart (0.01s) ✅
    └─ MISS: Calculate from Swiss Ephemeris (3-5s) →
             Cache in Layer 1 + Layer 3
             
Layer 2 Check: intent:{query_hash}
    ├─ HIT: Return classification (0.001s) ✅
    └─ MISS: Run LLM classification (0.5s) →
             Cache result
             
Layer 4 Check: rag:{query_hash}
    ├─ HIT: Return chunks (0.01s) ✅
    └─ MISS: Run hybrid retrieval (2-3s) →
             Cache results
             
Layer 5 Check: validation:{user_id}:marriage
    ├─ HIT: Return validation (0.01s) ✅
    └─ MISS: Run validation engine (8s) →
             Cache result
```

---

## Safety Framework

### Multi-Gate Classifier Architecture

```
User Query
    ↓
┌─────────────────────────────────────────────┐
│         Gate -1: Own-Data Detection          │
│  Checks: "my dob", "my chart", "when was i" │
│  Result: SAFE (user's own data)             │
│  Bypass: All other gates                    │
└─────────────────────────────────────────────┘
    ↓ (No match)
┌─────────────────────────────────────────────┐
│        Gate 0: Third-Party Detection         │
│  Checks: "my friend", "my sister", names    │
│  Result: SOFT_BLOCK (third-party)           │
│  Template: Suggest alternatives             │
└─────────────────────────────────────────────┘
    ↓ (No match)
┌─────────────────────────────────────────────┐
│        Gate 1: Semantic Routing              │
│  Routes: greeting, identity, death, medical │
│  Confidence: 0.75 threshold                 │
│  Result: Category (SAFE/BLOCK/CONDITIONAL)  │
└─────────────────────────────────────────────┘
    ↓ (No match)
┌─────────────────────────────────────────────┐
│        Gate 2: LLM Classification            │
│  Model: Gemini 2.5 Flash                    │
│  Prompt: Detailed safety criteria           │
│  Result: Full SafetyDecision object         │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│           Safety Decision                    │
│  ├─ SAFE: Proceed                           │
│  ├─ SOFT_BLOCK: Refuse with template        │
│  ├─ HARD_BLOCK: Refuse firmly               │
│  ├─ REFRAME: Transform query                │
│  └─ CONDITIONAL: Proceed with disclaimer    │
└─────────────────────────────────────────────┘
```

### Safety Decision Tree

```
Query: "When will my friend Deepika get married?"
    ↓
Gate -1: Own-Data Check
    ├─ Pattern: "my friend" (not "my")
    └─ Result: No match, continue
    ↓
Gate 0: Third-Party Check
    ├─ Pattern: "my friend Deepika"
    ├─ Extracted: "Deepika"
    └─ Result: SOFT_BLOCK ✋
        ↓
        Template: "I can only provide readings for YOU..."
        ↓
        END (No LLM call)

Query: "What is my dob?"
    ↓
Gate -1: Own-Data Check
    ├─ Pattern: "my dob" ✅
    └─ Result: SAFE
        ↓
        Skip all other gates
        ↓
        Route to CALCULATION_ONLY

Query: "When will I die?"
    ↓
Gate -1: No match → Gate 0: No match → Gate 1: Semantic
    ├─ Route match: "death_prediction"
    ├─ Confidence: 0.98
    └─ Result: HARD_BLOCK ✋
        ↓
        Template: "I cannot provide predictions about..."
        ↓
        END (No LLM call)

Query: "When will I get married?"
    ↓
Gate -1: No match ("my" but not "my [data]")
    ↓
Gate 0: No third-party
    ↓
Gate 1: Semantic route
    ├─ Route: "marriage" → CONDITIONAL
    └─ Result: REFRAME
        ↓
        Reframed: "What astrological periods indicate marriage?"
        ↓
        Add disclaimer: RELATIONSHIP
        ↓
        Continue to intent classification
```

---

[Continuing in next response due to length...]
