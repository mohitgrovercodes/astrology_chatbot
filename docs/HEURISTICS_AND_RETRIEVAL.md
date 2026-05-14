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
    → SemanticFrame (built once — route/domain/question_mode/polarity)
    → Orchestrator (LangGraph)
        → Route: CHITCHAT | CALCULATION_ONLY | RAG_ONLY | RAG_WITH_CALCULATION
    → For RAG_ONLY / RAG_WITH_CALCULATION:
        → Build enriched retrieval query (domain hint + chart suffix)
        → Build HyDE context (lagna + dasha lords + domain)
        → HybridRetriever.retrieve(question_mode=..., hyde_context=...)
```

### HybridRetriever.retrieve(...) — step by step

1. **Inputs**  
   Query, intent, optional `top_k`, language, `content_type`, `user_id`, `hyde_context`, `question_mode`.

2. **Query enrichment (before retrieval)**  
   The orchestrator appends two hints to the raw query string before calling `retrieve()`:
   - **Domain vocabulary**: e.g. `[7th house Venus Jupiter 2nd 5th house relationship partner]` for marriage, `[10th house Saturn Sun 6th house profession Dashamsha]` for career. Expands the BM25 token pool and shifts the semantic embedding toward domain-relevant chunks without hard filtering.
   - **Chart suffix**: `(Lagna: Cancer, Rashi: Scorpio)` so the embedding is personalised to the user's configuration.

   If language ≠ English, the enriched query is **translated to English** via a small LLM call.

3. **Three retrieval signals (all over the same Chroma collection)**  
   - **Semantic**: Embed enriched query with Vertex AI `gemini-embedding-001` (1536 dims), run vector similarity search in ChromaDB (2× top_k candidates).  
   - **Keyword (BM25)**: Tokenize enriched query, score all documents in the in-memory BM25 index, take top 2× top_k. Domain vocabulary terms boost relevant house/planet chunks here.  
   - **Chart-conditioned HyDE**: LLM generates a hypothetical classical-text passage conditioned on the full chart context — `”Cancer ascendant (Punarvasu), Saturn MD / Mercury AD, marriage domain”` — instead of a generic query rephrasing. The conditioned passage produces a much more specific embedding target, pulling chunks about the exact planet/ascendant/period combination.

4. **Fusion — question_mode-aware weights**  
   **Reciprocal Rank Fusion (RRF)** with weights from `RAGConfig.HYBRID_WEIGHTS_BY_QUESTION_MODE` (takes priority over intent-based weights):

   | `question_mode` | Semantic | BM25 | HyDE | Rationale |
   |---|---|---|---|---|
   | `timing` | 0.40 | **0.35** | 0.25 | Exact dasha/period terminology is diagnostic |
   | `advice` | **0.55** | 0.20 | 0.25 | Remedy guidance matches conceptually across varied phrasings |
   | `qualities` | **0.55** | 0.20 | 0.25 | Quality descriptions in classical texts vary widely in wording |
   | `summary` | 0.50 | 0.30 | 0.20 | Balanced default |

5. **Optional: memory injection**  
   If `user_id` is set and `MemoryRetriever` is enabled, the `conversation_memories` Chroma collection is queried by semantic similarity; up to 2 memory snippets (user-stated facts: “user works in finance”, “user has 2 children”) are merged into the fused list. Written by `src/rag/memory_writer.py` on each turn.

6. **Optional: rerank**  
   If `RAGConfig.should_rerank(...)` is true (e.g. `content_type == 'interpretation'`, or top score < 0.75), a **cross-encoder** (`ms-marco-MiniLM-L6-v2`) reranks the fused list and the top `top_k` are kept.

7. **Optional: context expansion**  
   Adjacent chunks (same book/chapter, chunk_index ± N) fetched and appended when `RAGConfig.should_expand(...)` is true.

8. **Output**  
   Deduplicated list of `Document` objects, up to `top_k`, returned to the orchestrator for prompt injection.

### Data sources

- **Vector store**: ChromaDB at `data/vectordb`, collection `vedic_astrology_books_knowledge`. Chunk metadata includes `planets`, `houses`, `signs`, `nakshatras`, `yogas` as comma-separated flat strings (filterable).
- **BM25**: Same documents, in-memory index built lazily on first retrieval call.
- **Memory**: Separate Chroma collection `conversation_memories`, keyed by `user_id`. Written asynchronously by `MemoryWriter`; read by `MemoryRetriever`.

### Validation tier selection

Tier determines how many rules the validation engine evaluates (80 / 120 / 150 rule cap for tiers 1–3). Now driven by `SemanticFrame` + `voice_preferences` rather than query keywords alone:

| Signal | Effect |
|---|---|
| Query contains “detailed” / “comprehensive” | → Tier 3 (keyword wins unconditionally) |
| `voice_preferences.detail_level == 'detailed'` | → Tier 3 |
| Query contains “explain” / “analyze” | → Tier 2 |
| `question_mode ∈ {advice, qualities, timing}` | → Tier 2 floor |
| `domain ∈ {health, divorce}` | → Tier 2 floor (risk domains need more rules) |
| Default | → Tier 1 (fast path for live chat) |

See `src/orchestration/orchestrator_validation_helpers.py:determine_validation_tier()`.
