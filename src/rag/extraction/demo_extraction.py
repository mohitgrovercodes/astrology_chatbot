"""
Demonstration script for the Vision LLM Extraction Pipeline.

This script shows how to:
1. Process different types of astrology book pages
2. Handle text-heavy, table-heavy, and mixed content
3. Generate RAG-ready output

Usage:
    # Set your API key first
    export GOOGLE_API_KEY="your-api-key"
    
    # Run the demo
    python demo_extraction.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from vision_pipeline import VisionPipeline, PipelineConfig
from extraction_schemas import PageType


def demo_single_page_classification():
    """Demo: Classify a single page type."""
    print("\n" + "="*70)
    print("DEMO 1: Page Classification")
    print("="*70)
    
    # This would use an actual image
    # For demo, we just show the expected output
    
    print("""
Expected output for a text-heavy page:
{
    "page_type": "text_heavy",
    "book_title": "Brihat Parasara Hora Shastra",
    "chapter_title": "Zodiacal Signs Described",
    "chapter_number": null,
    "has_sanskrit": true,
    "has_tables": false,
    "has_charts": false,
    "page_number": 56,
    "confidence": 0.95
}

Expected output for a table-heavy page:
{
    "page_type": "table_heavy",
    "book_title": "Brihat Parasara Hora Shastra",
    "chapter_title": "Planetary Characters And Description",
    "has_tables": true,
    "confidence": 0.92
}
""")


def demo_text_extraction():
    """Demo: What text extraction output looks like."""
    print("\n" + "="*70)
    print("DEMO 2: Text-Heavy Page Extraction")
    print("="*70)
    
    print("""
Sample extraction from a text-heavy page (bphs_textheavy.pdf):

{
    "page_number": 56,
    "chapter_title": "Zodiacal Signs Described",
    "content_blocks": [
        {
            "type": "shloka",
            "verse_number": "13-14",
            "sanskrit_text": "शीषोर्दयी दयुवीर्यादयस्तुलः कृष्णो रजोगुणी । पश्चिमो भूचरो घाती श्रो पध्यतनुिपात्‌ ॥९५ ॥",
            "english_text": null,
            "topic": "Virgo described"
        },
        {
            "type": "translation",
            "verse_number": "13-14",
            "sanskrit_text": null,
            "english_text": "Virgo described: The sign Virgo has been spoken of as Parvatiya or hillresorter and is strong in the day. It rises with its head and has a medium sized body. It is biped and resides in the South. It has grains and fire in its hands. It is of Vaishya Varna (race) and is variegated. Its element is air; it is virgin and is Tamoguni; it is of child like nature and its lord is Mercury.",
            "topic": "Virgo characteristics"
        },
        {
            "type": "shloka",
            "verse_number": "15-16",
            "sanskrit_text": "शुक्राऽधिपोऽथ स्वल्यांगो बहुपादब्राह्मणो विली । सोप्यस्थो दिनवीर्याढय्‌ः पि्शगों जलभूवहः ।९६ ॥",
            "english_text": null,
            "topic": "Libra and Scorpio described"
        },
        {
            "type": "translation", 
            "verse_number": "15-16",
            "english_text": "The sign Libra rises with its head, is strong in day, has black Complexion, is Rajoguni in nature; it resides in the West and wanders on the earth; it is violent, is of Shudra Varna (race) and has medium sized body and is biped. Its lord is Venus. The Sign Scorpio has slender physique and is multi footed (Centipede). It is Brahmin by Varna (race) and resides in holes. Its direction is north and it is strong in day. Its hue is reddish brown and it resides in both water and land. It has hairy body, very sharp forepart (very sharp sting) and its ruler or Lord is Mars.",
            "topic": "Libra and Scorpio characteristics"
        }
    ],
    "raw_text": "...",
    "extraction_quality": "good",
    "issues": []
}
""")


def demo_table_extraction():
    """Demo: What table extraction output looks like."""
    print("\n" + "="*70)
    print("DEMO 3: Table-Heavy Page Extraction")
    print("="*70)
    
    print("""
