# Heuristics, Intent Classification, and Retrieval

## Why heuristics are a good idea

Heuristics (pattern matching, keyword rules, semantic similarity to reference phrases) are used in NakshatraAI for:

1. **Speed** — No LLM call for clear-cut queries (“hi”, “what is my lagna”, “when will i get married”). Response is instant and predictable.
2. **Cost** — Fewer LLM calls mean lower API cost and less latency for the majority of traffic.
3. **Determinism** — For 100% unambiguous cases (e.g. “what is my sun sign”), rules give the same result every time. That avoids random misclassifications from the LLM on trivial inputs.
4. **Fallback** — When the LLM fails, times out, or returns invalid JSON, pattern-based fallback prevents the pipeline from breaking and still routes the query.

So heuristics are a good idea when they are limited to **high-certainty** cases and the rest is left to the LLM (or to “pattern + LLM confirmation” for borderline cases).

---

## Why misclassification still happens

Misclassification usually comes from one of these:

1. **Heuristics too broad** — A regex or keyword rule matches when it shouldn’t (e.g. “explain my chart” matched by a “my” + “chart” rule and sent to CALCULATION_ONLY instead of RAG_WITH_CALCULATION).
2. **Heuristics too narrow** — A valid phrasing isn’t in the pattern cache or semantic reference set, so the LLM is used and sometimes returns the wrong category.
3. **LLM inconsistency** — Same query phrased slightly differently gets a different intent from the LLM.
4. **Ambiguous queries** — e.g. “Jupiter” or “7th house” with no context: could be theory (RAG_ONLY) or “tell me about Jupiter in *my* chart” (RAG_WITH_CALCULATION). Heuristics alone can’t resolve that.

So: heuristics are good for **clear, high-confidence** cases; they become a source of errors when they override the LLM in **edge or ambiguous** cases.

---

## Keeping the chatbot smart and correct

To keep behaviour correct and “common sense”:

1. **Restrict heuristics to high confidence**
   - Use **exact-match cache** (e.g. `SAFE_PATTERN_CACHE`) only for phrases that are unambiguously one intent (e.g. “hi”, “what is my lagna”).
   - Use **regex/keyword pre-routers** only for patterns that almost never misclassify (e.g. “what is my sun sign”, “show my kundali”). If a rule can match both “show my chart” and “explain my chart”, prefer not to route by rule and let the LLM decide.

2. **Use LLM for everything else**
   - For anything not in the high-confidence set, call the LLM with a clear prompt and examples (as you already do in `LLMIntentClassifier`). That gives you “common sense” and context (e.g. conversation history).

3. **Optional: LLM confirmation for low-confidence patterns**
   - You already have semantic routing (embedding similarity to reference phrases). When the **semantic** or **pattern** confidence is below a threshold (e.g. 0.85), treat the result as a hint and **confirm with the LLM** (e.g. “Pattern suggested RAG_ONLY; is that correct for this query?”). Same idea is used in `orchestrator_validation_helpers.detect_query_type` with `confirm_query_type_with_llm` when pattern confidence &lt; 0.7.

4. **Clarify ambiguous queries**
   - For truly ambiguous inputs (e.g. “Jupiter” alone), return **AMBIGUOUS** and ask the user to clarify (“Do you mean: (a) general meaning of Jupiter, or (b) Jupiter in your chart?”). That avoids guessing and keeps behaviour correct.

5. **Log and review**
   - Log which path was used (pattern cache, keyword pre-route, semantic, LLM) and confidence. Review misclassified examples and either add high-confidence rules for them or tighten/remove rules that cause errors.

In short: **use heuristics only where they are clearly right; use the LLM (and optional confirmation) for the rest**, so the bot stays smart and correct.

---

## How to run the retrieval test

Two options:

### 1. Multilingual RAG test (AstrologyRetriever — semantic + BM25 only)

Uses the standalone `AstrologyRetriever` (ChromaDB + BM25, no HyDE/reranker). Good for checking vector DB and basic retrieval quality across languages.

From project root, with your conda env activated:

