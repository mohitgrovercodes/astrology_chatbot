<!-- docs\ARCHITECTURE.md -->
# NakshatraAI Architecture V2 - Simplified + LangGraph

**Date:** February 6, 2026
**Version:** 2.2 (Including Phase 11 Semantic Routing)
**Status:** In Production / Scaling Phase

---

## 🎯 Core Philosophy

### The Problem with V1

**Too Many Intent Categories:**
```
V1: 7 categories
├─ GREETING
├─ OFF_TOPIC
├─ UNCLEAR
├─ CALCULATION
├─ INTERPRETATION
├─ PREDICTION
└─ LEARNING
```

**Issues:**
- Unclear boundaries (PREDICTION vs INTERPRETATION?)
- Complex routing logic
- Harder to maintain
- Doesn't map to system capabilities

### The Solution: V2

**3 Categories Matching System Capabilities:**
```
V2: 3 categories (capability-based)
├─ CHITCHAT          → Conversational response
├─ NEEDS_CALCULATION → Deterministic engine
└─ NEEDS_RAG         → Knowledge + LLM
```

**Benefits:**
- Clear boundaries
- Maps directly to what the system can do
- Simpler routing
- Easier to maintain

---

## 🔄 Why LangGraph?

### V1 Mistake: Not Using LangGraph Properly

We had an `orchestrator.py` that was just a **Python class with methods**:
```python
class NakshatraAI:
    def process_query(self):
        intent = self.classify()
        if intent == "GREETING":
            return self.handle_greeting()
        elif intent == "PREDICTION":
            return self.handle_prediction()
        # ... manual routing
```

**Problems:**
- Not leveraging LangGraph's state management
- Manual routing logic
- Hard to visualize flow
- No built-in state tracking

### V2: Proper LangGraph StateGraph

Now we use LangGraph's **StateGraph** as designed:
```python
workflow = StateGraph(NakshatraState)

# Add nodes
workflow.add_node("authenticate", authenticate_fn)
workflow.add_node("classify_intent", classify_fn)
workflow.add_node("handle_chitchat", chitchat_fn)
workflow.add_node("handle_calculation", calc_fn)
workflow.add_node("handle_rag", rag_fn)

# Conditional routing
workflow.add_conditional_edges(
    "classify_intent",
    route_by_intent,
    {
        "chitchat": "handle_chitchat",
        "calculation": "handle_calculation",
        "rag": "handle_rag"
    }
)
```

**Benefits:**
- Proper state management
- Visual graph structure
- Built-in state tracking
- LangGraph handles execution
- Easier to debug and extend

---

## 🏗️ System Architecture

### High-Level Flow

```
User Query
    ↓
[LangGraph StateGraph]
    ↓
┌─────────────────┐
│ 1. Authenticate │ → Load user profile from MongoDB
└────────┬────────┘
         ↓
┌─────────────────┐
│ 2. Classify     │ → CHITCHAT | NEEDS_CALCULATION | NEEDS_RAG
│    Intent       │    (Semantic Router + LLM Fallback)
└────────┬────────┘
         ↓
    [Router]
         ↓
    ┌────┴────┐
    ↓    ↓    ↓
┌────────┐ ┌────────────┐ ┌─────────┐
│Chitchat│ │Calculation │ │   RAG   │
│Handler │ │Handler     │ │Handler  │
│        │ │            │ │         │
│Quick   │ │pyswisseph  │ │Retrieve │
│Response│ │Engine      │ │+        │
│        │ │            │ │Generate │
└───┬────┘ └─────┬──────┘ └────┬────┘
    └──────┴───────────────────┘
                ↓
    ┌───────────────────┐
    │ 4. Format Response│
    └──────────┬────────┘
               ↓
          Final Answer
```

### Detailed Component View