Sample extraction from a table-heavy page (bphs_tables.pdf):

{
    "page_number": 32,
    "tables": [
        {
            "table_number": 1,
            "title": "Ritu (Seasons) The Ritus are six",
            "table_type": "seasonal_correspondences",
            "context_before": "Ritu (Seasons) The Ritus are six. Therefore, Ritu is of about two months, because Ritu is the time taken by the Sun in crossing two signs. The Lord of Ritu is Mercury.",
            "headers": ["Ritu", "Situation of the Sun", "Lunar Month"],
            "rows": [
                ["1. Shishir", "Capricorn, Aquarius", "Magh, Phalgun"],
                ["2. Basant", "Pisces, Aries", "Chaitra, Baisakh"],
                ["3. Greeshma", "Taurus, Gemini", "Jyeshta, Ashadha"],
                ["4. Varsha", "Cancer, Leo", "Shravan, Bhadrapada"],
                ["5. Sharad", "Virgo, Libra", "Ashwina, Kartika"],
                ["6. Hemant", "Scorpio, Sagittarius", "Margh Shirsha, Pausa"]
            ],
            "markdown": "| Ritu | Situation of the Sun | Lunar Month |\\n|---|---|---|\\n| 1. Shishir | Capricorn, Aquarius | Magh, Phalgun |\\n| 2. Basant | Pisces, Aries | Chaitra, Baisakh |\\n...",
            "notes": null
        }
    ],
    "other_text": "The time from one sunrise to another sunrise is called one sawan day. In the same way 30 sawan days make one Sawan Masa. Its Lord is Mercury.",
    "extraction_quality": "good",
    "issues": []
}
""")


def demo_rag_chunk():
    """Demo: What a RAG-ready chunk looks like."""
    print("\n" + "="*70)
    print("DEMO 4: RAG-Ready Chunk Format")
    print("="*70)
    
    print("""
RAG chunks are designed for optimal retrieval. Here's an example:

