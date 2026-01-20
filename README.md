# Astrology AI Chatbot

An expert-level Astrology Chatbot supporting **Vedic and Western Astrology**, built with LangChain, LangGraph, and RAG.

## Features

- 🔮 **Birth Chart Calculations** - Accurate planetary positions using pyswisseph
- 🌟 **Vedic & Western Astrology** - Support for both systems
- 🤖 **AI-Powered Interpretations** - LLM + RAG for expert-level readings
- 🔄 **Multi-Provider LLM Support** - OpenAI, Google, Anthropic, xAI
- 🛡️ **Safety Guardrails** - Blocks harmful predictions
- 🚀 **Production-Ready API** - FastAPI with async support

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Mobile App                      │
└────────────────────┬────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────┐
│              FastAPI + Pydantic                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           LangGraph Orchestration                │
│  Intent → Safety → Router → Response Synthesis   │
└───────┬─────────────────────────────┬───────────┘
        │                             │
┌───────▼───────┐           ┌─────────▼──────────┐
│  Calculation  │           │   RAG Pipeline     │
│    Engine     │           │  ChromaDB + OpenAI │
│  (pyswisseph) │           │    Embeddings      │
└───────────────┘           └────────────────────┘
```

## Quick Start

### 1. Clone and Setup

```bash
cd astro_chatbot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run the API (after development is complete)

```bash
uvicorn src.api.main:app --reload
```

## Project Structure

```
astro_chatbot/
├── src/
│   ├── api/            # FastAPI routes
│   ├── engine/         # Astrology calculation engine wrapper
│   ├── rag/            # Document ingestion & retrieval
│   ├── orchestration/  # LangGraph workflow
│   ├── safety/         # Content guardrails
│   └── utils/          # Config, logging utilities
├── data/
│   ├── raw/            # Astrology texts for RAG
│   └── vectordb/       # ChromaDB persistence
├── config/
│   └── config.yaml     # Application configuration
├── tests/              # Unit and integration tests
├── .env.example        # Environment template
└── requirements.txt    # Dependencies
```

## Configuration

### LLM Providers

The chatbot supports multiple LLM providers. Set your preferred provider in `.env`:

| Provider | Env Variable | Models |
|----------|--------------|--------|
| OpenAI | `OPENAI_API_KEY` | gpt-4o, gpt-4o-mini |
| Google | `GOOGLE_API_KEY` | gemini-1.5-pro, gemini-1.5-flash |
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
| xAI | `XAI_API_KEY` | grok-2, grok-2-mini |

### Embeddings

Embeddings are fixed to OpenAI's `text-embedding-3-large` for consistency.

## Development Phases

- [x] Phase 1: Foundation (config, logging, LLM factory)
- [ ] Phase 2: Engine Integration
- [ ] Phase 3: RAG Pipeline
- [ ] Phase 4: LLM Integration
- [ ] Phase 5: LangGraph Orchestration
- [ ] Phase 6: Safety & Guardrails
- [ ] Phase 7: API Layer
- [ ] Phase 8: Testing & Evaluation
- [ ] Phase 9: Fine-Tuning
- [ ] Phase 10: Deployment

## Key Principles

```
CALCULATIONS = Deterministic (Python/pyswisseph, no LLM)
INTERPRETATIONS = LLM + RAG (no hardcoded rules)
```

## Safety

The chatbot includes guardrails for:
- ❌ Death timing predictions
- ❌ Medical diagnosis/treatment
- ❌ Gambling/lottery advice
- ❌ Legal advice

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
