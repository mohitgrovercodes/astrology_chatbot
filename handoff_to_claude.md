# 🚀 Handoff: Phase 3 Complete -> Initiating Phase 4

**Date:** 2026-01-29
**Status:** RAG Pipeline Stabilized. Moving to "Brain" Building.

## 🌟 Executive Summary for Claude
We have just completed **Phase 3 (RAG Pipeline)**. The system can now:
1.  Ingest PDFs (Vision LLM).
2.  Clean & Chunk text (Semantic Units).
3.  Store w/ Embeddings (ChromaDB + OpenAI).
4.  Retrieve w/ Smart Routing (Vector vs Hybrid vs HyDE).

**Current Goal (Phase 4):**
We need to **build the "Astrologer Persona"**. The current bot answers questions, but it sounds like a generic AI or a database searcher. We want it to speak like a *Rishi* or an *Expert Consultant*—respectful, precise, and acknowledging limits.

---

## 📂 Critical Files (Project Knowledge)
Add these to your context window immediately:

### 1. The Map
*   `docs/ASTRO_CHATBOT_PROJECT_STATUS.md`: The single source of truth for progress.
*   `task.md`: The active checklist for Phase 4.
*   `implementation_plan.md`: The detailed step-by-step technical plan for Phase 4.

### 2. The Core Code (To Be Modified)
*   `src/rag/rag_engine.py`: Contains `answer_question` and the new `_classify_query_intent` (Router). You will refactor this to use Templates.
*   `src/llm/factory.py`: The LLM infrastructure.
*   `chatbot.py`: The user interface (CLI).

---

## 🛠️ What We Are Doing Now (Phase 4 Roadmap)

We are transitioning from **Infrastructure** to **Intelligence**.

### Step 1: Directory Structure (Immediate)
Create `src/llm/prompts/` to separate logic from text.
*   `src/llm/prompts/personas.py`: Store system prompts (e.g., `VEDIC_CLASSICAL`).
*   `src/llm/prompts/templates.py`: Store Jinja2-style templates for RAG prompts.

### Step 2: Refactor Factory
Audit `src/llm/factory.py` to ensure it robustly handles:
*   Model switching (User asks "Switch to GPT-4" -> It happens).
*   Rate limiting (Already decent, but verify).

### Step 3: Integrate Persona into Engine
Modify `RAGEngine` in `src/rag/rag_engine.py`:
*   Replace hardcoded `SYSTEM_PROMPT` string with dynamic loading from `personas.py`.
*   Inject conversation history intelligently (Summary vs Full History).

### Step 4: Testing Tone
Run `chatbot.py` and verify:
*   Does it say "I believe..." or "According to the Shastras..."? (We want the latter).
*   Does it use Sanskrit terms correctly?

---

## 💡 Key Context: The "Router"
We realized that **Pure Vector Search** is great for concepts ("Inauspicious Sun"), but **Hybrid Search** is needed for lookups ("Verse 12").
*   We implemented a `_classify_query_intent` method in `rag_engine.py`.
*   **DO NOT BREAK THIS**. When refactoring, ensure the "Auto-Router" logic remains preserved or enhanced.

## 🏁 Final Words
You are building the **Soul** of the machine now. The Body (RAG) is ready. Good luck!