{
    "chunk_id": "chunk_00042",
    "text": "[Verse 13-14]\\n\\nशीषोर्दयी दयुवीर्यादयस्तुलः कृष्णो रजोगुणी...\\n\\nVirgo described: The sign Virgo has been spoken of as Parvatiya or hillresorter and is strong in the day. It rises with its head and has a medium sized body...",
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

This chunk can be:
1. Embedded with OpenAI text-embedding-3-large
2. Stored in ChromaDB with metadata for filtering
3. Retrieved based on semantic similarity AND metadata filters

Example retrieval query:
    retriever.search(
        query="What are the characteristics of Virgo sign?",
        filter={"content_type": "verse", "topic": "sign_characteristics"}
    )
""")


def demo_full_pipeline():
    """Demo: Full pipeline usage."""
    print("\n" + "="*70)
    print("DEMO 5: Full Pipeline Usage")
    print("="*70)
    
    print("""
# Full pipeline usage example:

from vision_pipeline import VisionPipeline, PipelineConfig

# Configure the pipeline
config = PipelineConfig(
    output_dir="./bphs_extraction",
    book_title="Brihat Parasara Hora Shastra",
    astrology_system="vedic",
    pdf_dpi=200,
    gemini_model="gemini-1.5-pro",
)

# Initialize pipeline
pipeline = VisionPipeline(config)

# Process PDF
result = pipeline.process_pdf(
    pdf_path="./Brihat_Parasara_Hora_Shastra.pdf",
    start_page=1,
    end_page=100,  # Process first 100 pages
)

# Access results
print(f"Extracted {result.total_pages} pages")
print(f"Content blocks: {result.extraction_stats['total_content_blocks']}")

# Get RAG-ready chunks
chunks = pipeline.create_rag_chunks(result)
print(f"Created {len(chunks)} RAG chunks")

# Files created:
# ./bphs_extraction/bphs_extraction.json     - Complete structured data
# ./bphs_extraction/bphs_rag_chunks.json     - RAG-ready chunks
# ./bphs_extraction/bphs_text.txt            - Plain text
# ./bphs_extraction/bphs_content.md          - Markdown with tables
# ./bphs_extraction/raw_responses/           - Raw Gemini responses
""")


def demo_integration_with_existing():
    """Demo: How to integrate with existing pipeline."""
    print("\n" + "="*70)
    print("DEMO 6: Integration with Existing Pipeline")
    print("="*70)
    
    print("""
# You can integrate this with your existing BPHSPipeline!

# Option 1: Replace Document AI entirely
# --------------------------------------
# In your pipeline_2.py, modify _process_single_page:

def _process_single_page(self, image, page_num, ...):
    # Use Vision LLM instead of Document AI
    from vision_pipeline import VisionPipeline
    
    vision = VisionPipeline()
    extracted = vision.process_single_page(
        image=image,
        page_num=page_num,
        book_title=self.config.book_title,
    )
    
    return {
        'page_num': page_num,
        'text': extracted.raw_text,
        'content_blocks': extracted.content_blocks,
        # ... etc
    }


# Option 2: Use for table extraction only
# ---------------------------------------
# Keep your current text extraction, but use Vision LLM for tables:

def extract_table_with_vision(self, image, bbox):
    # Crop the table region
    x1, y1, x2, y2 = bbox
    table_image = image[y1:y2, x1:x2]
    
    # Use Vision LLM for the table
    from vision_extractor import VisionExtractor
    
    extractor = VisionExtractor()
    result = extractor.extract_complex_table(table_image)
    
    return result  # Structured table data with markdown


# Option 3: Hybrid approach (recommended)
# --------------------------------------
# Use your existing table detection + Vision LLM extraction:

def hybrid_extract(self, image, detected_tables):
    from vision_pipeline import VisionPipeline
    
    vision = VisionPipeline()
    
    # If tables detected, use table-heavy prompt
    if detected_tables:
        from extraction_schemas import PageType
        extracted = vision.process_single_page(
            image=image,
            page_num=self.current_page,
            force_type=PageType.TABLE_HEAVY,
        )
    else:
        extracted = vision.process_single_page(
            image=image,
            page_num=self.current_page,
        )
    
    return extracted
""")


def main():
    """Run all demos."""
    print("\n")
    print("="*70)
    print("VISION LLM EXTRACTION PIPELINE - DEMONSTRATION")
    print("="*70)
    print("""
This demo shows how the Vision LLM extraction system works for
extracting content from Vedic astrology texts like BPHS.

The system uses Google Gemini 1.5 Pro Vision to:
- Classify page types (text-heavy, table-heavy, mixed)
- Extract Sanskrit shlokas and English translations
- Parse complex astrological tables
- Generate RAG-ready chunks with rich metadata
""")
    
    # Run demos
    demo_single_page_classification()
    demo_text_extraction()
    demo_table_extraction()
    demo_rag_chunk()
    demo_full_pipeline()
    demo_integration_with_existing()
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
1. Set your Google API key:
   export GOOGLE_API_KEY="your-api-key"

2. Install dependencies:
   pip install google-generativeai pdf2image pillow pydantic

3. Install Poppler for PDF conversion:
   - Windows: Download from GitHub releases
   - Linux: apt-get install poppler-utils
   - Mac: brew install poppler

4. Test with a single page:
   python -c "
   from vision_pipeline import VisionPipeline
   pipeline = VisionPipeline()
   # result = pipeline.process_pdf('your_book.pdf', start_page=1, end_page=5)
   "

5. Process your full PDF:
   python vision_pipeline.py your_book.pdf --start 1 --end 100 --output ./output

The extracted content will be ready for your RAG pipeline!
""")


if __name__ == "__main__":
    main()
