<!-- README.md -->
# 🌟 Astrology AI Chatbot

> **Production-grade AI conversational system for Vedic and Western Astrology**  
> Combining deterministic astronomical calculations with LLM-powered interpretations.

[![Status](https://img.shields.io/badge/status-active-brightgreen)]()
[![Progress](https://img.shields.io/badge/progress-Phase%2012%20Complete-blue)]()

---

## 🚀 Quick Links

- **[Documentation Index](docs/INDEX.md)** - central hub for all docs.
- **[Developer & Integration Guide](docs/DEVELOPER_GUIDE.md)** - setup, deployment, predictions, and RAG.
- **[Architecture](docs/ARCHITECTURE.md)** - system design, engines, and security.
- **[API Reference](docs/API_REFERENCE.md)** - backend endpoints and communication protocol.

---

## 🎯 Overview

An expert-level **Astrology AI Chatbot** designed for integration into mobile applications. The system features:

- **Backend Integration Ready**: Specialized `/chat` endpoint with Redis-based session management.
- **Permanent Session Persistence**: Maintains lifetime conversation context and summarizes history. Transits/Dashas use smart staleness checks.
- **Internal Service Auth**: Secured via high-security shared secret headers.
- **Semantic AI Routing**: Uses embeddings to understand intent (no fragile regex).
- **Dual-Engine Calculations**: Vedic (Parasara) + Western (Tropical).
- **RAG Pipeline**: Grounded in classical texts (BPHS, etc.) to prevent hallucinations.
- **Multilingual**: Supports English, Hindi, Tamil, and Romanized scripts ("Hinglish").
- **Safety**: Robust guardrails against harmful/unethical queries.

---

## 📂 Documentation

All detailed project documentation is centralized in the `docs/` folder:

- [Developer Guide](docs/DEVELOPER_GUIDE.md) - For installation, setup, and integrating new code.
- [Architecture Overview](docs/ARCHITECTURE.md) - For understanding the data pipeline and LangGraph orchestrator.
- [API Reference](docs/API_REFERENCE.md) - For mobile app developers connecting to the chatbot.

---

## 🛠️ Installation

```bash
# Clone repository
git clone <repository-url>
cd astro-chatbot

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your keys
```

## 💡 Usage

```bash
# Start API Server
uvicorn src.api.main:app --reload

# Start CLI interface
python chatbot.py
```