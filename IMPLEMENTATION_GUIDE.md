# Step-by-Step Implementation Guide
## Vision LLM Extraction for Astrology Texts

This guide walks you through implementing the Vision LLM extraction system from scratch.

---

## STEP 1: Project Setup

### 1.1 Create Project Directory Structure

```bash
# Navigate to your astro_chatbot project
cd astro_chatbot

# Create the RAG extraction directory
mkdir -p src/rag/extraction
cd src/rag/extraction
```

### 1.2 Copy the Extraction Files

Copy these files from the provided package to `src/rag/extraction/`:

```
src/rag/extraction/
├── __init__.py
├── vision_pipeline.py
├── vision_extractor.py
├── extraction_prompts.py
├── extraction_schemas.py
├── demo_extraction.py
├── requirements.txt
└── README.md
```

---

## STEP 2: Install Dependencies

### 2.1 System Dependencies (Poppler for PDF conversion)

**Windows:**
```bash
# Download Poppler from:
# https://github.com/oschwartz10612/poppler-windows/releases

# Extract to C:\poppler

# Add to PATH:
# C:\poppler\Library\bin
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

### 2.2 Python Dependencies

```bash
# Activate your virtual environment first
cd astro_chatbot
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install google-generativeai>=0.3.0
pip install pdf2image>=1.16.0
pip install Pillow>=10.0.0
pip install pydantic>=2.0.0
pip install numpy>=1.24.0
```

### 2.3 Verify Installation

```python
# test_dependencies.py
import google.generativeai as genai
from pdf2image import convert_from_path
from PIL import Image
import pydantic
import numpy as np

print("✓ google-generativeai:", genai.__version__ if hasattr(genai, '__version__') else "installed")
print("✓ pdf2image: installed")
print("✓ Pillow:", Image.__version__)
print("✓ pydantic:", pydantic.__version__)
print("✓ numpy:", np.__version__)
print("\n✅ All dependencies installed!")
```

Run: `python test_dependencies.py`

---

## STEP 3: Get Google Gemini API Key

### 3.1 Create Google AI Studio Account

1. Go to: https://aistudio.google.com/
2. Sign in with your Google account
3. Click "Get API Key" in the left sidebar
4. Click "Create API Key"
5. Copy the API key

### 3.2 Set Environment Variable

**Linux/Mac (add to ~/.bashrc or ~/.zshrc):**
```bash
export GOOGLE_API_KEY="your-api-key-here"

# Apply changes
source ~/.bashrc
```

**Windows (PowerShell):**
```powershell
# Temporary (current session only)
$env:GOOGLE_API_KEY = "your-api-key-here"

# Permanent (run as Administrator)
[System.Environment]::SetEnvironmentVariable('GOOGLE_API_KEY', 'your-api-key-here', 'User')
```

**Or create a .env file in your project:**
```bash
# astro_chatbot/.env
GOOGLE_API_KEY=your-api-key-here
```

### 3.3 Verify API Key Works

```python
# test_gemini.py
import os
import google.generativeai as genai

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not set!")
    exit(1)

genai.configure(api_key=api_key)

# Test with a simple prompt
model = genai.GenerativeModel('gemini-1.5-flash')
response = model.generate_content("Say 'Hello, Astrology!'")
print("✅ Gemini API working!")
print(f"Response: {response.text}")
```

Run: `python test_gemini.py`

---

## STEP 4: Test with a Single Image

### 4.1 Create a Test Script

```python
# test_single_page.py
import os
import sys
from pathlib import Path

# Add the extraction module to path
sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

from pdf2image import convert_from_path
import numpy as np

# Convert first page of your PDF to image
pdf_path = "path/to/your/astrology_book.pdf"
images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)

# Save for inspection
images[0].save("test_page.png")
print(f"✅ Saved test_page.png ({images[0].size})")

# Convert to numpy array (what the extractor expects)
image_array = np.array(images[0])
print(f"✅ Image array shape: {image_array.shape}")
```

### 4.2 Test Page Classification

```python
# test_classification.py
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

from pdf2image import convert_from_path
import numpy as np
from vision_extractor import VisionExtractor, ExtractionConfig

