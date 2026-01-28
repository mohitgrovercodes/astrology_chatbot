# Astrology AI ChatBot - Complete RAG System

A production-grade end-to-end RAG (Retrieval-Augmented Generation) system for Vedic astrology, powered by classical texts like Brihat Parasara Hora Shastra.

## 🌟 Project Overview

This system provides a complete pipeline from PDF extraction to an interactive AI chatbot that answers astrology questions based on classical texts.

### Key Features
- **📚 Complete RAG Pipeline**: 7-phase processing from PDF to vector database
- **🔍 Semantic Search**: ChromaDB-powered retrieval with metadata filtering
- **🤖 AI Chatbot**: Interactive CLI with Gemini-powered answers
- **📖 Classical Texts**: Grounded in authoritative Vedic astrology sources
- **🎯 Smart Retrieval**: HyDE-style retrieval with context expansion
- **💰 Cost Tracking**: Built-in tracking for API usage and costs

## 🏗️ Complete Pipeline

### Phase 1: PDF Extraction
Extract text and structures using Gemini Vision models.

### Phase 2: Structural Cleaning
Remove headers, footers, normalize Sanskrit text.

### Phase 3: Cross-Page Analysis
Link content across pages, detect continuations.

### Phase 4: Semantic Segmentation
Create semantic units (verse + commentary, concepts).

### Phase 5: Chunk Enrichment
Add metadata, entities, hypothetical questions.

### Phase 6: Embedding
Generate embeddings using OpenAI `text-embedding-3-large`.

### Phase 7: Vector Database
Ingest chunks into ChromaDB with metadata.

### Phase 8: Retrieval
Semantic search with filtering and context expansion.

### Phase 9: Chatbot
Interactive Q&A with Gemini-powered answers.

## 📂 Project Structure

```text
├── chatbot.py                 # 🤖 Interactive chatbot CLI
├── batch_extract.py           # Phase 1: PDF extraction
├── run_preprocessing_phases.py # Phases 2-6: Processing pipeline
├── src/
│   ├── rag/
│   │   ├── extraction/        # Vision extraction (Phase 1)
│   │   ├── preprocessing/     # Phases 2-6 modules
│   │   │   ├── structural_cleaner.py
│   │   │   ├── page_analyzer.py
│   │   │   ├── semantic_segmenter.py
│   │   │   ├── chunk_enricher.py
│   │   │   ├── embedder.py
│   │   │   └── vector_db_builder.py
│   │   ├── retriever.py       # Phase 8: Semantic search
│   │   └── rag_engine.py      # Phase 9: Answer generation
│   ├── llm/                   # LLM Factory (Vertex AI)
│   └── utils/                 # Config, logging, cost tracking
├── data/
│   └── vectordb/              # ChromaDB storage
└── config/                    # YAML configuration
```

## 🚀 Quick Start

### 1. Installation

```bash
# Install dependencies
pip install pydantic google-generativeai openai chromadb langchain-google-vertexai
pip install pillow numpy pdf2image
```

### 2. Set API Keys

```bash
# .env file
OPENAI_API_KEY=your_openai_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/google_credentials.json
```

### 3. Run Complete Pipeline

```bash
# Extract and process PDF (Phases 1-7)
python src/rag/preprocessing/pipeline.py input.pdf --output-dir preprocessing_output

# Or run phases individually:

# Phase 1: Extract PDF
python batch_extract.py book.pdf --start 1 --end 99

# Phases 2-6: Process
python run_preprocessing_phases.py --input extraction_output/page_1.json

# Phase 6: Embed
python src/rag/preprocessing/embedder.py preprocessing_output/enriched.json

# Phase 7: Build vector DB
python src/rag/preprocessing/vector_db_builder.py preprocessing_output/embedded.json --reset
```

### 4. Run Chatbot 🎉

```bash
# Start interactive chatbot
python chatbot.py

# Example questions:
# - What does Mars in the 5th house signify?
# - Explain the concept of Gulika
# - What are the effects of Jupiter in Aries?
```

## 💬 Chatbot Usage

### Interactive Commands

```bash
/help                    # Show help
/filter planet=Mars      # Filter by planet
/filter house=5          # Filter by house
/filter clear            # Clear filters
/sources on|off          # Toggle source citations
/clear                   # Clear conversation history
/quit                    # Exit
```

### Example Session

```
🔮 You: What does Mars in the 5th house signify?

🤔 Thinking...

✨ ANSWER
According to classical texts, Mars in the 5th house indicates...
[AI-generated answer based on retrieved context]

📚 SOURCES
[1] Brihat Parasara Hora Sastra - Chapter on Houses (Verse 63-66) - Relevance: 94.2%
[2] Brihat Parasara Hora Sastra - Mars Effects - Relevance: 89.7%
```

## 🔧 Advanced Usage

### Test Retrieval

```bash
# Basic retrieval
python src/rag/retriever.py "Effects of Jupiter" --top-k 5

# With filtering
python src/rag/retriever.py "Mars effects" --filter-planet Mars --filter-house 5

# HyDE retrieval
python src/rag/retriever.py "Explain Gulika" --hyde --expand
```

### Test RAG Engine

```bash
# Get AI answer
python src/rag/rag_engine.py "What is the significance of the 10th house?"

# Custom model
python src/rag/rag_engine.py "Jupiter in Aries" --model gemini-1.5-pro
```

### Collection Management

```bash
# View collection stats
python src/rag/preprocessing/vector_db_builder.py --stats --collection brihat_parasara_hora_sastra

# Reset and rebuild
python src/rag/preprocessing/vector_db_builder.py embedded.json --reset
```

## 🎯 Technology Stack

- **Extraction**: Gemini Vision (Flash/Pro) via Vertex AI
- **Embeddings**: OpenAI `text-embedding-3-large` (3072 dimensions)
- **Vector DB**: ChromaDB with persistent storage
- **LLM**: Gemini 2.0 Flash via Vertex AI
- **Retrieval**: Semantic search + metadata filtering
- **Framework**: LangChain, Pydantic

## 📊 Current Status

✅ **163 chunks** indexed from Brihat Parasara Hora Shastra  
✅ **74 Sanskrit verses** with translations  
✅ **Full metadata** (planets, houses, signs, nakshatras, yogas)  
✅ **Interactive chatbot** ready to use  

## 🛠️ Developer Tools

- **Cost Tracking**: SQLite-based tracking in `logs/cost_tracker.db`
- **Rate Limiting**: Built-in protection against API rate limits
- **Checkpointing**: Save/resume at any pipeline phase
- **CLI Testing**: Test each component independently

## 📄 License
Internal project for expert Astrology AI system development.
