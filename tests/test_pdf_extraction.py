# tests\test_pdf_extraction.py
#!/usr/bin/env python3
"""
Test PDF Extraction with Vertex AI (with AI Studio fallback)
Demonstrates Vision LLM extraction with rate limiting
"""

import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from pdf2image import convert_from_path
import numpy as np
import google.generativeai as genai

def extract_pdf_page(pdf_path: str, page_number: int, output_dir: str = "./test_output"):
    """
    Extract a single page from PDF using Gemini Vision
    
    Args:
        pdf_path: Path to PDF file
        page_number: Page number to extract (1-indexed)
        output_dir: Directory to save outputs
    """
    print("=" * 70)
    print(f"PDF EXTRACTION TEST - Page {page_number}")
    print("=" * 70)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize model (Vertex AI with fallback to AI Studio)
    model = None
    is_vertex_ai = False
    
    # Try Vertex AI first
    print(f"\n[1/5] Attempting Vertex AI initialization...")
    try:
        from langchain_google_vertexai import ChatVertexAI
        
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        
        if project:
            # Use Vertex AI via LangChain wrapper
            model = ChatVertexAI(
                model="gemini-2.5-flash",
                project=project,
                location=location,
                temperature=0.1,
            )
            is_vertex_ai = True
            print(f"[OK] Using Vertex AI (project={project}, location={location})")
        else:
            print(f"[SKIP] GOOGLE_CLOUD_PROJECT not set, trying AI Studio...")
    except ImportError:
        print(f"[SKIP] langchain-google-vertexai not installed, trying AI Studio...")
    except Exception as e:
        print(f"[SKIP] Vertex AI init failed ({e}), trying AI Studio...")
    
    # Fallback to AI Studio
    if model is None:
        try:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('models/gemini-2.5-flash')
                is_vertex_ai = False
                print("[OK] Using AI Studio API (fallback)")
            else:
                print("[FAIL] No GOOGLE_API_KEY found for AI Studio")
                return None
        except Exception as e:
            print(f"[FAIL] AI Studio init failed: {e}")
            return None
    
    if model is None:
        print("[FAIL] Could not initialize any LLM provider")
        return None
    
    # Convert PDF page to image
    print(f"\n[2/5] Converting PDF page {page_number} to image...")
    try:
        images = convert_from_path(
            pdf_path, 
            dpi=250, 
            first_page=page_number, 
            last_page=page_number
        )
        image = images[0]
        print(f"[OK] Image created: {image.size}")
        
        # Save image for reference
        image_path = Path(output_dir) / f"page_{page_number}.png"
        image.save(image_path)
        print(f"[OK] Saved to: {image_path}")
        
    except Exception as e:
        print(f"[FAIL] PDF conversion failed: {e}")
        return None
    
    # Model already initialized above
    print(f"\n[3/5] Model ready: gemini-2.5-flash")
    print(f"      Provider: {'Vertex AI' if is_vertex_ai else 'AI Studio'}")
    
    # Create extraction prompt
    prompt = """
Extract the text content from this page. Follow these rules:

1. Preserve the exact layout and formatting
2. Identify any headers, subheaders, or titles
3. Maintain paragraph breaks
4. Note any Sanskrit text (transliterated or in Devanagari)
5. Preserve verse numbers if present
6. Extract table data if present

Provide the extraction in the following JSON format:
{
    "page_type": "text|table|mixed|title_page",
    "title": "chapter or section title if present",
    "content": "full extracted text",
    "has_sanskrit": true/false,
    "verses": ["verse 1 text", "verse 2 text"] if applicable,
    "tables": [{"title": "", "data": []}] if applicable
}
"""
    
    # Extract content with Vision API
    print(f"\n[4/5] Extracting content with Vision API...")
    try:
        if is_vertex_ai:
            # Vertex AI (LangChain) - needs different invocation
            import base64
            from io import BytesIO
            
            # Convert PIL image to base64
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Invoke with text + image (LangChain pattern)
            from langchain_core.messages import HumanMessage
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            )
            response = model.invoke([message])
            extracted_text = response.content
            
        else:
            # AI Studio (genai) - direct invocation
            response = model.generate_content([prompt, image])
            extracted_text = response.text
        print(f"[OK] Extraction complete ({len(extracted_text)} characters)")
        
        # Save extracted text
        text_path = Path(output_dir) / f"page_{page_number}_extracted.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(extracted_text)
        print(f"[OK] Saved to: {text_path}")
        
    except Exception as e:
        print(f"[FAIL] Extraction failed: {e}")
        return None
    
    # Display preview
    print(f"\n[5/5] Extraction Preview:")
    print("-" * 70)
    preview = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
    print(preview)
    print("-" * 70)
    
    print(f"\n{'='*70}")
    print("EXTRACTION SUCCESSFUL!")
    print(f"{'='*70}")
    print(f"Output directory: {output_dir}")
    print(f"  - Image: page_{page_number}.png")
    print(f"  - Text: page_{page_number}_extracted.txt")
    
    return extracted_text


def batch_extract_with_rate_limit(
    pdf_path: str, 
    start_page: int, 
    end_page: int,
    delay_seconds: float = 4.5,
    output_dir: str = "./batch_output"
):
    """
    Extract multiple pages with rate limiting
    
    Args:
        pdf_path: Path to PDF
        start_page: Starting page number (1-indexed)
        end_page: Ending page number (inclusive)
        delay_seconds: Delay between requests (default 4.5s for 15 req/min limit)
        output_dir: Output directory
    """
    print("=" * 70)
    print("BATCH PDF EXTRACTION WITH RATE LIMITING")
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print(f"Pages: {start_page} to {end_page}")
    print(f"Rate limit: {delay_seconds}s between requests")
    print(f"Estimated time: {(end_page - start_page + 1) * delay_seconds / 60:.1f} minutes")
    print("=" * 70)
    
    results = []
    
    for page_num in range(start_page, end_page + 1):
        print(f"\n\nProcessing page {page_num}/{end_page}...")
        
        result = extract_pdf_page(pdf_path, page_num, output_dir)
        results.append({
            'page': page_num,
            'success': result is not None,
            'content': result
        })
        
        # Rate limiting delay
        if page_num < end_page:
            print(f"\n[Rate Limit] Waiting {delay_seconds}s before next request...")
            time.sleep(delay_seconds)
    
    # Summary
    successful = sum(1 for r in results if r['success'])
    print(f"\n\n{'='*70}")
    print("BATCH EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total pages: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    print(f"Output: {output_dir}")
    
    return results


if __name__ == "__main__":
    # Example usage
    print("PDF Extraction Test\n")
    print("Usage:")
    print("  python test_pdf_extraction.py")
    print("\nThis will prompt you for:")
    print("  1. PDF file path")
    print("  2. Page number to extract")
    print()
    
    pdf_path = input("Enter PDF path (or press Enter for demo): ").strip()
    
    if not pdf_path:
        print("\nDemo mode: Please provide a PDF path to test extraction")
        print("Example: D:\\docs\\astrology_book.pdf")
    else:
        if not os.path.exists(pdf_path):
            print(f"[ERROR] File not found: {pdf_path}")
        else:
            page_num = int(input("Enter page number to extract: "))
            extract_pdf_page(pdf_path, page_num)
