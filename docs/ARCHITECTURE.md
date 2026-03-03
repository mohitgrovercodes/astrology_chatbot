# NakshatraAI — Master System Architecture

> **Last Updated:** February 2026 (Post-Redis permanent storage & Post-UX fixes)
> **Status:** Production Architecture

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Flow & Lifecycle](#data-flow--lifecycle)
3. [Calculation Engines (Vedic & Western)](#calculation-engines-vedic--western)
4. [RAG Pipeline](#rag-pipeline)
5. [Orchestrator & Validation](#orchestrator--validation)
6. [Safety Framework](#safety-framework)
7. [Caching & State Architecture](#caching--state-architecture)

---

## Architecture Overview

**NakshatraAI** is a production-grade AI-powered astrology chatbot backing a mobile application via FastAPI. It fuses deterministic astronomical calculations (Swiss Ephemeris) with dynamic AI interpretation.

### Core Design Principles
1. **Determinism over Probability** - Hard calculations (charts, transits) are done in Python, never guessed by the LLM.
2. **Safety-First** - Multi-tiered guardrails exist before a prompt reaches the main LLM. 
3. **Stateless Scalability** - Shared Redis instance stores permanent data ensuring context continuity.
4. **Authoritative Knowledge** - LLM interpretations are heavily grounded using Retrieval-Augmented Generation (RAG) over classical astrological texts like BPHS.

---

## Data Flow & Lifecycle

```
User Query from Mobile App
    ↓
┌─────────────────────────────────────────────┐
│  FastAPI Layer & Session Match               │
│  - Loads or rejects `/initialize` request    │
│  - `/message` enters Orchestrator            │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  Orchestration (LangGraph `orchestrator.py`) │
│  - Check Intent (ChitChat vs Prediction)     │
│  - Language Detection (Multilingual routing) │
│  - Safety Gate (Multi-stage blocking)        │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  Calculations + RAG + Validation             │
│  - Calculate Chart via engines (if needed)   │
│  - Hybrid BM25+Vector text retrieval         │
│  - Run astrological rules validation engine  │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  LLM Synthesis                               │
│  - Feed charts, dasha, transits to LLM       │
│  - Add RAG chunks, rules, and chat history   │
│  - Generate, append disclaimers, localize    │
└─────────────────────────────────────────────┘
    ↓
Response to Mobile App
```

---

## Calculation Engines (Vedic & Western)

The system enforces accurate planetary math using `pyswisseph` (Swiss Ephemeris).

### Vedic Engine (`src/engines/vedic/`)
- Uses **Sidereal** Zodiac with Lahiri (Chitrapaksha) Ayanamsa.
- Generates base planetary positions, **D1-D60 Divisional Charts** (calculated theoretically, integration pending).
- Evaluates **Vimshottari Dasha**. Dasha is mapped by Mahadasha, Antardasha, and Pratyantardasha.
- Evaluates Yoga detections (Raj Yoga, Dhana Yoga, etc) and Dignity Strengths (Exaltation/Debilitation).

### Western Engine (`src/engines/western/`)
- Uses **Tropical** Zodiac. 
- Analyzes Houses (Placidus, Koch, Whole Sign, Equal).
- Evaluates Major/Minor aspects with configurable orbs (Conjunction, Trine, Square, Quincunx, etc).
- Evaluates Essential Dignities (Rulership, Exaltation, Detriment, Fall).

---

## RAG Pipeline

The Retrieval-Augmented Generation system prevents hallucinations on astrology philosophy or timing techniques by injecting specific shlokas into the LLM context.

1. **Extraction**: PDFs are processed through Gemini Vision (with `gemini-2.5-flash-lite` being the primary high-speed extractor, defaulting to `gemini-2.5-pro` on low confidence).
2. **Preprocessing & Segmentation**: Structural cleaning normalizes texts. An LLM profiles the book intelligently and segments the texts based on semantic boundaries/verse markers (e.g. `॥ 42 ॥`).
3. **Enrichment**: Each chunk generates a summary and extracts named entities (Planets, Houses).
4. **Vector Store**: Over 14,000 chunks embedded using OpenAI (`text-embedding-3-large`) into ChromaDB (`data/vectordb`).
5. **Retrieval Engine**: Employs **Hybrid Search (BM25 + Semantic Vector, 30/70 split)** for entity/topic hits. Supports HyDE for conceptual queries, combined with Metadata-based reranking.

---

## Orchestrator & Validation

NakshatraAI uses LangGraph to construct a deterministic state machine for conversations (`src/orchestration/orchestrator.py`).
- **Intent Classifier**: Parses the user query to route between `CHITCHAT`, `CALCULATION_ONLY`, `RAG_ONLY`, or `RAG_WITH_CALCULATION`.
- **Validation Engine**: Evaluates prediction requests against 750+ JSON-configured rules (e.g., checking if the 7th Lord genuinely supports a marriage query before enabling the LLM to speak). Returns a strength score. 

---

## Safety Framework

A robust Multi-Gate Safety system prevents the bot from rendering dangerous or unethical astrology.
- **Gate -1 (Own-Data Detection)**: Identifies if the user is asking about their own chart.
- **Gate 0 (Third-Party Detection)**: Automatically SOFT-blocks inquiries into other people's lives ("When will my friend die?").
- **Gate 1 (Semantic Routing)**: Prevents medical/legal/death prediction attempts.
- **Gate 2 (LLM Classifier)**: Evaluates nuances, enforces REFLECTION schemas to subtly pivot a question (e.g., turns "Will I divorce?" to "What do planetary periods indicate about my relationship dynamic?").

---

## Caching & State Architecture

To allow seamless mobile app interaction even after weeks of inactivity, data strictly defaults to **Permanent Storage**. TTLs are removed for essential user data.

1. **User Profile**: `redis.set()` — Permanent. Birth date, time, location.
2. **Birth Chart**: `redis.set()` — Permanent. Birth geometry never changes.
3. **Conversation State**: `redis.set()` — Permanent. A sliding window of the last 10 messages is preserved, with summarizes triggered every 10 items.
4. **Transits Data**: Controlled centrally in `config.py` as `TRANSIT_REFRESH_HOURS=24`. On data retrieval, the app triggers a recompute if the payload's `stored_at` timestamp is stale.
5. **Dasha Data**: Controlled centrally in `config.py` as `DASHA_REFRESH_DAYS=30`. Antardasha changes slowly, auto-recomputes on read if older than 30 days.

*This application-level eviction model ensures Redis doesn't blindly prune data for inactive users while guaranteeing astronomically correct transits/periods when those users return.*