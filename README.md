# 🌟 Astrology AI Chatbot

> **Production-grade AI conversational system for Vedic and Western Astrology**  
> Combining deterministic astronomical calculations with LLM-powered interpretations.

[![Status](https://img.shields.io/badge/status-active-brightgreen)]()
[![Progress](https://img.shields.io/badge/progress-Phase%2012%20Complete-blue)]()

---

## 🚀 Quick Links

- **[Project Status & Roadmap](docs/project_status_master.md)** - detailed progress report.
- **[API Reference](docs/API_REFERENCE.md)** - detailed API documentation & integration guide.
- **[Architecture](docs/ARCHITECTURE.md)** - system design overview.

---

## 🎯 Overview

An expert-level **Astrology AI Chatbot** designed for integration into mobile applications. The system features:

- **Backend Integration Ready**: Specialized `/chat` endpoint with Redis-based session management.
- **24h Session Persistence**: Maintains conversation context for up to 20 messages.
- **Internal Service Auth**: Secured via high-security shared secret headers.
- **Semantic AI Routing**: Uses embeddings to understand intent (no fragile regex).
- **Dual-Engine Calculations**: Vedic (Parasara) + Western (Tropical).
- **RAG Pipeline**: Grounded in classical texts (BPHS, etc.) to prevent hallucinations.
- **Multilingual**: Supports English, Hindi, Tamil, and Romanized scripts ("Hinglish").
- **Safety**: Robust guardrails against harmful/unethical queries.

---

## 📂 Documentation

All detailed documentation has been moved to the `docs/` folder:

- `docs/PROJECT_STATUS_V3.md` (Legacy Status)
- `docs/PLATFORM_HANDOFF.md`
- `docs/QUICKSTART.md`
- `docs/QUICK_REFERENCE.md`

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
# Run the chatbot interface
python chatbot_phase5_1.py
```