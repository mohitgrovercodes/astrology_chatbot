# NakshatraAI — System Architecture

> **Last Updated:** 2026-02-17  
> **Version:** 2.0 (Post-MVP Architecture)

---

## 1. High-Level Architecture

NakshatraAI follows a **layered architecture** with clear separation between deterministic computation, knowledge retrieval, LLM interpretation, and safety enforcement.

```mermaid
graph TB
    subgraph "Client Layer"
        CLI["CLI Chatbot<br/>(chatbot.py)"]
        API["FastAPI REST API<br/>(src/api/)"]
        MOBILE["Mobile App<br/>(External)"]
    end

    subgraph "Orchestration Layer"
        ORCH["LangGraph Orchestrator<br/>(orchestrator.py)"]
        INTENT["Intent Classifier<br/>(intent_classifier.py)"]
        LANG["Language Detector<br/>(language_detector.py)"]
        SAFETY["Safety Classifier<br/>(classifier.py)"]
    end

    subgraph "Intelligence Layer"
        LLM["LLM Factory<br/>(factory.py)"]
        RAG["RAG Engine<br/>(rag_engine.py)"]
        PERSONA["Persona System<br/>(personas.py)"]
        PROMPT["Prompt Builder<br/>(prompt_builder.py)"]
    end

    subgraph "Retrieval Layer"
        RET["Hybrid Retriever<br/>(retriever.py)"]
        CHROMA["ChromaDB<br/>(Vector Store)"]
        BM25["BM25 Index<br/>(Keyword Search)"]
        RERANK["Reranker<br/>(reranker.py)"]
        MEMORY["Memory Retriever<br/>(memory_retriever.py)"]
    end

    subgraph "Computation Layer"
        VEDIC["Vedic Engine<br/>(vedic_engine.py)"]
        WEST["Western Engine<br/>(western_engine.py)"]
        CORE["Core Ephemeris<br/>(ephemeris.py)"]
        TOOLS["Calculation Tools<br/>(calculation_tools.py)"]
        VALID["Validation Engine<br/>(vedic_validation_engine_v2.py)"]
    end

    subgraph "Data Layer"
        REDIS["Redis Cache"]
        MONGO["MongoDB / SQLite"]
        RULES["Rule JSON Files<br/>(~92 MB)"]
    end

    CLI --> ORCH
    API --> ORCH
    MOBILE --> API

    ORCH --> INTENT
    ORCH --> LANG
    ORCH --> SAFETY
    ORCH --> LLM
    ORCH --> RAG
    ORCH --> TOOLS

    RAG --> RET
    RAG --> PERSONA
    RAG --> PROMPT
    RAG --> MEMORY

    RET --> CHROMA
    RET --> BM25
    RET --> RERANK

    TOOLS --> VEDIC
    TOOLS --> WEST
    VEDIC --> CORE
    WEST --> CORE
    ORCH --> VALID
    VALID --> RULES

    ORCH --> REDIS
    ORCH --> MONGO
```

---

## 2. Request Processing Flow

Every user query flows through a deterministic LangGraph state machine:

```mermaid
stateDiagram-v2
    [*] --> Authenticate
    Authenticate --> DetectLanguage
    DetectLanguage --> ClassifyIntent
    
    ClassifyIntent --> Chitchat: CHITCHAT
    ClassifyIntent --> Clarification: AMBIGUOUS
    ClassifyIntent --> CalculationOnly: CALCULATION_ONLY
    ClassifyIntent --> RAGWithCalc: RAG_WITH_CALCULATION
    ClassifyIntent --> RAGOnly: RAG_ONLY
    
    Chitchat --> ValidateResponse
    Clarification --> [*]: Return clarification question
    
    CalculationOnly --> ValidateResponse
    
    RAGWithCalc --> ValidateResponse
    
    RAGOnly --> ValidateResponse
    
    ValidateResponse --> FormatResponse: SAFE
    ValidateResponse --> RAGWithCalc: UNSAFE (retry ≤ 2)
    ValidateResponse --> FormatResponse: Max retries exceeded
    
    FormatResponse --> [*]
```

### Node Descriptions

| Node | Responsibility | Key Logic |
|---|---|---|
| **Authenticate** | Load user profile + session data | MongoDB/dummy DB lookup, merge session |
| **DetectLanguage** | Identify query language | Library-based → LLM fallback |
| **ClassifyIntent** | Route query to correct handler | LLM classification → pattern fallback |
| **Chitchat** | Quick conversational response | Persona-driven, no computation |
| **Clarification** | Ask user to disambiguate | Detects "Mars in 7th" ambiguity |
| **CalculationOnly** | Raw chart data (no interpretation) | VedicEngine direct output |
| **RAGWithCalculation** | Personalized prediction | Chart + Dasha + Transit + RAG + LLM |
| **RAGOnly** | General astrology theory | RAG retrieval + LLM synthesis |
| **ValidateResponse** | Critic loop (safety check) | Constitution verification, max 2 retries |
| **FormatResponse** | Add disclaimers, format output | Language-appropriate formatting |

