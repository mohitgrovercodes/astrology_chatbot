# 🌟 Astrology AI Chatbot - Quick Start Guide

Complete step-by-step instructions to run your RAG-powered astrology chatbot.

## 📋 Prerequisites

- Python 3.8+
- OpenAI API key (for embeddings)
- Google Cloud credentials (for Vertex AI/Gemini)
- Optional: Cohere API key (for reranking)

---

## 🚀 Step 1: Install Dependencies

```bash
# Core dependencies
pip install pydantic google-generativeai openai chromadb langchain-google-vertexai
pip install pillow numpy pdf2image

# Retrieval improvements
pip install rank-bm25 tiktoken

# Optional: Reranking
pip install cohere  # For Cohere Rerank API
pip install sentence-transformers  # For local cross-encoder
```

---

## 🔑 Step 2: Set API Keys

### Windows (PowerShell)
```powershell
$env:OPENAI_API_KEY="your_openai_api_key"
$env:GOOGLE_APPLICATION_CREDENTIALS="path\to\google_credentials.json"
$env:COHERE_API_KEY="your_cohere_key"  # Optional
```

### Linux/Mac
```bash
export OPENAI_API_KEY="your_openai_api_key"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/google_credentials.json"
export COHERE_API_KEY="your_cohere_key"  # Optional
```

### Or create `.env` file
```bash
OPENAI_API_KEY=your_openai_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/google_credentials.json
COHERE_API_KEY=your_cohere_key
```

---

## 📚 Step 3: Process Your PDF (If Starting Fresh)

### Option A: Full Pipeline (Recommended)
```bash
# Process PDF through all 7 phases
python src/rag/preprocessing/pipeline.py input.pdf --output-dir preprocessing_output
```

### Option B: Step-by-Step

**Phase 1: Extract PDF**
```bash
python batch_extract.py book.pdf --start 1 --end 99 --workers 5
```

**Phases 2-5: Clean & Enrich**
```bash
python run_preprocessing_phases.py --input extraction_output/page_1.json
```

**Phase 6: Embed**
```bash
python src/rag/preprocessing/embedder.py preprocessing_output/enriched.json
```

**Phase 7: Build Vector DB**
```bash
python src/rag/preprocessing/vector_db_builder.py preprocessing_output/embedded.json --reset
```

---

## 💬 Step 4: Run the Chatbot!

### Basic Usage (Gemini)
```bash
python chatbot.py
```

### With OpenAI
```bash
python chatbot.py --provider openai --model gpt-4o
```

### With Reranking (Best Quality)
```bash
python chatbot.py --provider google --model gemini-2.0-flash-exp --rerank
```

### Custom Collection
```bash
python chatbot.py --collection "your_collection_name"
```

---

## 🎯 Step 5: Use the Chatbot

Once running, you'll see:
```
╔══════════════════════════════════════════════════════════════╗
║          🌟 Astrology AI Chatbot 🌟                         ║
╚══════════════════════════════════════════════════════════════╝

🔮 You: 
```

### Example Questions
```
What does Mars in the 5th house signify?
Explain the concept of Gulika
What are the effects of Jupiter in Aries?
How does Saturn influence the 10th house?
```

### Commands
```
/help                    - Show help
/filter planet=Mars      - Filter by planet
/filter house=5          - Filter by house
/filter clear            - Clear filters
/sources on|off          - Toggle source citations
/clear                   - Clear conversation history
/quit                    - Exit
```

---

## 🧪 Step 6: Test Retrieval (Optional)

### Test Semantic Search
```bash
python src/rag/retriever.py "Mars in 5th house" --top-k 5
```

### Test Hybrid Search
```bash
python src/rag/retriever.py "Mars in 5th house" --hybrid --top-k 5
```

### Test with Filters
```bash
python src/rag/retriever.py "planetary effects" --filter-planet Mars --filter-house 5
```

### Test RAG Engine
```bash
python src/rag/rag_engine.py "What is the significance of the 10th house?"
```

---

## 📊 Step 7: Check Your Data

### View Collection Stats
```bash
python src/rag/preprocessing/vector_db_builder.py --stats --collection brihat_parasara_hora_sastra
```

### View Collection Info
```bash
python src/rag/retriever.py --info
```

---

## 🎨 Advanced Usage

### Full-Featured Chatbot
```bash
python chatbot.py \
  --provider google \
  --model gemini-2.0-flash-exp \
  --collection brihat_parasara_hora_sastra \
  --rerank \
  --reranker-method cohere
```

### Sub-Chunk Large Chunks
```bash
python src/rag/preprocessing/subchunker.py \
  preprocessing_output/enriched.json \
  --output preprocessing_output/subchunked.json \
  --max-size 500
```

---

## 🐛 Troubleshooting

### Issue: "Collection not found"
```bash
# Rebuild vector database
python src/rag/preprocessing/vector_db_builder.py preprocessing_output/embedded.json --reset
```

### Issue: "No OpenAI API key"
```bash
# Check environment variable
echo $OPENAI_API_KEY  # Linux/Mac
echo $env:OPENAI_API_KEY  # Windows PowerShell
```

### Issue: "Vertex AI not initialized"
```bash
# Check Google credentials
echo $GOOGLE_APPLICATION_CREDENTIALS
# Verify file exists
ls $GOOGLE_APPLICATION_CREDENTIALS
```

### Issue: Rate limits
The system has built-in retry logic, but you can:
- Reduce batch size in embedder
- Add delays between requests
- Use rate limiting in LLM factory

---

## 📁 Project Structure

```
astro_chatbot/
├── chatbot.py                 # 🤖 Main chatbot CLI
├── batch_extract.py           # Phase 1: PDF extraction
├── run_preprocessing_phases.py # Phases 2-5
├── src/
│   ├── rag/
│   │   ├── retriever.py       # Semantic + hybrid search
│   │   ├── rag_engine.py      # Answer generation
│   │   ├── reranker.py        # Reranking module
│   │   └── preprocessing/
│   │       ├── embedder.py    # Phase 6: Embeddings
│   │       ├── vector_db_builder.py  # Phase 7: ChromaDB
│   │       └── subchunker.py  # Sub-chunking utility
│   └── llm/
│       └── factory.py         # LLM factory (Gemini/OpenAI)
└── data/
    └── vectordb/              # ChromaDB storage
```

---

## ✅ Quick Verification

Run these commands to verify everything works:

```bash
# 1. Check dependencies
python -c "import chromadb, openai, google.generativeai; print('✅ All imports OK')"

# 2. Check API keys
python -c "import os; print('OpenAI:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING')"

# 3. Check vector DB
python src/rag/retriever.py --info

# 4. Test retrieval
python src/rag/retriever.py "test query" --top-k 3

# 5. Run chatbot
python chatbot.py
```

---

## 🎯 Current Status

Your system has:
- ✅ 163 chunks indexed
- ✅ 74 Sanskrit verses
- ✅ Full metadata (planets, houses, signs, etc.)
- ✅ Hybrid search (semantic + BM25)
- ✅ Query expansion
- ✅ Reranking support
- ✅ Multi-LLM support (Gemini/OpenAI)

---

## 🆘 Need Help?

1. Check the [walkthrough.md](file:///C:/Users/Hp/.gemini/antigravity/brain/c2061dfa-b7f1-4646-bdd4-85d2f8f4fd37/walkthrough.md) for detailed feature documentation
2. Review error messages - they usually indicate missing API keys or dependencies
3. Verify your data is in `data/vectordb/`

**Happy chatting! 🌙✨**
