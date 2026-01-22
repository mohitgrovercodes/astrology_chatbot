# RAG Preprocessing Pipeline

Complete text pre-processing pipeline for the Astrology AI Chatbot RAG system.

## Features

- **6-Phase Pipeline**: From raw PDF extraction to embedding-ready chunks
- **Sanskrit Support**: Unicode normalization for Devanagari text
- **Cross-Page Analysis**: Automatic continuation detection
- **Semantic Segmentation**: Verse-commentary unit extraction
- **Entity Extraction**: Planets, houses, signs, nakshatras
- **Metadata Enrichment**: Hypothetical questions, summaries
- **OpenAI Integration**: text-embedding-3-large support

## Quick Start

### 1. Install Dependencies

```bash
pip install pydantic google-generativeai openai
```

### 2. Set API Keys

```bash
# Optional: For enhanced analysis
export GOOGLE_API_KEY="your-google-api-key"

# Required: For embedding generation
export OPENAI_API_KEY="your-openai-api-key"
```

### 3. Run Pipeline

```bash
# Full pipeline
python src/rag/preprocessing/pipeline.py extracted/input.json --output-dir processed

# With LLM enhancement
python src/rag/preprocessing/pipeline.py input.json --use-llm --output-dir processed

# Skip embedding (no API key needed)
python src/rag/preprocessing/pipeline.py input.json --skip-embedding
```

## Pipeline Phases

| Phase | Module | Description |
|-------|--------|-------------|
| 2 | `structural_cleaner.py` | Header/footer removal, Sanskrit normalization |
| 3 | `page_analyzer.py` | Cross-page continuation detection |
| 4 | `semantic_segmenter.py` | Verse-commentary unit extraction |
| 5 | `chunk_enricher.py` | Entity extraction, question generation |
| 6 | `embedder.py` | OpenAI embedding generation |

## Usage

### CLI Options

```bash
python src/rag/preprocessing/pipeline.py [INPUT] [OPTIONS]

Arguments:
  INPUT                Input extracted JSON file

Options:
  -o, --output-dir     Directory for checkpoint files
  -s, --source-book    Book name for metadata
  -t, --tradition      "vedic" or "western" (default: vedic)
  --use-llm           Enable LLM for enhanced analysis
  --skip-embedding    Skip Phase 6 embedding
```

### Sample Run

```
Input: 5 pages
Duration: 0.08 seconds
Chunks: 10
Tokens: 2,224
Entities: 6 planets, 14 houses
```

## Output Format

The pipeline generates:
- `*_phase2_cleaned.json` - Cleaned pages
- `*_phase3_linked.json` - With cross-page relationships  
- `*_phase4_segmented.json` - Semantic units
- `*_phase5_enriched.json` - Ready for embedding
- `*_final.json` - Complete output with embeddings

## Next Steps

1. Choose VectorDB (Pinecone/Qdrant/Weaviate)
2. Implement VectorDB ingestion
3. Build retrieval interface
4. Test RAG query quality

## Documentation

- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Current project status
- [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Development guide

## License

Internal project for astrology chatbot development.