# Load test image
pdf_path = "path/to/your/bphs.pdf"  # UPDATE THIS
images = convert_from_path(pdf_path, dpi=200, first_page=56, last_page=56)
image = np.array(images[0])

# Initialize extractor
config = ExtractionConfig(
    model_name="gemini-1.5-flash",  # Use flash for testing (cheaper)
    temperature=0.1,
    delay_between_requests=2.0,
    output_dir="./test_output",
)
extractor = VisionExtractor(config)

# Classify the page
page_type, metadata = extractor.classify_page(image)

print(f"\n📄 Page Classification Results:")
print(f"   Type: {page_type.value}")
print(f"   Book: {metadata.get('book_title', 'Unknown')}")
print(f"   Chapter: {metadata.get('chapter_title', 'Unknown')}")
print(f"   Has Sanskrit: {metadata.get('has_sanskrit', False)}")
print(f"   Has Tables: {metadata.get('has_tables', False)}")
print(f"   Confidence: {metadata.get('confidence', 0):.2f}")
```

---

## STEP 5: Extract a Single Page

### 5.1 Full Single Page Extraction

```python
# extract_single_page.py
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

from pdf2image import convert_from_path
import numpy as np
from vision_extractor import VisionExtractor, ExtractionConfig

# Configuration
PDF_PATH = "path/to/your/bphs.pdf"  # UPDATE THIS
PAGE_NUMBER = 56  # Test with a text-heavy page first
OUTPUT_DIR = "./test_output"

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load page image
print(f"📄 Loading page {PAGE_NUMBER}...")
images = convert_from_path(PDF_PATH, dpi=200, first_page=PAGE_NUMBER, last_page=PAGE_NUMBER)
image = np.array(images[0])
print(f"   Image size: {image.shape}")

# Initialize extractor
print("🔧 Initializing extractor...")
config = ExtractionConfig(
    model_name="gemini-1.5-pro",  # Use Pro for better quality
    temperature=0.1,
    delay_between_requests=3.0,
    save_raw_responses=True,
    output_dir=OUTPUT_DIR,
)
extractor = VisionExtractor(config)

# Extract content
print("🚀 Extracting content...")
extracted_page = extractor.extract_page(
    image=image,
    page_num=PAGE_NUMBER,
    book_title="Brihat Parasara Hora Shastra",
)

# Display results
print(f"\n✅ Extraction Complete!")
print(f"   Page Type: {extracted_page.metadata.page_type.value}")
print(f"   Content Blocks: {len(extracted_page.content_blocks)}")
print(f"   Confidence: {extracted_page.extraction_confidence:.2f}")

print(f"\n📝 Content Blocks:")
for i, block in enumerate(extracted_page.content_blocks):
    print(f"\n   [{i+1}] {block.content_type.value.upper()}")
    print(f"       Text preview: {block.text[:100]}..." if len(block.text) > 100 else f"       Text: {block.text}")
    
    if block.verse_data:
        print(f"       Verse: {block.verse_data.verse_number}")
    if block.table_data:
        print(f"       Table: {block.table_data.title}")

# Save full result
output_path = Path(OUTPUT_DIR) / f"page_{PAGE_NUMBER}_extraction.json"
with open(output_path, "w", encoding="utf-8") as f:
    result_dict = {
        "page_number": extracted_page.metadata.page_number,
        "page_type": extracted_page.metadata.page_type.value,
        "confidence": extracted_page.extraction_confidence,
        "content_blocks": [
            {
                "type": block.content_type.value,
                "text": block.text,
                "verse_data": block.verse_data.model_dump() if block.verse_data else None,
                "table_data": block.table_data.model_dump() if block.table_data else None,
            }
            for block in extracted_page.content_blocks
        ],
        "raw_text": extracted_page.raw_text,
    }
    json.dump(result_dict, f, ensure_ascii=False, indent=2)

print(f"\n💾 Saved to: {output_path}")
```

---

## STEP 6: Process Multiple Pages

### 6.1 Batch Processing Script

```python
# process_batch.py
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

from vision_pipeline import VisionPipeline, PipelineConfig