```
┌────────────────────────────────────────────────────────┐
│           MOBILE APP (Your Existing App)               │
└──────────────────────┬─────────────────────────────────┘
                       │ REST API
┌──────────────────────▼─────────────────────────────────┐
│              FASTAPI LAYER (Phase 7)                   │
│              POST /chat                                │
└──────────────────────┬─────────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────────┐
│         LANGGRAPH ORCHESTRATOR (V2)                    │
│                                                        │
│  StateGraph with 6 nodes:                             │
│  ┌──────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │Authenticate│→│Classify     │→│Route by     │      │
│  │           │ │Intent       │ │Intent       │      │
│  └──────────┘  └─────────────┘  └─────────────┘      │
│                                        ↓              │
│       ┌─────────────┬──────────────────┴─────────┐    │
│       ↓             ↓                            ↓    │
│  ┌────────┐   ┌─────────────┐   ┌──────────────┐    │
│  │Chitchat│   │Calculation  │   │RAG           │    │
│  └────────┘   └─────────────┘   └──────────────┘    │
│       └─────────────┬──────────────────┬─────────┘    │
│                     ↓                                 │
│            ┌─────────────────┐                        │
│            │Format Response  │                        │
│            └─────────────────┘                        │
└────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┴────────────────┐
        ↓                               ↓
┌───────────────┐            ┌──────────────────────┐
│CALCULATION    │            ┌──────────────────────┐
│ENGINE         │            │RAG PIPELINE          │
│               │            │                      │
│• pyswisseph   │            │┌────────────────┐    │
│• Birth Charts │            ││Hybrid Retrieval│    │
│• Dashas       │            ││                │    │
│• Transits     │            ││Semantic+BM25   │    │
│               │            ││+HyDE           │    │
│(Your existing │            │└────────────────┘    │
│ engines)      │            │        ↓             │
└───────────────┘            │┌────────────────┐    │
                             ││ChromaDB        │    │
                             │└────────────────┘    │
                             └──────────────────────┘
                                       │
                            ┌──────────▼──────────┐
                            │LLM GENERATION       │
                            │                     │
                            │Gemini 2.5 Flash     │
                            │(Primary)            │
                            └─────────────────────┘
```

---

## 📚 RAG Preprocessing Pipeline (8-Phase Discovery)

To achieve high-precision astrology retrieval, we implemented a sophisticated **Preprocessing Pipeline** that moves beyond fixed-length chunking.

### The 8-Phase Workflow

| Phase | Name | Responsibility |
| :--- | :--- | :--- |
| **P1** | Extraction | Vision-LLM based PDF-to-Markdown extraction |
| **P2** | Cleaning | Structural normalization and noise removal |
| **P3** | Analysis | Cross-page continuity and chapter detection |
| **P3.5**| **Profiling** | **Automated Structural Discovery (LLM)** |
| **P4** | **Segmentation**| **Profile-Aware Semantic Chunking** |
| **P5** | Enrichment | Summary, Entity Extraction (Planets/Houses) |
| **P6** | Embedding | Multi-vector indexing (OpenAI Large) |
| **P7** | Ingestion | Vector Database persistence (ChromaDB) |

### Key Innovation: Structural Discovery (Phase 3.5)
The system is **Book-Agnostic**. Before splitting a book, it uses an LLM to "read" representative samples and identify:
- **Verse Patterns**: Regex for shloka markers (e.g. `॥ 42 ॥`).
- **Semantic Markers**: Transition keywords (e.g. `"Sage Parasara said"`, `"Note:"`).
- **Hierarchy**: Logical nesting of chapters, verses, and commentaries.

### Semantic Segmentation (Phase 4)
We use a **Hierarchical Splitter** instead of a token-limited one:
1. **Hard Breaks**: Page/Chapter boundaries.
2. **Context markers**: Discovered transition phrases.
3. **Soft breaks**: Sentence boundaries (respecting Sanskrit punctuation).
4. **Context Injection**: Each split chunk inherits a "Context Header" to prevent meaning fragmentation.

---

## 🧠 Semantic Routing (Phase 11 Update)

We replaced the brittle Regex/Keyword matching system with a **Semantic AI Router**.

### Technical Architecture
- **Engine**: `sentence-transformers/all-MiniLM-L6-v2`
    - **Size**: ~80MB (Quantized)
    - **Latency**: <50ms on CPU
    - **Location**: Runs locally in `src/routing/` (No API calls required)
- **Component**: `SemanticRouter` (Singleton pattern in `src/routing/semantic_router.py`)
- **Mechanism**: Cosine Similarity between `Query Embedding` and `Route Canonical Embeddings`.

### Configured Routes

**1. Chitchat (`orchestrator.py`)**
- **Threshold**: 0.70
- **Examples**: "wassup", "sup", "namaste", "vanakkam".
- **Impact**: Catches slang and variations that regex missed.

