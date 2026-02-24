<!-- docs\RAG_PIPELINE_DETAILED.md -->
# RAG Pipeline - Detailed Technical Documentation

**Purpose:** Complete documentation of the RAG (Retrieval-Augmented Generation) pipeline  
**Audience:** Developers working on knowledge retrieval and prediction enhancement  
**Last Updated:** February 11, 2026

---

## Overview

The RAG pipeline transforms classical astrology texts (PDFs) into a searchable knowledge base and retrieves relevant information to ground LLM responses.

**Pipeline Stages:**
1. **Extraction** - PDF → Markdown (Vision LLM)
2. **Preprocessing** - 8-phase text processing
3. **Retrieval** - Semantic + keyword search
4. **Generation** - LLM synthesis with retrieved context

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE                              │
└─────────────────────────────────────────────────────────────┘

PHASE 1: EXTRACTION
┌──────────┐
│ PDF File │ → Vision LLM (Gemini) → Markdown
└──────────┘

PHASE 2-7: PREPROCESSING
Markdown → Cleaning → Analysis → Profiling → Segmentation → 
Enrichment → Embedding → Vector DB

RETRIEVAL TIME:
Query → Language Detection → Strategy Selection → 
Hybrid Search (Vector + BM25) → Reranking → Top-K Chunks

GENERATION TIME:
Query + Chunks + Chart Data → Prompt Builder → LLM → Response
```

---

## Phase 1: PDF Extraction

**Location:** `src/rag/extraction/`  
**Main File:** `vision_pipeline.py`

### Vision LLM Extraction

**Model:** Gemini 2.5 Flash  
**Input:** PDF pages as images  
**Output:** Structured Markdown

**Features:**
- Table detection and conversion
- Sanskrit text preservation
- Verse numbering extraction
- Chapter/section hierarchy
- Footnote handling

**Extraction Prompt:**
```
Extract all text from this astrology book page.
Preserve:
- Sanskrit verses with transliteration
- Verse numbers (॥ 42 ॥)
- Chapter headings
- Tables and lists
- Footnotes

Output as clean Markdown.
```

**Performance:**
- Speed: ~2-3 seconds per page
- Accuracy: ~95% for printed text
- Cost: ~$0.001 per page (Gemini Flash)

---

## Phase 2: Structural Cleaning

**Location:** `src/rag/preprocessing/structural_cleaner.py`  
**Purpose:** Normalize and clean extracted text

### Cleaning Operations

1. **Whitespace Normalization**
   - Remove excessive blank lines
   - Standardize indentation
   - Trim trailing spaces

2. **Header/Footer Removal**
   - Page numbers
   - Running headers
   - Copyright notices

3. **Hyphenation Repair**
   - Rejoin words split across lines
   - Example: "astro-\nlogy" → "astrology"

4. **Unicode Normalization**
   - Standardize Devanagari characters
   - Fix encoding issues
   - Normalize punctuation

5. **Noise Removal**
   - OCR artifacts
   - Watermarks
   - Scanning artifacts

**Example:**
```markdown
# Before Cleaning
Page 42                    BRIHAT PARASHARA HORA SHASTRA
॥ 42 ॥  The   Sun   in   the   7th   house   indicates...
[Watermark: Sample Copy]

# After Cleaning
॥ 42 ॥ The Sun in the 7th house indicates...
```

---

## Phase 3: Cross-Page Analysis

**Location:** `src/rag/preprocessing/page_analyzer.py`  
**Purpose:** Detect continuity across page boundaries

### Analysis Features

1. **Sentence Continuation Detection**
   - Identifies sentences split across pages
   - Merges incomplete sentences

2. **Chapter Boundary Detection**
   - Identifies chapter starts/ends
   - Preserves chapter context

3. **Verse Sequence Tracking**
   - Ensures verse numbers are sequential
   - Flags missing verses

4. **Table Continuation**
   - Detects tables spanning multiple pages
   - Merges table fragments

**Example:**
```markdown
# Page 41 (end)
The Sun in the 7th house indicates marriage to a person of

# Page 42 (start)
high status and authority.