# Configuration
PDF_PATH = "path/to/your/bphs.pdf"  # UPDATE THIS
START_PAGE = 1
END_PAGE = 10  # Start small for testing
OUTPUT_DIR = "./bphs_extraction"

# Create pipeline configuration
config = PipelineConfig(
    # PDF settings
    pdf_dpi=200,
    
    # Gemini settings
    gemini_model="gemini-1.5-pro",  # or "gemini-1.5-flash" for lower cost
    temperature=0.1,
    
    # Rate limiting (important!)
    delay_between_requests=3.0,  # 3 seconds between API calls
    
    # Output
    output_dir=OUTPUT_DIR,
    save_raw_responses=True,
    save_page_images=True,  # Save images for debugging
    
    # Book metadata
    book_title="Brihat Parasara Hora Shastra",
    astrology_system="vedic",
)

# Progress callback
def progress(current, total, page_num):
    print(f"  Progress: {current}/{total} (Page {page_num})")

# Initialize pipeline
print("🔧 Initializing Vision Pipeline...")
pipeline = VisionPipeline(config)

# Process PDF
print(f"\n🚀 Processing {PDF_PATH}")
print(f"   Pages: {START_PAGE} to {END_PAGE}")

result = pipeline.process_pdf(
    pdf_path=PDF_PATH,
    start_page=START_PAGE,
    end_page=END_PAGE,
    progress_callback=progress,
)

# Summary
print(f"\n✅ Processing Complete!")
print(f"   Total pages: {result.total_pages}")
print(f"   Successful: {result.extraction_stats.get('successful', 0)}")
print(f"   Failed: {result.extraction_stats.get('failed', 0)}")
print(f"   Content blocks: {result.extraction_stats.get('total_content_blocks', 0)}")

print(f"\n📁 Output files in: {OUTPUT_DIR}/")
```

---

## STEP 7: Generate RAG Chunks

### 7.1 Create RAG-Ready Chunks

```python
# generate_rag_chunks.py
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

from vision_pipeline import VisionPipeline, PipelineConfig

# Load existing extraction result or process new
OUTPUT_DIR = "./bphs_extraction"
EXTRACTION_FILE = f"{OUTPUT_DIR}/bphs_extraction.json"

# Option 1: Load existing extraction
if os.path.exists(EXTRACTION_FILE):
    print(f"📂 Loading existing extraction from {EXTRACTION_FILE}")
    with open(EXTRACTION_FILE, "r", encoding="utf-8") as f:
        extraction_data = json.load(f)
    
    # Reconstruct result object (simplified - in practice, use proper deserialization)
    print(f"   Loaded {len(extraction_data.get('pages', []))} pages")

# Option 2: Process and generate chunks in one go
else:
    print("🔧 No existing extraction found. Processing PDF...")
    
    config = PipelineConfig(
        output_dir=OUTPUT_DIR,
        book_title="Brihat Parasara Hora Shastra",
    )
    
    pipeline = VisionPipeline(config)
    result = pipeline.process_pdf(
        pdf_path="path/to/your/bphs.pdf",
        start_page=1,
        end_page=50,
    )
    
    # Generate RAG chunks
    chunks = pipeline.create_rag_chunks(result)
    
    print(f"\n✅ Generated {len(chunks)} RAG chunks")
    
    # Display sample chunks
    print("\n📝 Sample Chunks:")
    for chunk in chunks[:3]:
        print(f"\n   Chunk: {chunk.chunk_id}")
        print(f"   Type: {chunk.content_type}")
        print(f"   Topic: {chunk.topic}")
        print(f"   Page: {chunk.source_page}")
        print(f"   Text: {chunk.text[:150]}...")
```

---

## STEP 8: Integrate with ChromaDB

### 8.1 Load Chunks into ChromaDB

```python
# load_to_chromadb.py
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

# Install if needed: pip install langchain-openai langchain-chroma chromadb

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document

# Configuration
CHUNKS_FILE = "./bphs_extraction/bphs_rag_chunks.json"
CHROMA_DIR = "./data/vectordb"
COLLECTION_NAME = "astrology_knowledge"

