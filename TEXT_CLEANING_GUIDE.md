# Text Cleaning Pipeline - Usage Guide

## Overview

After extracting text from PDFs, the raw content needs cleaning before creating chunks for the vector database. This pipeline handles:

✅ **Remove Artifacts**
- Page numbers
- Headers and footers  
- Running titles
- PDF conversion artifacts

✅ **Fix Text Flow**
- Join sentences split across lines
- Handle hyphenated words at line breaks
- Remove unnecessary line breaks
- Preserve logical paragraph breaks

✅ **Handle Page Transitions**
- Remove page break markers
- Deduplicate repeated headers/footers
- Merge content across pages

✅ **Preserve Important Elements**
- Verse numbers and structure
- Sanskrit text (transliterated and Devanagari)
- Chapter/section headings
- Tables and lists
- Bullet points

✅ **Normalize Formatting**
- Standardize whitespace
- Fix quotes and special characters
- Normalize punctuation

---

## Three Cleaning Methods

### 1. Rule-Based (Fast, Free)
```bash
python src/rag/text_cleaner.py input.txt -m rule
```
- ⚡ Instant processing
- 💰 No API costs
- ✅ Good for simple text
- ❌ May miss context-specific issues

### 2. LLM-Based (Slower, Highest Quality)
```bash
python src/rag/text_cleaner.py input.txt -m llm
```
- 🎯 Context-aware cleaning
- 📚 Understands astrology content
- ✅ Best quality
- ⏱️ ~2-3 seconds per file
- 💰 Uses API (gemini-flash-lite-latest - cheapest)

### 3. Hybrid (Recommended)
```bash
python src/rag/text_cleaner.py input.txt -m hybrid
```
- ⚡ Rule-based first (instant)
- 🎯 LLM refinement after
- ✅ Best balance of speed/quality
- 💰 Minimal API usage

---

## Usage Examples

### Single File

```bash
# Clean one extracted file
python src/rag/text_cleaner.py test_output/page_1_extracted.txt

# Specify output file
python src/rag/text_cleaner.py test_output/page_1_extracted.txt -o cleaned_page_1.txt

# Use LLM-based cleaning
python src/rag/text_cleaner.py test_output/page_1_extracted.txt -m llm
```

### Batch Processing

```bash
# Clean all extracted files in a directory
python src/rag/text_cleaner.py test_output/ -b

# Custom output directory
python src/rag/text_cleaner.py test_output/ -b -o cleaned_output/

# Use rule-based only (fast, free)
python src/rag/text_cleaner.py test_output/ -b -m rule

# Custom file pattern
python src/rag/text_cleaner.py test_output/ -b -p "*.json"
```

### Python API

```python
from src.rag.text_cleaner import TextCleaner

# Initialize
cleaner = TextCleaner(use_llm=True)

# Clean extracted content
extraction_data = {
    "content": "Raw extracted text...",
    "page_type": "text",
    # ... other fields
}

cleaned_data = cleaner.clean_extraction(extraction_data, method="hybrid")
print(cleaned_data["content"])

# Process file
cleaner.process_file(
    "test_output/page_1_extracted.txt",
    output_file="cleaned/page_1.txt",
    method="hybrid"
)
```

---

## Workflow Integration

### Complete PDF → Clean Text Pipeline

```bash
# Step 1: Extract from PDF
python tests/test_pdf_extraction.py
# Input your PDF path and page numbers
# Output: test_output/page_*.txt

# Step 2: Clean extracted text
python src/rag/text_cleaner.py test_output/ -b -m hybrid
# Output: test_output_cleaned/page_*_cleaned.txt

# Step 3: (Next) Create chunks for vector DB
# Step 4: (Next) Load into ChromaDB
```

---

## Cleaning Rules Detail

### Rule-Based Cleaning

1. **Whitespace Normalization**
   - Collapses multiple spaces to single space
   - Removes excessive newlines
   - Preserves paragraph breaks

2. **Hyphenation Fixes**
   - Joins words split across lines: "astro-\nlogy" → "astrology"

3. **Artifact Removal**
   - Page numbers: "Page 45", "45"
   - Common headers: "Chapter 3", "Section 1.2"

4. **Quote Normalization**
   - Smart quotes → straight quotes
   - Standardizes apostrophes

5. **Punctuation Cleanup**
   - Multiple periods → ellipsis
   - Removes trailing/leading whitespace

### LLM-Based Enhancements

1. **Context-Aware Cleaning**
   - Understands astrology terminology
   - Recognizes Sanskrit vs English text
   - Preserves technical formatting

2. **Intelligent Deduplication**
   - Removes repeated headers from page turns
   - Handles running titles intelligently

3. **Structure Preservation**
   - Keeps verse numbering intact
   - Maintains table structure
   - Preserves list formatting

4. **Multilingual Support**
   - Handles English + Sanskrit text
   - Preserves transliteration schemes
   - Maintains Devanagari script

---

## Cost Considerations

### Rule-Based
- **Cost**: $0
- **Speed**: Instant
- **Quality**: Good for simple text

### LLM-Based (gemini-flash-lite-latest)
- **Cost**: ~$0.000075 per 1000 tokens
- **Example**: 1000 pages (avg 500 tokens each) = ~$0.04
- **Speed**: ~2-3 seconds per file
- **Quality**: Excellent

### Hybrid (Recommended)
- **Cost**: Minimal (only complex cases use LLM)
- **Speed**: Fast (mostly rule-based)
- **Quality**: High

---

## Next Steps

After cleaning:
1. **Chunking** - Create overlapping chunks (500-1000 tokens)
2. **Metadata** - Add source info, chapter, topic tags
3. **Embedding** - Generate vectors with OpenAI embeddings
4. **Storage** - Load into ChromaDB
5. **Retrieval** - Test query quality

See main README for complete RAG pipeline workflow.