# After Analysis
The Sun in the 7th house indicates marriage to a person of high status and authority.
```

---

## Phase 3.5: Book Profiling (Structural Discovery)

**Location:** `src/rag/preprocessing/book_profiler.py`  
**Purpose:** Automatically discover book structure using LLM

### Key Innovation

Instead of hardcoding chunking rules, the system:
1. Samples representative pages from the book
2. Uses LLM to identify structural patterns
3. Generates book-specific chunking rules

**Discovered Patterns:**
- **Verse Markers:** Regex patterns for shloka numbers
- **Semantic Markers:** Transition phrases ("Sage Parasara said", "Note:")
- **Hierarchy:** Chapter → Section → Verse → Commentary structure

**Example Profile:**
```json
{
  "book_name": "Brihat Parashara Hora Shastra",
  "verse_pattern": "॥ \\d+ ॥",
  "semantic_markers": [
    "Sage Parasara said",
    "Maitreya said",
    "Note:",
    "Commentary:"
  ],
  "hierarchy": {
    "level_1": "Chapter",
    "level_2": "Section",
    "level_3": "Verse",
    "level_4": "Commentary"
  },
  "chunking_strategy": "verse_based"
}
```

**Benefits:**
- Works with any astrology book
- No manual rule creation
- Preserves semantic boundaries

---

## Phase 4: Semantic Segmentation

**Location:** `src/rag/preprocessing/semantic_segmenter.py`  
**Purpose:** Split text into semantically coherent chunks

### Segmentation Strategy

**Hierarchical Splitting:**
1. **Hard Breaks** (Always split)
   - Page boundaries
   - Chapter boundaries
   - Major section headings

2. **Semantic Breaks** (Split if meaningful)
   - Verse boundaries (discovered patterns)
   - Transition phrases (discovered markers)
   - Topic shifts (detected by LLM)

3. **Soft Breaks** (Split only if chunk too large)
   - Paragraph boundaries
   - Sentence boundaries

**Context Injection:**
Each chunk inherits a "Context Header" to prevent meaning fragmentation.

**Example:**
```markdown
# Original Text
Chapter 7: Effects of Planets in Houses

॥ 42 ॥ The Sun in the 7th house indicates...
॥ 43 ॥ The Moon in the 7th house indicates...

# After Segmentation
Chunk 1:
---
Context: Chapter 7 - Effects of Planets in Houses
---
॥ 42 ॥ The Sun in the 7th house indicates marriage to a person of high status...

Chunk 2:
---
Context: Chapter 7 - Effects of Planets in Houses
---
॥ 43 ॥ The Moon in the 7th house indicates a partner who is nurturing...
```

**Chunk Size:**
- Target: 300-500 tokens
- Max: 800 tokens
- Min: 100 tokens

---

## Phase 5: Chunk Enrichment

**Location:** `src/rag/preprocessing/chunk_enricher.py`  
**Purpose:** Add metadata and summaries to chunks

### Enrichment Operations

1. **Summary Generation**
   - LLM generates concise summary of chunk
   - Used for better retrieval

2. **Entity Extraction**
   - Planets mentioned (Sun, Moon, Mars, etc.)
   - Houses mentioned (1st, 7th, 10th, etc.)
   - Signs mentioned (Aries, Taurus, etc.)
   - Nakshatras mentioned

3. **Topic Classification**
   - Marriage, Career, Health, Wealth, etc.

4. **Metadata Tagging**
   - Source book
   - Chapter number
   - Page number
   - Verse number (if applicable)
   - Language (Sanskrit, English, etc.)

**Example Enriched Chunk:**
```json
{
  "content": "॥ 42 ॥ The Sun in the 7th house indicates...",
  "summary": "Effects of Sun in 7th house for marriage",
  "entities": {
    "planets": ["Sun"],
    "houses": ["7th"],
    "signs": [],
    "nakshatras": []
  },
  "topics": ["marriage", "relationships", "spouse"],
  "metadata": {
    "source": "Brihat Parashara Hora Shastra",
    "chapter": 7,
    "page": 42,
    "verse": 42,
    "language": "en"
  }
}
```

---

## Phase 6: Embedding

**Location:** `src/rag/preprocessing/embedder.py`  
**Purpose:** Convert text chunks to vector embeddings

### Embedding Model

**Model:** OpenAI `text-embedding-3-large`  
**Dimensions:** 3072  
**Cost:** $0.13 per 1M tokens

**Alternative Models:**
- `text-embedding-3-small` (1536 dims, cheaper)
- `text-embedding-ada-002` (1536 dims, legacy)

### Embedding Strategy

**Multi-Vector Approach:**
1. **Content Embedding** - Main chunk text
2. **Summary Embedding** - Chunk summary (for better retrieval)

**Batch Processing:**
- Batch size: 100 chunks
- Parallel processing: 5 concurrent batches
- Rate limiting: 3000 RPM

**Performance:**
- Speed: ~1000 chunks/minute
- Cost: ~$0.01 per 1000 chunks

---

## Phase 7: Vector DB Ingestion

**Location:** `src/rag/preprocessing/vector_db_builder.py`  
**Purpose:** Store embeddings in ChromaDB

### ChromaDB Schema

**Collection Structure:**
```python
{
  "id": "bphs_ch7_v42",
  "embedding": [0.123, -0.456, ...],  # 3072 dimensions
  "metadata": {
    "source": "BPHS",
    "chapter": 7,
    "page": 42,
    "verse": 42,
    "language": "en",
    "planets": ["Sun"],
    "houses": ["7th"],
    "topics": ["marriage"]
  },
  "document": "॥ 42 ॥ The Sun in the 7th house indicates..."
}
```

**Indexing:**
- HNSW (Hierarchical Navigable Small World) index
- Distance metric: Cosine similarity
- Index build time: ~1 minute per 10,000 chunks

**Storage:**
- Location: `data/vectordb/`
- Size: ~500MB per 10,000 chunks
- Persistence: Disk-based (SQLite + Parquet)

---

## Retrieval Strategies

**Location:** `src/rag/retriever.py` and `src/rag/rag_engine.py`

### 1. Vector Search (Default)

**Method:** Semantic similarity using embeddings

**Process:**
1. Embed query using same model
2. Find K nearest neighbors in vector space
3. Return top-K chunks

**Best For:**
- Conceptual queries ("What does Jupiter mean?")
- Paraphrased questions
- Multilingual queries

**Example:**
```python
query = "What are the effects of Jupiter in the 7th house?"
# Retrieves chunks about Jupiter, 7th house, marriage, relationships
```

### 2. Hybrid Search (Vector + BM25)

**Method:** Combine semantic and keyword matching

**Process:**
1. Vector search → Get top-20 candidates
2. BM25 keyword search → Get top-20 candidates
3. Merge and rerank → Return top-K

**Best For:**
- Specific terminology ("Vimshottari dasha")
- Proper nouns ("Parasara", "Jaimini")
- Exact phrase matching

**Weighting:**
- Vector score: 70%
- BM25 score: 30%

### 3. HyDE (Hypothetical Document Embeddings)

**Method:** Generate hypothetical answer, then search

**Process:**
1. LLM generates hypothetical answer to query
2. Embed hypothetical answer
3. Search for similar chunks
4. Return top-K chunks

**Best For:**
- Abstract questions ("How to predict marriage timing?")
- Questions requiring synthesis
- Queries with no direct text match

**Example:**
```python
query = "How to predict career success?"
# LLM generates: "Career success is indicated by strong 10th house..."
# Search for chunks similar to generated text
```

### 4. Query Routing (Automatic Strategy Selection)

**Method:** Classify query intent, select best strategy

**Rules:**
- **Keyword queries** → BM25 only
- **Conceptual queries** → Vector search
- **General questions** → HyDE
- **Hybrid queries** → Hybrid search

**Classification:**
```python
def classify_query_intent(query):
    if has_specific_terms(query):  # "Vimshottari", "Navamsa"
        return "keyword"
    elif is_abstract(query):  # "How to...", "What is the meaning..."
        return "conceptual"
    else:
        return "general"