```bash
conda activate venv/
python tests/test_multilingual_rag.py
```

- Requires: ChromaDB at `data/vectordb` (or path in config), collection `vedic_astrology_books_knowledge`, and Google Cloud credentials for Vertex AI embeddings.
- Writes: `multilingual_rag_test_results.json` with scores and topic coverage per query.

### 2. Hybrid retrieval test (production path)

To test the **actual** retrieval path used in the app (HybridRetriever: semantic + BM25 + HyDE + optional reranking):

```bash
conda activate venv/
python tests/run_retrieval_test.py
```

(See below for what this script does; create it if you want a single entry point.)

---

## How the chatbot retrieves data right now

End-to-end flow:

```
User message
    → Orchestrator (LangGraph)
        → Intent classification (LLMIntentClassifier)
            → 1) Exact pattern cache (e.g. "hi" → CHITCHAT)
            → 2) Keyword pre-route (e.g. "what is my lagna" → CALCULATION_ONLY)
            → 3) Semantic routing (embedding vs reference phrases)
            → 4) LLM classification (if none of the above)
        → Route: CHITCHAT | CALCULATION_ONLY | RAG_ONLY | RAG_WITH_CALCULATION
    → For RAG_ONLY / RAG_WITH_CALCULATION:
        → HybridRetriever.retrieve(...)
```

### HybridRetriever.retrieve(...) — step by step

1. **Inputs**  
   Query, intent (e.g. RAG_WITH_CALCULATION), optional `top_k`, language, `content_type`, `user_id`.

2. **Query for retrieval**  
   If language ≠ English, the query is **translated to English** via a small LLM call so the vector store (indexed in English) is searched in English.

3. **Three retrieval signals (all over the same Chroma collection)**  
   - **Semantic**: Embed query with Vertex AI `gemini-embedding-001` (1536 dims), run vector similarity search in ChromaDB (e.g. 2× top_k candidates).  
   - **Keyword (BM25)**: Tokenize query, score all documents in the in-memory BM25 index built from the same collection, take top 2× top_k.  
   - **HyDE**: One LLM call to generate a short “ideal answer passage” in the style of the corpus; embed that passage and run semantic search with it. Gives a third ranking.

4. **Fusion**  
   **Reciprocal Rank Fusion (RRF)** with intent-based weights from `RAGConfig` (e.g. semantic 0.5, keyword 0.3, HyDE 0.2). Combined ranking is produced from the three lists.

5. **Optional: memory**  
   If `user_id` is set and `MemoryRetriever` is enabled, a separate Chroma collection of conversation memories is queried by semantic similarity; a few memory snippets are merged into the fused list (and deduped).

6. **Optional: rerank**  
   If `RAGConfig.should_rerank(...)` is true (e.g. content_type interpretation, or top score &lt; threshold), a **cross-encoder** (e.g. `ms-marco-MiniLM-L6-v2`) reranks the fused list and the top `top_k` are kept.

7. **Optional: context expansion**  
   If `RAGConfig.should_expand(...)` is true, **adjacent chunks** (same book/chapter, chunk_index ± 1) are fetched from Chroma and appended so that surrounding sentences are available.

8. **Output**  
   Deduplicated list of documents (LangChain `Document`), up to `top_k`, returned to the orchestrator. The orchestrator then passes these to the prompt builder as “knowledge chunks” and the LLM generates the answer.

### Data sources

- **Vector store**: ChromaDB, persistent path (e.g. `data/vectordb`), collection `vedic_astrology_books_knowledge`. Embeddings from Vertex AI (`gemini-embedding-001`).
- **BM25**: Same documents as in Chroma, loaded once and kept in memory; used only for keyword scoring.
- **Memory** (optional): Separate Chroma collection (e.g. `conversation_memories`), keyed by `user_id`, for previous conversation snippets.

So: **retrieval is hybrid (semantic + BM25 + HyDE), then optionally reranked and expanded**, and the intent that drove the route (e.g. RAG_WITH_CALCULATION) is the same one used to choose weights and whether to rerank/expand.
