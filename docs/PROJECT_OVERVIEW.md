# NakshatraAI — Project Overview

> **Last Updated:** February 25, 2026
> **Project Name:** NakshatraAI — Expert Astrology AI Chatbot
> **Phase:** Active Development (Post-MVP)
> **Status:** 98% Production-Ready

---

## 🌟 Executive Summary

NakshatraAI is a production-grade AI-powered astrology chatbot supporting both Vedic and Western systems. It combines **deterministic astronomical calculations** (Swiss Ephemeris) with **LLM-powered interpretations** (RAG + persona-driven responses) and a robust **safety/guardrails layer**.

The system is designed for seamless integration into mobile applications, offering high-performance, validation-backed predictions in multiple Indian languages.

---

## 🚀 Core Capabilities

1.  **Birth Chart Calculations**
    - Vedic (Lahiri Ayanamsa) & Western (Tropical)
    - Divisional charts (D1-D60)
    - Vimshottari Dasha systems
    - Current transits and planetary strengths (Shadbala)

2.  **AI-Powered Interpretations**
    - RAG-based knowledge retrieval from authoritative classical texts (14,500+ chunks)
    - Context-aware predictions and timing
    - Persona-driven, conversational responses

3.  **Safety & Guardrails**
    - Multi-gate safety classifier for harmful queries
    - Third-party prediction blocking
    - Automated query reframing and conditional disclaimers

4.  **Performance & Localization**
    - 5-layer Redis caching (85% performance improvement)
    - Multilingual support for English and 6 Indian languages (Hindi, Tamil, Telugu, Kannada, Malayalam, Marathi)
    - Stateless API architecture

---

## 📊 Component Status Overview

| Component | Status | Maturity | Key Files |
|---|---|---|---|
| **Vedic Engine** | ✅ Complete | Production | `src/engines/vedic/` |
| **Western Engine** | ✅ Complete | Production | `src/engines/western/` |
| **Core Ephemeris** | ✅ Complete | Production | `src/engines/core/` |
| **Orchestrator** | ✅ Complete | Production | `src/orchestration/orchestrator.py` |
| **RAG Engine** | ✅ Complete | Production | `src/rag/rag_engine.py` |
| **Safety System** | ✅ Complete | Production | `src/safety/` |
| **FastAPI REST API** | ✅ Complete | Production | `src/api/` |
| **Caching Layer** | ✅ Complete | Production | `src/services/cache_manager.py` |
| **Validation Engine** | 🔄 In Progress | Beta | `src/prediction/vedic_validation_engine_v2.py` |
| **Fine-tuning** | 📋 Planned | - | Dataset preparation phase |

---

## 🎯 What's Working (End-to-End)

- ✅ **CLI Chatbot**: Full conversational flow via `chatbot.py`.
- ✅ **REST API**: Production-ready endpoints for chat, calculations, and user management.
- ✅ **Smart Routing**: 4-way intent classification (Chitchat, Calculation, RAG+Calc, RAG-Only).
- ✅ **Knowledge Retrieval**: Hybrid semantic/keyword search across classical astrology books.
- ✅ **Multilingual Support**: High-quality responses in multiple native scripts and Hinglish.

---

## 🗓️ Roadmap & Next Steps

### Immediate Focus
- **Refinement**: Fine-tuning validation rules (~92 MB JSON datasets).
- **Optimization**: Finalizing tier classification and rule indexing for sub-500ms validation.

### Long-term Goals
- **Fine-tuning**: Training LoRA/QLoRA models on validated astrological interpretations.
- **Production Monitoring**: Implementing advanced observability and user feedback loops.
- **KP System**: Future support for Krishnamurti Padhdhati (KP) astrology.

---

## 📂 Key Entry Points

- **CLI Chatbot**: `python chatbot.py`
- **API Server**: `uvicorn src.api.main:app --reload`
- **Developer Guide**: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