---

## 3. Module Architecture

### 3.1 Computation Layer

The bottom-most layer. **Purely deterministic** — no LLM calls, no network dependencies.

```
src/engines/
├── core/                          # Shared astronomical primitives
│   ├── ephemeris.py               # Swiss Ephemeris wrapper (pyswisseph)
│   ├── datetime_utils.py          # Julian Day ↔ datetime conversions
│   ├── coordinates.py             # GeoPosition, lat/lon handling
│   ├── celestial_bodies.py        # CelestialBody enum, planet data
│   └── exceptions.py              # Custom exception hierarchy
│
├── vedic/                         # Vedic (Sidereal) astrology
│   ├── vedic_engine.py            # Main engine: chart, lagna, positions
│   ├── rashi_nakshatra.py         # Rashi + Nakshatra calculations
│   ├── dasha_systems.py           # Vimshottari dasha periods
│   ├── aspects_yogas.py           # Aspects + yoga detection
│   ├── divisional_charts.py       # Navamsa, other D-charts
│   ├── graha_stats.py             # Shadbala (planetary strength)
│   └── vedic_constants.py         # Ayanamsa, zodiac, nakshatra data
│
└── western/                       # Western (Tropical) astrology
    ├── western_engine.py          # Main engine: tropical chart
    ├── western_aspects.py         # Aspect patterns
    ├── western_dignities.py       # Essential/accidental dignities
    ├── western_houses.py          # House systems
    └── western_signs.py           # Sign characteristics
```

**Design Principle:** The `core/` module has ZERO dependencies on other project modules. Vedic and Western engines depend only on `core/`.

### 3.2 RAG Pipeline

```
src/rag/
├── rag_engine.py           # Main RAG orchestrator (876 lines)
├── retriever.py            # Multi-strategy retriever (Semantic/BM25/Hybrid/HyDE)
├── reranker.py             # Cross-encoder reranking
├── memory_retriever.py     # Long-term conversation memory
├── ingest_local.py         # Local file ingestion utility
│
├── extraction/             # PDF → structured text
│   ├── vision_pipeline.py  # Vision LLM extraction pipeline
│   ├── vision_extractor.py # Gemini Vision API integration
│   ├── extraction_schemas.py # Extraction output schemas
│   └── extraction_prompts.py # Extraction prompt templates
│
└── preprocessing/          # Text → embeddings (6-phase)
    ├── pipeline.py         # Master preprocessing pipeline
    ├── structural_cleaner.py  # Phase 1: Clean raw text
    ├── page_analyzer.py       # Phase 2: Cross-page analysis
    ├── semantic_segmenter.py  # Phase 3: Semantic chunking
    ├── chunk_enricher.py      # Phase 4: LLM metadata enrichment
    ├── subchunker.py          # Phase 5: Sub-chunk splitting
    ├── embedder.py            # Phase 6: Embedding generation
    ├── vector_db_builder.py   # ChromaDB ingestion
    ├── schemas.py             # Pipeline data schemas
    └── book_profiler.py       # Source-specific processing config
```

**Retrieval Strategy Routing:**

```mermaid
graph LR
    Q["User Query"] --> RC["Classify Query Intent"]
    RC -->|keyword| BM25["BM25 Search"]
    RC -->|conceptual| HYDE["HyDE Search"]
    RC -->|general| HYB["Hybrid Search<br/>(RRF Fusion)"]
    BM25 --> RR["Reranker"]
    HYDE --> RR
    HYB --> RR
    RR --> EXP["Context Expansion<br/>(Adjacent Chunks)"]
    EXP --> OUT["Retrieved Chunks"]
```

### 3.3 AI / Intelligence Layer

```
src/ai/
├── intent_classifier.py    # 4-category LLM classifier with fallback
├── hybrid_retriever.py     # LangChain-compatible retriever wrapper
├── prompt_builder.py       # Dynamic prompt construction
├── persona_generator.py    # LLM-based persona generation
├── personas.py             # Pre-defined astrologer personas
└── user_manager.py         # User profile & birth data management
```

### 3.4 Safety Layer

```
src/safety/
├── classifier.py           # Multi-gate LLM safety classifier
├── input_validator.py      # Pattern-based pre-screening (Gate 1)
├── constitution.py         # Astrologer behavioral rules
├── disclaimers.py          # Domain-specific disclaimer templates
├── models.py               # SafetyDecision, BlockReasons enums
└── templates.py            # Safety prompt templates
```

**Safety Processing Pipeline:**

