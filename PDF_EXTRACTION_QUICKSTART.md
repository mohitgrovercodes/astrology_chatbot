# PDF Extraction Workflow - Quick Start

## ✅ What's Ready

1. **AI Studio API** - Verified working
   - Model: `gemini-2.5-flash`
   - Vision capable
   - API Key configured in `.env`

2. **Extraction Script** - `tests/test_pdf_extraction.py`
   - Single page extraction
   - Batch processing with rate limiting
   - Saves images + extracted text

## 🚀 Quick Test

### Single Page Extraction

```bash
# Activate your venv first
D:\AI\IMGProjects\astro_chatbot\astro_chatbot\venv\python.exe tests\test_pdf_extraction.py
```

**It will prompt you for:**
1. PDF file path
2. Page number to extract

**Output:**
- `test_output/page_N.png` - Converted image
- `test_output/page_N_extracted.txt` - Extracted text in JSON format

### Batch Extraction (Multiple Pages)

Edit `test_pdf_extraction.py` and run the `batch_extract_with_rate_limit()` function:

```python
# Example at bottom of file
results = batch_extract_with_rate_limit(
    pdf_path="path/to/your/bphs.pdf",
    start_page=1,
    end_page=10,  # Start small for testing
    delay_seconds=4.5,  # Respects 15 req/min limit
    output_dir="./batch_output"
)
```

## ⚙️ Rate Limits

**AI Studio Free Tier:**
- 15 requests/minute for gemini-2.5-flash
- Script uses 4.5s delays (safe margin)
- **~12-13 pages per minute**

**For 1000 pages:**
- Estimated time: ~75-80 minutes
- Completely automated
- Free!

## 📝 Extraction Output Format

The script extracts content as JSON:

```json
{
    "page_type": "text|table|mixed|title_page",
    "title": "chapter title if present",
    "content": "full extracted text",
    "has_sanskrit": true/false,
    "verses": ["verse 1", "verse 2"],
    "tables": [{"title": "", "data": []}]
}
```

## 🔧 Next Steps

1. **Test with your PDF** - Try extracting 1-2 pages first
2. **Verify quality** - Check if extraction captures everything needed
3. **Batch process** - Once satisfied, process full document
4. **Chunking** - We'll create RAG chunks from extracted content
5. **Vector DB** - Load into ChromaDB for retrieval

## 📚 Integration with IMPLEMENTATION_GUIDE.md

The `IMPLEMENTATION_GUIDE.md` has more detailed instructions for:
- Different extraction strategies
- Handling complex tables
- Sanskrit text extraction
- Creating RAG chunks
- Loading into ChromaDB

## ⚠️ Important Notes

- **Poppler Required**: Make sure Poppler is installed for PDF→Image conversion
- **Rate Limiting**: Don't reduce delay below 4s to avoid hitting rate limits
- **API Costs**: AI Studio is free but has lower rate limits than paid Vertex AI
- **Quality**: gemini-2.5-flash provides excellent extraction quality

Ready to test with your astrology PDFs!
