# 🌟 Astrology AI Chatbot

> **Production-grade AI conversational system for Vedic and Western Astrology**  
> Combining deterministic astronomical calculations with LLM-powered interpretations

[![Status](https://img.shields.io/badge/status-production--ready-brightgreen)]()
[![Progress](https://img.shields.io/badge/progress-82%25-blue)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-proprietary-red)]()

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Documentation](#documentation)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

---

## 🎯 Overview

An expert-level **Astrology AI Chatbot** designed for integration into mobile applications. The system provides:

- ✅ **Vedic Astrology** calculations and interpretations
- ✅ **Western Astrology** support
- ✅ **User authentication** with subscriber-only access
- ✅ **Automatic birth data loading** from user profiles
- ✅ **Classical text-grounded interpretations** via RAG
- ✅ **Automated Book Profiling** (Structural DNA discovery)
- ✅ **8-Phase Preprocessing Pipeline** for high-precision data
- ✅ **Intelligent orchestration** using LangGraph
- ✅ **Personalized experience** with conversation memory
- ✅ **Safety & Ethics Guardrails** (Professional-style disclaimers)

### Core Principle

```
CALCULATIONS = Deterministic (pyswisseph engine)
INTERPRETATIONS = LLM + RAG (classical texts)
ORCHESTRATION = LangGraph (state machine)
```

---

## ✨ Features

### 🔢 Astrological Calculations

- **Vedic System**
  - Complete birth charts (Lagna, Rashi, Nakshatras)
  - Vimshottari Dasha periods (Maha, Antar, Pratyantar)
  - Divisional charts (D1-D60)
  - Yogas detection (Raja Yoga, Dhana Yoga, etc.)
  - Transit analysis
  - Aspects and planetary strengths

- **Western System**
  - Natal charts (Sun, Moon, Ascendant)
  - House placements (Placidus, Whole Sign, etc.)
  - Aspects (conjunction, opposition, trine, square, sextile)
  - Essential dignities (domicile, exaltation, detriment, fall)

### 💬 Conversational AI

- **Natural Language Understanding**
  - Intent classification (calculation vs interpretation)
  - Follow-up question handling
  - Context-aware responses
  
- **Persona System**
  - Hybrid Traditional-Modern (default)
  - Vedic Classical (strictly traditional)
  - Modern Educational (teaching-focused)
  - Western Psychological

- **Knowledge Grounding**
  - RAG from classical texts (BPHS, Jataka Parijata)
  - Source citations
  - No hallucinated interpretations

### 🔐 User Management

- **Authentication**
  - Subscriber verification
  - Trial user support
  - Graceful access denial for expired/free accounts
  
- **Profile Management**
  - Auto-load birth data from database
  - No repeated data entry
  - Personalized greetings
  - Preference storage (Vedic/Western, language)

### 🛡️ Safety & Ethics

- **Built-in Guardrails**
  - Blocks death timing predictions
  - Blocks medical diagnosis queries
  - Blocks gambling/lottery predictions
  - Blocks legal advice requests
  
- **Ethical Responses**
  - Respectful denials
  - Alternative suggestions
  - Appropriate disclaimers

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MOBILE APP                           │
│               (Future: REST API)                        │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│              CHATBOT INTERFACE                          │
│          (chatbot_phase5_1.py)                          │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│            USER MANAGER                                 │
│  • Authenticate subscription                            │
│  • Load user profile                                    │
│  • Auto-populate birth data                             │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│         LANGGRAPH ORCHESTRATOR                          │
│  0. Load Profile → Authenticate                         │
│  1. Classify Intent → calculation/interpretation        │
│  2. Safety Check → Block harmful queries               │
│  3. Extract Data → Profile or query                    │
│  4. Calculate → Use engines                            │
│  5. Retrieve Knowledge → RAG                           │
│  6. Synthesize → Combine results                       │
└─────┬──────────────────────────┬────────────────────────┘
      │                          │
      ↓                          ↓
┌─────────────────┐    ┌────────────────────┐
│ Calculation     │    │ RAG Engine         │
│ Tools           │    │ • ChromaDB         │
│ • Vedic         │    │ • OpenAI Embeddings│
│ • Western       │    │ • Persona System   │
│ • Transits      │    │ • Classical Texts  │
└────────┬────────┘    └────────────────────┘
         │
         ↓
┌────────────────────────────────────┐
│   YOUR CALCULATION ENGINES         │
│   • vedic_engine.py                │
│   • western_engine.py              │
│   • pyswisseph integration         │
└────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- pip package manager
- **Choose ONE provider:**
  - **Google Cloud (Vertex AI) - RECOMMENDED**
    - Service Account JSON key
    - Enabled Vertex AI API
  - **OpenAI**
    - API Key (sk-...)
- **MongoDB** (Local or Atlas) for user storage

### Installation

```bash
# Clone repository
git clone <repository-url>
cd astro-chatbot

# Install dependencies
pip install -r requirements.txt --break-system-packages

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Basic Usage

```bash
# Run authenticated chatbot (development mode with dummy users)
python chatbot_phase5_1.py

# Select a test user:
# 1. Arjun Kumar (user001) - Active Premium
# 2. Priya Sharma (user002) - Active Basic
# 3. Rahul Verma (user003) - Expired [Will be blocked]
# 4. Sophia Anderson (user004) - Active Premium (Western)

# Or specify user directly
python chatbot_phase5_1.py --user user001
```

### Example Interaction

```
Welcome Arjun! 👋
I have your birth details from your profile.
✓ Birth data on file: Jaipur, Rajasthan, India

🔮 You: Calculate my birth chart

🤔 Processing...

═══════════════════════════════════════════════════════════
✨ ANSWER
═══════════════════════════════════════════════════════════
📊 Your Chart Calculation

**Lagna (Ascendant):** Gemini
**Rashi (Moon Sign):** Taurus
**Sun Sign:** Pisces
**Moon Nakshatra:** Rohini

**Current Dasha Periods:**
  • Mahadasha: Venus
  • Antardasha: Saturn
  • Pratyantardasha: Mercury

**Key Planetary Positions:**
  • Sun: Pisces, 10th house
  • Moon: Taurus, 12th house
  • Mars: Capricorn, 8th house
  • Mercury: Pisces, 10th house
  • Jupiter: Cancer, 2nd house
═══════════════════════════════════════════════════════════

🔮 You: What does my Moon in Taurus mean?

[Retrieves interpretation from classical texts...]
```

---

## 📦 Installation

### Step 1: System Requirements

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3-pip

# macOS
brew install python@3.10
```

### Step 2: Python Dependencies

```bash
# Core dependencies
pip install langchain langchain-core langchain-openai --break-system-packages
pip install langchain-google-genai langchain-anthropic --break-system-packages
pip install langgraph langchain-chroma chromadb --break-system-packages
pip install pyswisseph python-dateutil pydantic --break-system-packages

# Or install from requirements.txt
pip install -r requirements.txt --break-system-packages
```

### Step 3: Configuration

```bash
# Set up environment file
cp .env.example .env

# Edit .env with your configuration:
# ----------------------------------
# LLM Providers
OPENAI_API_KEY=your-openai-key-here
GOOGLE_API_KEY=your-google-key-here

# Google Cloud (If using Vertex AI)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
GOOGLE_CLOUD_PROJECT=your-project-id

# Default LLM
DEFAULT_LLM_PROVIDER=google
DEFAULT_LLM_MODEL=gemini-2.5-flash

# MongoDB
MONGODB_URI=mongodb://localhost:27017/astro_data
```

### Step 4: Run the API (Phase 7)

```bash
# Start the FastAPI server
uvicorn src.api.main:app --reload

# Documentation available at:
# http://localhost:8000/api/docs
```
```

### Step 4: Verify Installation

```bash
# Test user authentication
python user_manager.py
# Expected: All tests pass ✅

# Test calculation tools
python calculation_tools.py
# Expected: Chart calculations work ✅

# Test orchestrator
python orchestrator.py
# Expected: All queries processed ✅
```

---

## 💡 Usage

### Command-Line Interface

```bash
# Interactive mode (select user from menu)
python chatbot_phase5_1.py

# Specify user directly
python chatbot_phase5_1.py --user user001

# Resume existing session
python chatbot_phase5_1.py --user user001 --session abc-123-def

# Disable conversation storage
python chatbot_phase5_1.py --user user001 --no-storage
```

### Available Commands

```
/help       Show help message
/profile    View your birth data and preferences
/history    View conversation history
/clear      Clear conversation history (new session)
/quit       Exit chatbot
```

### Test Users (Development)

| User ID | Name | Subscription | Birth Data | Location |
|---------|------|--------------|------------|----------|
| `user001` | Arjun Kumar | Active Premium | ✅ Complete | Jaipur, India |
| `user002` | Priya Sharma | Active Basic | ✅ Complete | Mumbai, India |
| `user003` | Rahul Verma | Expired | ✅ Complete | Delhi, India |
| `user004` | Sophia Anderson | Active Premium | ✅ Complete | New York, USA |
| `user005` | Guest User | Free | ❌ No data | N/A |

### Example Queries

**Calculations:**
```
Calculate my birth chart
Show me my current dasha
What are the transits today?
Calculate my western chart
```

**Interpretations:**
```
What does Jupiter in 5th house mean?
Explain the concept of Rahu-Ketu
What is Raja Yoga?
How does Moon in Taurus affect personality?
```

**Follow-ups:**
```
You: What is Mars?
Bot: [Explains Mars]

You: What about in the 7th house?
Bot: [Understands context, explains Mars in 7th]
```

---

## 📁 Project Structure

```
astro-chatbot/
├── src/
│   ├── engines/               # Calculation engines
│   │   ├── core/              # Base ephemeris, coordinates
│   │   ├── vedic/             # Vedic astrology
│   │   └── western/           # Western astrology
│   │
│   ├── llm/                   # LLM components
│   │   ├── prompts/           # Personas & templates
│   │   └── factory.py         # Multi-provider LLM factory
│   │
│   ├── rag/                   # RAG pipeline
│   │   ├── rag_engine.py      # Main RAG orchestrator
│   │   ├── retriever.py       # ChromaDB retrieval
│   │   └── reranker.py        # Result reranking
│   │
│   ├── tools/                 # LangChain tools
│   │   └── calculation_tools.py
│   │
│   └── orchestration/         # LangGraph orchestrator
│       └── orchestrator.py
│
├── data/
│   ├── raw/                   # Source texts (PDFs)
│   ├── vectordb/              # ChromaDB storage
│   └── conversations/         # Session storage (JSON)
│
├── tests/                     # Test suites
│   ├── test_personas_standalone.py
│   └── test_prompt_system.py
│
├── user_manager.py            # User authentication
├── conversation_store.py      # Storage abstraction
├── chatbot_phase5_1.py        # Main chatbot interface
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── README.md                  # This file
└── ASTRO_CHATBOT_PROJECT_STATUS.md  # Detailed status
```

---

## 🛠️ Technology Stack

### Core Framework
- **Python 3.10+**
- **LangChain** - LLM orchestration framework
- **LangGraph** - State machine for conversation flow

### LLM & Embeddings
- **OpenAI** - GPT-4, text-embedding-3-large
- **Google Gemini** - Gemini 2.0 Flash/Pro
- **Anthropic Claude** - Claude Sonnet 4
- **xAI** - Grok (alternative)

### Vector Database
- **ChromaDB** - Vector storage and retrieval
- **OpenAI Embeddings** - text-embedding-3-large (3072 dimensions)

### Calculation Engine
- **pyswisseph** - Swiss Ephemeris (astronomical calculations)
- Custom Vedic & Western engines

### Storage
- **Development:** JSON files
- **Production:** MongoDB (ready)

### Future Additions
- **FastAPI** - REST API layer (Phase 6)
- **Docker** - Containerization
- **Kubernetes** - Orchestration

---

## 📚 Documentation

### Core Documentation
- **[README.md](README.md)** - This file (overview & quick start)
- **[PROJECT_STATUS.md](ASTRO_CHATBOT_PROJECT_STATUS.md)** - Detailed progress report
- **[PHASE5_COMPLETE.md](PHASE5_COMPLETE.md)** - Orchestration details
- **[PHASE5_1_COMPLETE.md](PHASE5_1_COMPLETE.md)** - User authentication guide
- **[PHASE5_QUICK_START.md](PHASE5_QUICK_START.md)** - 15-minute deployment
- **[PHASE4_COMPLETE.md](PHASE4_COMPLETE.md)** - Persona system documentation

### API Documentation (Future)
- Swagger UI (after Phase 6)
- OpenAPI specification
- Endpoint reference

### Code Documentation
- Docstrings in all modules
- Type hints throughout
- Inline comments for complex logic

---

## 🧪 Testing

### Run All Tests

```bash
# Test user authentication
python user_manager.py
# Expected: 6/6 tests pass

# Test personas
python tests/test_personas_standalone.py
# Expected: 58/61 tests pass (95%)

# Test calculation tools
python calculation_tools.py
# Expected: All tools execute successfully

# Test orchestrator
python orchestrator.py
# Expected: 4 test queries processed correctly
```

### Test Coverage

- **User Authentication:** 100% ✅
- **Persona System:** 95% ✅ (3 edge cases documented)
- **Calculation Tools:** 100% ✅
- **Orchestration:** 100% ✅ (manual testing)
- **RAG Pipeline:** 95% ✅

### Test Data

**5 dummy users** for development testing:
- Active subscribers (user001, user002, user004)
- Expired subscription (user003)
- Free account (user005)

---

## 🗺️ Roadmap

### ✅ Completed (85%)

- [x] Phase 1: Foundation
- [x] Phase 2: Engine Integration
- [x] Phase 3: RAG Pipeline
- [x] Phase 4: LLM Integration (Personas, Templates)
- [x] Phase 5: Orchestration (LangGraph)
- [x] Phase 5.1: User Authentication
- [x] Phase 6: Safety & Guardrails
- [x] Phase 3.5 & 4: RAG Preprocessing Upgrade (Structural Discovery)

### 🚧 In Progress (15%)

- [ ] **Phase 6: FastAPI Layer** (Next - 2 weeks)
  - REST API endpoints
  - WebSocket support
  - API documentation
  - Rate limiting

- [ ] **Phase 7: MongoDB Migration** (1 week)
  - Production database connection
  - User profile updates
  - Usage analytics

### 📅 Upcoming

- [ ] **Phase 8: Testing & QA** (2 weeks)
  - Load testing
  - Security audits
  - User acceptance testing

- [ ] **Phase 9: Fine-Tuning** (Optional)
  - Collect production data
  - Custom model training

- [ ] **Phase 10: Deployment** (1 week)
  - Docker containers
  - Cloud deployment
  - CI/CD pipeline
  - Monitoring

---

## 🤝 Contributing

This is a proprietary project. Internal contributions follow these guidelines:

### Development Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
# ...

# Run tests
python -m pytest tests/

# Commit with meaningful message
git commit -m "feat: add feature description"

# Push and create PR
git push origin feature/your-feature-name
```

### Code Style

- **Python:** Follow PEP 8
- **Type Hints:** Required for all functions
- **Docstrings:** Google style
- **Comments:** Explain "why", not "what"
- **Tests:** Required for new features

### Commit Convention

```
feat: New feature
fix: Bug fix
docs: Documentation update
test: Add/update tests
refactor: Code refactoring
chore: Maintenance tasks
```

---

## 📄 License

**Proprietary** - All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

---

## 📞 Support

### For Issues

- Check [PROJECT_STATUS.md](ASTRO_CHATBOT_PROJECT_STATUS.md) for known issues
- Review documentation in `/docs` folder
- Contact: Principal Generative AI Engineer

### For Questions

- Technical questions: See inline code documentation
- Architecture questions: See PROJECT_STATUS.md
- Usage questions: See this README

---

## 🙏 Acknowledgments

- **Swiss Ephemeris (pyswisseph)** - Astronomical calculations
- **LangChain** - LLM orchestration framework
- **OpenAI** - GPT-4 and embeddings
- **Google** - Gemini models
- **ChromaDB** - Vector storage
- **Classical Texts** - BPHS, Jataka Parijata, and other authoritative sources

---

## 🎯 Quick Reference

### Environment Variables

```bash
OPENAI_API_KEY          # Required for embeddings
GOOGLE_API_KEY          # Required for Gemini LLM
DEFAULT_LLM_PROVIDER    # google | openai | anthropic
DEFAULT_LLM_MODEL       # gemini-2.5-flash | gpt-4o
MONGODB_URI             # Production database (future)
```

### Important Files

```bash
chatbot_phase5_1.py           # Main chatbot entry point
user_manager.py               # User authentication
orchestrator.py               # LangGraph state machine
calculation_tools.py          # Astrology tools
src/rag/rag_engine.py         # RAG pipeline
src/llm/prompts/personas.py   # Persona system
```

### Key Commands

```bash
python chatbot_phase5_1.py                    # Start chatbot
python chatbot_phase5_1.py --user user001     # Login as specific user
python user_manager.py                        # Test authentication
python orchestrator.py                        # Test orchestrator
```

---

## 📊 Status Summary

| Component | Status | Production Ready? |
|-----------|--------|-------------------|
| Core Chatbot | ✅ Complete | ✅ YES |
| User Auth | ✅ Complete | ✅ YES |
| Calculations | ✅ Verified | ✅ YES |
| RAG | ✅ Tested | ✅ YES |
| Orchestration | ✅ Complete | ✅ YES |
| Safety | ✅ Complete | ✅ YES |
| MongoDB | ⚠️ Dummy | ✅ READY (needs URI) |
| API Layer | ❌ Pending | ❌ Phase 6 |
| Deployment | ❌ Pending | ❌ Phase 10 |

**Overall:** ✅ **Core system is production-ready!**  
**Next Step:** Build FastAPI layer for mobile app integration

---

*Built with ❤️ by the Astrology AI Team*  
*Last Updated: February 2, 2026*