```mermaid
graph LR
    Q["Query"] --> G1["Gate 1<br/>Semantic Routes<br/>(Pattern Match)"]
    G1 -->|blocked| BLOCK["BLOCK<br/>(Return safe message)"]
    G1 -->|pass| G2["Gate 2<br/>LLM Classifier<br/>(Few-shot)"]
    G2 -->|SAFE| SAFE["Proceed"]
    G2 -->|DISCLAIMER| DISC["Add Disclaimer<br/>+ Proceed"]
    G2 -->|BLOCK| BLOCK
    G2 -->|REFRAME| REF["Reframe Query<br/>+ Proceed"]
```

### 3.5 API Layer

```
src/api/
├── main.py                 # FastAPI app setup, middleware, events
├── config.py               # API-specific settings (Pydantic)
├── dependencies.py         # Singleton DI (orchestrator, engines, etc.)
│
├── routes/
│   ├── chat.py             # POST /api/v1/chat
│   ├── user.py             # User management endpoints
│   ├── calculation.py      # Direct calculation endpoints
│   └── health.py           # Health check / readiness
│
├── middleware/
│   └── (timing, CORS)
│
└── schemas/
    └── user.py             # Request/response Pydantic models
```

### 3.6 Services Layer

```
src/services/
├── astrology_service.py      # 3rd-party API orchestration + caching
├── backend_data_adapter.py   # Mobile app ↔ NakshatraAI translation
└── cache_manager.py          # Redis cache with TTL management
```

---

## 4. Data Flow: Personalized Prediction

The most complex flow — `RAG_WITH_CALCULATION`:

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant IC as Intent Classifier
    participant VE as Vedic Engine
    participant R as Retriever
    participant LLM as LLM
    participant SC as Safety Classifier
    
    U->>O: "When will I get married?"
    O->>O: Authenticate (load profile)
    O->>O: Detect language
    O->>IC: Classify intent
    IC-->>O: RAG_WITH_CALCULATION
    
    O->>SC: Safety check (query)
    SC-->>O: DISCLAIMER (relationship)
    
    O->>VE: Calculate birth chart
    VE-->>O: Chart data (lagna, planets, houses)
    O->>VE: Calculate dashas
    VE-->>O: Current Mahadasha/Antardasha
    O->>VE: Calculate transits
    VE-->>O: Current planetary transits
    
    O->>R: Retrieve knowledge ("marriage timing vedic")
    R-->>O: Relevant chunks (7th house, Venus, Dasha rules)
    
    O->>LLM: Build prediction prompt<br/>(chart + dasha + transit + chunks + persona)
    LLM-->>O: Personalized interpretation
    
    O->>O: Validate response (critic loop)
    O->>O: Add relationship disclaimer
    O-->>U: Final response + disclaimer
```

---

## 5. Configuration Architecture

```mermaid
graph TB
    ENV[".env file<br/>(API keys, secrets)"] --> PYDANTIC["Pydantic Settings<br/>(EnvConfig)"]
    YAML["config/config.yaml<br/>(structured config)"] --> APPCONFIG["AppConfig<br/>(config/config.py)"]
    PYDANTIC --> APPCONFIG
    RAG_PY["config/rag_config.py<br/>(dynamic RAG tuning)"] --> RAG_ENGINE
    
    APPCONFIG --> |singleton| FACTORY["LLM Factory"]
    APPCONFIG --> |singleton| API["API Settings"]
    APPCONFIG --> |singleton| SAFETY["Safety Config"]
    APPCONFIG --> |singleton| RAG_ENGINE["RAG Engine"]
```

**Precedence:** `.env` overrides → `config.yaml` defaults → code defaults

---

## 6. LLM Provider Architecture

```mermaid
graph TB
    subgraph "LLM Factory (src/llm/factory.py)"
        FACTORY["LLMFactory.create()"]
        RL["RateLimitedLLM<br/>(Wrapper)"]
        PURPOSE["Purpose-Based<br/>Model Selection"]
    end
    
    subgraph "Providers"
        OAI["OpenAI<br/>(ChatOpenAI)"]
        OLLAMA["Ollama<br/>(ChatOllama)"]
    end
    
    subgraph "Purposes"
        GEN["general<br/>(main responses)"]
        CLASS["classification<br/>(intent, safety)"]
        SAFE["safety<br/>(content filtering)"]
    end
    
    FACTORY --> PURPOSE
    PURPOSE --> GEN
    PURPOSE --> CLASS
    PURPOSE --> SAFE
    FACTORY --> RL
    RL --> OAI
    RL --> OLLAMA