# Verify OpenAI API key is set
if not os.environ.get("OPENAI_API_KEY"):
    print("❌ OPENAI_API_KEY not set!")
    print("   Set it with: export OPENAI_API_KEY='your-key'")
    exit(1)

# Load chunks
print(f"📂 Loading chunks from {CHUNKS_FILE}")
with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)
print(f"   Loaded {len(chunks)} chunks")

# Convert to LangChain Documents
print("\n🔄 Converting to LangChain Documents...")
documents = []
for chunk in chunks:
    doc = Document(
        page_content=chunk["text"],
        metadata={
            "chunk_id": chunk["chunk_id"],
            "source_book": chunk["source_book"],
            "source_chapter": chunk.get("source_chapter"),
            "source_page": chunk["source_page"],
            "content_type": chunk["content_type"],
            "topic": chunk.get("topic"),
            "verse_numbers": chunk.get("verse_numbers"),
            "has_sanskrit": chunk.get("has_sanskrit", False),
            "astrology_system": "vedic",
        }
    )
    documents.append(doc)

print(f"   Created {len(documents)} documents")

# Initialize embeddings
print("\n🔧 Initializing OpenAI Embeddings...")
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    dimensions=3072,
)

# Create/load ChromaDB
print(f"\n💾 Creating ChromaDB at {CHROMA_DIR}...")
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
    collection_name=COLLECTION_NAME,
    persist_directory=CHROMA_DIR,
)

print(f"\n✅ Successfully loaded {len(documents)} documents into ChromaDB!")
print(f"   Collection: {COLLECTION_NAME}")
print(f"   Directory: {CHROMA_DIR}")

# Test retrieval
print("\n🔍 Testing retrieval...")
results = vectorstore.similarity_search(
    "What are the characteristics of Virgo sign?",
    k=3,
)

print(f"\nTop 3 results for 'What are the characteristics of Virgo sign?':")
for i, doc in enumerate(results):
    print(f"\n   [{i+1}] Page {doc.metadata.get('source_page')}")
    print(f"       Type: {doc.metadata.get('content_type')}")
    print(f"       Text: {doc.page_content[:200]}...")