```

---

## Metadata Filtering

**Purpose:** Narrow search scope using metadata

### Available Filters

1. **Language Filter**
   ```python
   filters = {"language": "en"}
   # Only retrieve English chunks
   ```

2. **Source Filter**
   ```python
   filters = {"source": "BPHS"}
   # Only retrieve from Brihat Parashara Hora Shastra
   ```

3. **Topic Filter**
   ```python
   filters = {"topics": {"$contains": "marriage"}}
   # Only retrieve marriage-related chunks
   ```

4. **Planet Filter**
   ```python
   filters = {"planets": {"$contains": "Jupiter"}}
   # Only retrieve chunks mentioning Jupiter
   ```

5. **House Filter**
   ```python
   filters = {"houses": {"$contains": "7th"}}
   # Only retrieve chunks about 7th house
   ```

### Combined Filters

```python
filters = {
    "language": "en",
    "planets": {"$contains": "Jupiter"},
    "houses": {"$contains": "7th"},
    "topics": {"$contains": "marriage"}
}
# Retrieve English chunks about Jupiter in 7th house for marriage
```

---

## Reranking

**Location:** `src/rag/reranker.py`  
**Purpose:** Improve retrieval quality by reordering results

### Reranking Methods

1. **Cross-Encoder Reranking** (Not implemented)
   - Use cross-encoder model to score query-chunk pairs
   - More accurate but slower

2. **LLM-based Reranking** (Not implemented)
   - Ask LLM to rank chunks by relevance
   - Most accurate but expensive

3. **Metadata-based Reranking** (Implemented)
   - Boost chunks with matching metadata
   - Fast and effective

**Current Implementation:**
```python
def rerank_by_metadata(chunks, query_entities):
    for chunk in chunks:
        boost = 0
        if chunk.planets in query_entities['planets']:
            boost += 0.1
        if chunk.houses in query_entities['houses']:
            boost += 0.1
        chunk.score += boost
    return sorted(chunks, key=lambda x: x.score, reverse=True)
