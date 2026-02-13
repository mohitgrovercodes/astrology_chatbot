<!-- src\rag\extraction\README.md -->
# Vision LLM Extraction Pipeline for Astrology Texts

A production-ready extraction system for scanned Vedic and Western astrology texts using Google Gemini 1.5 Pro Vision.

## Why Vision LLM?

Traditional OCR (Tesseract, Document AI, PaddleOCR) struggles with:
- ❌ Complex table layouts (merged cells, borderless tables)
- ❌ Multilingual content (Sanskrit + English)
- ❌ Context preservation (what text relates to what table?)
- ❌ Astrological terminology

Vision LLMs (Gemini 1.5 Pro) excel at:
- ✅ Understanding document layout and structure
- ✅ Recognizing patterns even in borderless tables
- ✅ Preserving semantic relationships
- ✅ Handling multilingual text accurately

## Features

- **Page Classification**: Automatically classifies pages as text-heavy, table-heavy, mixed, or chart
- **Structured Extraction**: Extracts Sanskrit shlokas, English translations, notes, and tables
- **Table Understanding**: Parses complex astrological tables into structured data
- **RAG-Ready Output**: Generates chunks optimized for embedding and retrieval
- **Rich Metadata**: Includes topic classification, verse numbers, languages present

## Installation

```bash
# 1. Clone/copy the rag_extraction folder to your project

# 2. Install dependencies
pip install google-generativeai pdf2image pillow pydantic numpy

# 3. Install Poppler (for PDF conversion)
# Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases
# Linux: apt-get install poppler-utils
# Mac: brew install poppler

# 4. Set your API key
export GOOGLE_API_KEY="your-gemini-api-key"
```

## Quick Start

```python
from rag_extraction import VisionPipeline, PipelineConfig

# Configure
config = PipelineConfig(
    book_title="Brihat Parasara Hora Shastra",
    output_dir="./extraction_output",
    astrology_system="vedic",
)

# Initialize
pipeline = VisionPipeline(config)

# Extract
result = pipeline.process_pdf(
    pdf_path="./BPHS.pdf",
    start_page=1,
    end_page=50,
)

# Get RAG chunks
chunks = pipeline.create_rag_chunks(result)
print(f"Created {len(chunks)} RAG-ready chunks")
```

## Output Formats

The pipeline generates multiple output files:

| File | Description |
|------|-------------|
| `{book}_extraction.json` | Complete structured extraction with all metadata |
| `{book}_rag_chunks.json` | Ready-to-embed chunks for RAG |
| `{book}_text.txt` | Plain text for reference |
| `{book}_content.md` | Markdown with formatted tables |
| `raw_responses/` | Raw Gemini responses for debugging |

## RAG Chunk Format

```json
{
  "chunk_id": "chunk_00042",
  "text": "[Verse 13-14]\n\nशीषोर्दयी...\n\nVirgo described: The sign Virgo...",
  "metadata": {
    "page_type": "text_heavy",
    "has_tables": false,
    "languages": ["english", "sanskrit"],
    "extraction_confidence": 0.9
  },
  "source_book": "Brihat Parasara Hora Shastra",
  "source_chapter": "Zodiacal Signs Described",
  "source_page": 56,
  "content_type": "verse",
  "topic": "sign_characteristics",
  "verse_numbers": "13-14",
  "has_sanskrit": true
}
```

## Configuration Options

```python
@dataclass
class ExtractionConfig:
    # Model Strategy
    primary_model: str = "gemini-2.5-flash-lite"  # default for text_heavy
    table_model: str = "gemini-2.5-flash"        # default for tables/mixed
    upgrade_model: str = "gemini-2.5-pro"        # for retries
    
    # Thresholds
    confidence_threshold: float = 0.8
    delay_between_requests: float = 2.0
    
    # Output
    output_dir: str = "./extraction_output"
    save_raw_responses: bool = True
```

## File Structure

```
rag_extraction/
├── vision_pipeline.py       # Main pipeline orchestration
├── vision_extractor.py      # Core logic (Two-tier, retries, validation)
├── extraction_prompts.py    # Astrology-specific Vision LLM prompts
├── extraction_schemas.py    # Pydantic models for structured output
└── README.md
```

## Integration with Existing Pipeline

If you have an existing table detection pipeline, you can integrate:

```python
# Option 1: Replace Document AI entirely
from rag_extraction import VisionPipeline

vision = VisionPipeline()
extracted = vision.process_single_page(image, page_num)

# Option 2: Use for tables only
from rag_extraction import VisionExtractor

extractor = VisionExtractor()
table_data = extractor.extract_complex_table(table_image)

# Option 3: Hybrid (your detection + Vision extraction)
if detected_tables:
    extracted = vision.process_single_page(
        image, page_num, 
        force_type=PageType.TABLE_HEAVY
    )
```

## Cost Estimation

Gemini 1.5 Pro pricing (as of 2024):
- ~$1.25 per 1M input tokens
- ~$5.00 per 1M output tokens
- Images: ~250-500 tokens per image (depending on resolution)

For a 500-page book at 200 DPI:
- Estimated cost: $5-15 total
- Processing time: ~25-50 minutes (with rate limiting)

For lower cost, use `gemini-1.5-flash` (8x cheaper, still good quality).

## Next Steps: Chunking for RAG

The RAG chunks from this pipeline can be directly used with:

```python
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Load chunks
with open("extraction_output/bphs_rag_chunks.json") as f:
    chunks = json.load(f)

# Create documents
from langchain.schema import Document

documents = [
    Document(
        page_content=chunk["text"],
        metadata={
            "source": chunk["source_book"],
            "page": chunk["source_page"],
            "content_type": chunk["content_type"],
            "topic": chunk["topic"],
            "has_sanskrit": chunk["has_sanskrit"],
        }
    )
    for chunk in chunks
]

# Embed and store
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
    persist_directory="./astrology_vectordb",
)
```

## Troubleshooting

### "Response blocked by safety filters"
Gemini may block some astrological content. Try:
- Processing in smaller batches
- Using the Flash model instead of Pro

### Rate limiting errors
Increase `delay_between_requests` in config (default is 3 seconds).

### Poor table extraction
For very complex tables, use `extractor.extract_complex_table()` which uses a specialized prompt.

### Sanskrit text issues
Ensure your terminal/editor supports Unicode. Check `raw_responses/` for actual extracted text.

## License

Part of the Astrology AI Chatbot project.