```

---

## STEP 9: Full Integration Example

### 9.1 Complete End-to-End Script

```python
# full_extraction_pipeline.py
"""
Complete end-to-end extraction pipeline:
1. PDF → Images
2. Images → Structured Content (Gemini Vision)
3. Structured Content → RAG Chunks
4. RAG Chunks → ChromaDB
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add extraction module to path
sys.path.insert(0, str(Path(__file__).parent / "src/rag/extraction"))

from vision_pipeline import VisionPipeline, PipelineConfig

# =============================================================================
# CONFIGURATION
# =============================================================================

PDF_PATH = "path/to/Brihat_Parasara_Hora_Shastra.pdf"  # UPDATE THIS
BOOK_TITLE = "Brihat Parasara Hora Shastra"
OUTPUT_DIR = f"./extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Page range (start small for testing!)
START_PAGE = 1
END_PAGE = 10  # Increase once you've verified quality

# Model selection
USE_FLASH = False  # True = cheaper/faster, False = better quality

# =============================================================================
# VALIDATION
# =============================================================================

def validate_setup():
    """Validate all prerequisites are met."""
    errors = []
    
    # Check PDF exists
    if not os.path.exists(PDF_PATH):
        errors.append(f"PDF not found: {PDF_PATH}")
    
    # Check API key
    if not os.environ.get("GOOGLE_API_KEY"):
        errors.append("GOOGLE_API_KEY environment variable not set")
    
    # Check Poppler
    try:
        from pdf2image import convert_from_path
        # Quick test
        if os.path.exists(PDF_PATH):
            convert_from_path(PDF_PATH, first_page=1, last_page=1, dpi=72)
    except Exception as e:
        errors.append(f"Poppler not working: {e}")
    
    if errors:
        print("❌ Setup validation failed:")
        for err in errors:
            print(f"   - {err}")
        return False
    
    print("✅ Setup validation passed!")
    return True

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def main():
    print("="*70)
    print("VISION LLM EXTRACTION PIPELINE")
    print("="*70)
    print(f"Book: {BOOK_TITLE}")
    print(f"PDF: {PDF_PATH}")
    print(f"Pages: {START_PAGE} to {END_PAGE}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Model: {'gemini-1.5-flash' if USE_FLASH else 'gemini-1.5-pro'}")
    print("="*70)
    
    # Validate setup
    if not validate_setup():
        return
    
    # Create pipeline config
    config = PipelineConfig(
        pdf_dpi=200,
        gemini_model="gemini-1.5-flash" if USE_FLASH else "gemini-1.5-pro",
        temperature=0.1,
        delay_between_requests=3.0,
        output_dir=OUTPUT_DIR,
        save_raw_responses=True,
        save_page_images=False,
        book_title=BOOK_TITLE,
        astrology_system="vedic",
    )
    
    # Progress callback
    def on_progress(current, total, page_num):
        pct = (current / total) * 100
        print(f"   [{current}/{total}] Page {page_num} ({pct:.0f}%)")
    
    # Initialize pipeline
    print("\n🔧 Initializing pipeline...")
    pipeline = VisionPipeline(config)
    
    # Process PDF
    print(f"\n🚀 Starting extraction...")
    result = pipeline.process_pdf(
        pdf_path=PDF_PATH,
        start_page=START_PAGE,
        end_page=END_PAGE,
        progress_callback=on_progress,
    )
    
    # Generate RAG chunks
    print("\n📦 Generating RAG chunks...")
    chunks = pipeline.create_rag_chunks(result)
    
    # Final summary
    print("\n" + "="*70)
    print("EXTRACTION COMPLETE")
    print("="*70)
    print(f"✅ Pages processed: {result.total_pages}")
    print(f"✅ Successful: {result.extraction_stats.get('successful', 0)}")
    print(f"✅ Failed: {result.extraction_stats.get('failed', 0)}")
    print(f"✅ Content blocks: {result.extraction_stats.get('total_content_blocks', 0)}")
    print(f"✅ RAG chunks: {len(chunks)}")
    print(f"\n📁 Output directory: {OUTPUT_DIR}/")
    print("   - *_extraction.json  (full structured data)")
    print("   - *_rag_chunks.json  (ready for embedding)")
    print("   - *_text.txt         (plain text)")
    print("   - *_content.md       (formatted markdown)")
    print("="*70)

if __name__ == "__main__":
    main()
```

---

## STEP 10: Troubleshooting

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| `GOOGLE_API_KEY not set` | Set environment variable: `export GOOGLE_API_KEY="your-key"` |
| `Poppler not found` | Install Poppler and add to PATH |
| `Rate limit exceeded` | Increase `delay_between_requests` to 5-10 seconds |
| `Response blocked by safety` | Use `gemini-1.5-flash` or process in smaller batches |
| `JSON parse error` | Check `raw_responses/` folder for actual API responses |
| `Poor Sanskrit extraction` | Increase DPI to 300, use Pro model instead of Flash |
| `Tables not structured` | Try `extractor.extract_complex_table()` for difficult tables |

### Debugging Tips

```python
# 1. Check raw API responses
# Look in: OUTPUT_DIR/raw_responses/raw_response_page_XXX.json

# 2. Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# 3. Test with a single page first
# Always start with START_PAGE=X, END_PAGE=X (same page)

# 4. Compare extraction quality
# Save page images with save_page_images=True
# Compare original image with extracted content
```

---

## Quick Reference: File Locations

After running the pipeline, you'll have:

```
OUTPUT_DIR/
├── bphs_extraction.json      # Full structured data
├── bphs_rag_chunks.json      # RAG-ready chunks
├── bphs_text.txt             # Plain text
├── bphs_content.md           # Formatted markdown
├── page_images/              # (if save_page_images=True)
│   ├── page_001.png
│   └── ...
└── raw_responses/            # (if save_raw_responses=True)
    ├── raw_response_page_001.json
    └── ...
```

---

## Next Steps After Extraction

Once you have `*_rag_chunks.json`:

1. **Load into ChromaDB** (Step 8)
2. **Build retriever** with metadata filtering
3. **Connect to LLM** for RAG responses
4. **Test retrieval quality** with sample queries

Need help with any specific step? Let me know!