```

---

## RAG Engine

**Location:** `src/rag/rag_engine.py` (788 lines)  
**Class:** `RAGEngine`

### Key Methods

#### `answer_question()`

**Purpose:** Main entry point for RAG-based Q&A

**Signature:**
```python
def answer_question(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict] = None,
    use_hyde: Optional[bool] = None,  # Auto-detect if None
    conversation_history: Optional[List[Dict]] = None,
    user_profile: Optional[Dict] = None
) -> RAGResponse
```

**Process:**
1. Detect if follow-up query
2. Expand query if needed
3. Classify query intent
4. Select retrieval strategy
5. Retrieve chunks
6. Build prompt
7. Generate response
8. Format with sources

#### `_is_followup_query()`

**Purpose:** Detect if query is a follow-up to previous conversation

**Examples:**
- "What about in the 7th?" (follow-up)
- "And for marriage?" (follow-up)
- "Tell me more" (follow-up)

#### `_expand_followup_query()`

**Purpose:** Expand follow-up query into self-contained query

**Example:**
```python
# Previous: "What are the effects of Jupiter?"
# Current: "What about in the 7th house?"
# Expanded: "What are the effects of Jupiter in the 7th house?"
```

---

## Prompt Building

**Location:** `src/ai/prompt_builder.py`  
**Class:** `PromptBuilder`

### Prompt Structure

```
SYSTEM PROMPT:
You are a professional Vedic astrologer...

CONTEXT:
[Retrieved chunks from classical texts]

USER PROFILE:
Name: John Doe
Birth Date: 1990-05-15
Lagna: Aries
Moon Sign: Cancer

CONVERSATION HISTORY:
User: What is my sun sign?
Assistant: Your sun sign is Taurus.

QUERY:
When will I get married?

INSTRUCTIONS:
1. Use the provided classical texts as your primary source
2. Reference the user's birth chart
3. Provide specific timing if possible
4. Be empathetic and professional
5. Cite sources when making claims

RESPONSE:
```

### Persona System

**Location:** `src/ai/personas.py`

**Available Personas:**
1. **Vedic Astrologer** - Traditional, classical approach
2. **Western Astrologer** - Modern, psychological approach
3. **Hybrid** - Combines both systems (default)

**Persona Configuration:**
```python
{
    "name": "Professional Vedic Astrologer",
    "tone": "empathetic, professional, traditional",
    "style": "Uses classical terminology, cites ancient texts",
    "constraints": [
        "Never predict death",
        "Always provide disclaimers for health/legal",
        "Focus on growth and self-awareness"
    ]
}
```

---

## Performance Metrics

### Preprocessing Pipeline
- **Total Time:** ~2-3 minutes per 100-page book
- **Extraction:** ~3 seconds/page
- **Preprocessing:** ~30 seconds per 100 pages
- **Embedding:** ~1 minute per 1000 chunks
- **Ingestion:** ~10 seconds per 1000 chunks

### Retrieval Performance
- **Vector Search:** ~50-100ms
- **Hybrid Search:** ~150-200ms
- **HyDE:** ~800ms (includes LLM call)
- **Reranking:** ~10-20ms

### Generation Performance
- **Prompt Building:** ~10ms
- **LLM Generation:** ~2-3 seconds (gpt-4o-mini)
- **Total RAG Query:** ~3-5 seconds

---

## Current Limitations

### Preprocessing
1. ❌ No table structure preservation (tables converted to text)
2. ❌ No image/diagram extraction
3. ❌ No mathematical formula parsing
4. ❌ Limited Sanskrit transliteration handling

### Retrieval
1. ❌ No cross-encoder reranking
2. ❌ No query expansion beyond follow-ups
3. ❌ No multi-hop reasoning
4. ❌ No contradiction detection

### Generation
1. ❌ No source citation in response text
2. ❌ No confidence scoring
3. ❌ No fact-checking against multiple sources
4. ❌ No hallucination detection

---

## Recommended Enhancements

### Priority 1: Improve Retrieval Quality
1. Implement cross-encoder reranking
2. Add query expansion techniques
3. Implement multi-hop reasoning
4. Add contradiction detection

### Priority 2: Better Source Attribution
1. Inline source citations in response
2. Confidence scores for each claim
3. Multiple source verification
4. Highlight conflicting sources

### Priority 3: Enhanced Preprocessing
1. Better table structure preservation
2. Diagram/chart extraction and description
3. Improved Sanskrit handling
4. Mathematical formula parsing

---

**Document Version:** 1.0  
**Last Updated:** February 11, 2026  
**For Questions:** Refer to code in `src/rag/`