**2. Safety (`classifier.py`)**
- **Threshold**: 0.75
- **Categories**: DEATH_PREDICTION, MEDICAL, GAMBLING, HARMFUL, PRIVACY.
- **Impact**: Robust detection of harmful intent without needing exhaustive keyword lists. (e.g., "end my life" is caught even without "suicide" keyword).

---

## 🌐 Multilingual Architecture (Phase 6.2)

We enforce a **Strict 8-Language Lockdown** to prevent hallucinated languages and response drift.

### 1. The 8 Supported Languages
The system strictly parses inputs into one of these 8 codes. All else falls back to English.
1. **English** (`en`)
2. **Hindi** (`hi`) + **Hinglish** (`hi-lat`)
3. **Marathi** (`mr`) + **Romanized** (`mr-lat`)
4. **Punjabi** (`pa`) + **Romanized** (`pa-lat`)
5. **Tamil** (`ta`) + **Romanized** (`ta-lat`)
6. **Telugu** (`te`) + **Romanized** (`te-lat`)
7. **Malayalam** (`ml`) + **Romanized** (`ml-lat`)

### 2. Roman Script Handling (`-lat`)
We use a **Single-Source-Locale** strategy:
- **Detection**: `LanguageDetector` identifies Romanized text (e.g., "Kasa ahe?") -> Returns `mr-lat`.
- **Loading**: `LocalizationManager` loads the **Base JSON** (`mr.json`).
- **Instruction**: `PromptBuilder` injects: *"Respond in Marathi using Roman Script"*.
- **Benefit**: No duplicate `*-lat.json` files required. 8 files cover 14 variants.

### 3. Drift Prevention (RAG)
To prevent Cross-Lingual Contamination (e.g., English query getting Marathi chunks):
- **Filter**: `language IN [detected_code, 'en']`
- **Logic**: English (`en`) is always retrieved as the "Universal Knowledge Hub".
- **Result**: Users get answers in their requested language/script without random language switching.

---

## 📊 Intent Classification Logic

### The 3 Categories Explained

#### 1. CHITCHAT
**Definition:** General conversation that doesn't need astrology knowledge or calculations.
**Processing:** < 100ms (Semantic Route or Fallback ID)

#### 2. NEEDS_CALCULATION
**Definition:** User wants to GENERATE or CALCULATE specific astrological data.
**Examples:** "Calculate my birth chart", "Show my dasha"
**Response:** Deterministic engine (pyswisseph)
**Processing:** 500ms - 2s

#### 3. NEEDS_RAG
**Definition:** User wants astrological KNOWLEDGE, INTERPRETATION, or PREDICTION.
**Examples:** "What does Jupiter mean?", "When will I get married?"
**Response:** Hybrid retrieval + LLM
**Processing:** 3-5s

---

## 🎯 Routing Decision Tree

```
Query arrives
    ↓
[Semantic Router] Check Chitchat/Safety (Latency < 50ms)
    ├─ Match? → Return Result Immediately
    └─ No Match ↓
[LLM Classification] Check Intent (Latency ~800ms)
    ├─ Calculation? → NEEDS_CALCULATION
    └─ Knowledge? → NEEDS_RAG
```

**Rule:** Semantic Routing takes precedence for speed and safety. LLM Classification handles the nuance between Calculation and RAG.

---

## 📈 Performance Characteristics

| Path | Avg Time | Bottleneck |
|------|----------|------------|
| CHITCHAT (Semantic) | <50ms | None |
| CHITCHAT (LLM) | ~800ms | LLM Latency |
| NEEDS_CALCULATION | 1-2s | pyswisseph computation |
| NEEDS_RAG | 3-5s | Retrieval + Generation |

**Optimization Strategy:**
- **Semantic First**: Offload 30-40% of queries (greetings, safety) to local embedding model.
- **Caching**: Cache RAG intents and calculation results.

---

## 📋 Next Steps

### Immediate (Phase 12)
- [ ] Implement FastAPI layer (replace CLI)
- [ ] Containerize with Docker (include sentence-transformers model)

### Long-term
- [ ] Add analytics nodes for router performance
- [ ] Fine-tune RAG model on astrology texts