```

---

## 7. Dependency Graph

```
Orchestrator
├── IntentClassifier (src/ai/)
├── UserManager (src/ai/)
├── HybridRetriever (src/ai/)
├── PromptBuilder (src/ai/)
├── CalculationTools (src/tools/)
│   └── VedicEngine (src/engines/vedic/)
│       └── CoreEphemeris (src/engines/core/)
├── SafetyClassifier (src/safety/)
├── LLMFactory (src/llm/)
├── RAGEngine (src/rag/)
│   ├── AstrologyRetriever (src/rag/)
│   │   └── ChromaDB + BM25
│   ├── MemoryRetriever (src/rag/)
│   └── Reranker (src/rag/)
├── LanguageDetector (src/locales/)
├── ValidationEngine (src/prediction/) [optional]
└── ConversationStore (scripts/)
```

---

## 8. Deployment Architecture

```mermaid
graph TB
    subgraph "Docker Compose"
        APP["NakshatraAI App<br/>(FastAPI + Uvicorn)"]
        REDIS_D["Redis Container"]
    end
    
    subgraph "External Services"
        OPENAI_S["OpenAI API<br/>(LLM + Embeddings)"]
        OLLAMA_S["Ollama Server<br/>(Local LLM)"]
    end
    
    subgraph "Persistent Storage"
        CHROMADB["ChromaDB<br/>(data/vectordb/)"]
        SQLITE["SQLite<br/>(dev user DB)"]
        LOGS["Log Files<br/>(logs/)"]
    end
    
    APP --> REDIS_D
    APP --> OPENAI_S
    APP --> OLLAMA_S
    APP --> CHROMADB
    APP --> SQLITE
    APP --> LOGS
```

---

## 9. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Deterministic calculations over LLM** | Astronomical positions must be exact. LLMs hallucinate numbers. |
| **RAG over fine-tuning for knowledge** | Classical texts need factual accuracy. RAG provides citations. |
| **LangGraph over simple chains** | Complex 4-way routing with state needs graph-based orchestration. |
| **Multi-gate safety** | Pattern matching (fast) + LLM classification (accurate) = robust. |
| **Purpose-based LLM selection** | Classification needs speed; predictions need quality. |
| **Stateless API mode** | Mobile app pre-computes charts; chatbot interprets. Scales better. |
| **Hybrid retrieval (RRF)** | Combines semantic (meaning) + keyword (exact terms) strengths. |
| **Constitution-based critic loop** | Post-generation verification catches hallucinations and unsafe content. |

---

## 10. File Map (Complete)

```
astro_chatbot/
├── chatbot.py                      # CLI entry point
├── config/
│   ├── config.py                   # Main config loader (Pydantic + YAML)
│   ├── config.yaml                 # Base configuration
│   ├── rag_config.py               # Dynamic RAG settings
│   └── logger.py                   # Logging configuration
│
├── src/
│   ├── orchestration/
│   │   └── orchestrator.py         # LangGraph orchestrator (1,693 lines)
│   │
│   ├── ai/
│   │   ├── intent_classifier.py    # 4-category classifier
│   │   ├── hybrid_retriever.py     # LangChain retriever wrapper
│   │   ├── prompt_builder.py       # Prompt construction
│   │   ├── persona_generator.py    # Dynamic persona creation
│   │   ├── personas.py             # Pre-built personas
│   │   └── user_manager.py         # User profile management
│   │
│   ├── engines/
│   │   ├── core/                   # Swiss Ephemeris wrapper (5 files)
│   │   ├── vedic/                  # Vedic astrology engine (8 files)
│   │   └── western/                # Western astrology engine (7 files)
│   │
│   ├── rag/
│   │   ├── rag_engine.py           # Main RAG orchestrator
│   │   ├── retriever.py            # Multi-strategy retriever
│   │   ├── reranker.py             # Cross-encoder reranking
│   │   ├── memory_retriever.py     # Conversation memory
│   │   ├── extraction/             # PDF extraction (6 files)
│   │   └── preprocessing/          # Text preprocessing (11 files)
│   │
│   ├── llm/
│   │   ├── factory.py              # LLM provider factory
│   │   └── prompts/                # Prompt templates
│   │
│   ├── safety/                     # Safety & guardrails (7 files)
│   ├── api/                        # FastAPI REST API (routes, schemas)
│   ├── services/                   # Data services & caching
│   ├── tools/                      # Calculation tool wrappers
│   ├── routing/                    # Semantic router
│   ├── locales/                    # i18n (6 languages)
│   ├── prediction/                 # Validation engine
│   ├── db/                         # Database clients
│   ├── integrations/               # 3rd-party API clients
│   └── utils/                      # Cost tracking, formatting, etc.
│
├── scripts/                        # Utility scripts (6 files)
├── tests/                          # Test suite (20 files)
├── data/                           # Data directory (vectordb, profiles)
├── docs/                           # Documentation
├── Dockerfile                      # Container definition
├── docker-compose.yml              # Multi-container setup
└── requirements.txt                # Python dependencies
```