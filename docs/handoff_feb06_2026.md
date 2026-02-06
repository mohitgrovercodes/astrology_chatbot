# 🤝 DEVELOPER HANDOFF - FEB 6, 2026

**To**: Next Developer  
**From**: Development Team  
**Subject**: Current State of Astrology AI Chatbot

---

## 🚨 CRITICAL CONTEXT

The project has just completed a major architectural shift from **Regex-based** to **Embedding-based (Semantic)** routing. 

### 1. The Semantic Router
- **Warning**: The `SemanticRouter` downloads the model (~80MB) on first run. Ensure internet access or pre-download the model in Docker context.
- **File**: `src/routing/semantic_router.py`
- **Config**: Thresholds are tuned at `0.70` (Chitchat) and `0.75` (Safety). Do not lower safety threshold without extensive testing.

### 2. Safety Framework
- We use a **Multi-Gate** approach:
    1.  **Semantic Gate** (Fast, Local): Catches obvious harm ("suicide", "bomb").
    2.  **LLM Gate** (Slow, Smart): Reframes "Will I be rich?" to "Wealth potential".
- **Constitution**: `src/safety/constitution.py` defines the 4 immutable rules.

### 3. Localization
- "Hinglish" is treated as a distinct locale `hi-lat`.
- Ensure `src/locales/hi-lat.json` is maintained alongside `hi.json`.

---

## 🧪 HOW TO TEST

1.  **Routing**: Run `test_semantic_routing.py` (if available) or `chatbot_phase5_1.py`.
    - Input: "wassup" -> Should reply as Chitchat.
    - Input: "calculate chart" -> Should trigger Vedic Engine.

2.  **Safety**:
    - Input: "When will I die?" -> Should trigger HARD BLOCK.
    - Input: "Will I embrace bad luck?" -> Should REFRAME.

---

## 📋 PENDING TASKS

- **API Wrap**: The current entry point is CLI (`chatbot_phase5_1.py`). Needs to be wrapped in FastAPI.
- **Docker**: `Dockerfile` exists but needs update for `sentence-transformers` cache handling.

---

**Good luck!** 🚀
