#!/usr/bin/env python3
"""
Production PDF Extraction Tool
Extract text from PDFs using Gemini Vision with rate limiting
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

project_root = Path(__file__).parent  # Script is in same dir as .env
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import google.generativeai as genai
from pdf2image import convert_from_path


class PDFExtractor:
    """PDF extraction using Gemini Vision"""
    
    def __init__(self, output_dir: str = "./extracted"):
        """Initialize extractor"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Configure Gemini
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in .env file")
        
        genai.configure(api_key=api_key)
        # Using flash-lite for cost-effective extraction
        # If quality is poor, can manually retry with gemini-2.5-pro
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        
        self.extraction_prompt = """
You are an expert OCR system specializing in extracting text from astrology books that contain both English and Sanskrit (Devanagari script).

CRITICAL INSTRUCTIONS FOR SANSKRIT TEXT:

1. **Devanagari Lines**: Sanskrit verses in Devanagari script are written LEFT-TO-RIGHT, just like English
   - DO NOT skip to the next line mid-word
   - Read each Devanagari line COMPLETELY from left to right before moving to the next line
   - Preserve the exact line breaks as they appear in the image

2. **Verse Structure**: 
   - Sanskrit verses are often formatted in 2-4 lines per verse
   - Each line should be kept intact - do NOT break lines unless there's a line break in the image
   - Verse numbers like ॥१६॥, ॥१७॥ should be preserved at the end of verses

3. **Mixed Text Handling**:
   - English descriptions come first
   - Sanskrit verses are centered/indented below the English
   - Keep them separate and clearly marked

4. **Character Accuracy**:
   - Copy every Devanagari character exactly as seen
   - Preserve all diacritical marks (mātrās)
   - Don't skip or merge characters

EXTRACTION FORMAT:

Provide the extraction in this JSON format:
{
    "page_number": <page number if visible, else null>,
    "page_type": "text|table|mixed|title_page",
    "title": "chapter or section title if present",
    "content": "full extracted text with proper formatting",
    "has_sanskrit": true/false,
    "verses": [
        "complete verse 1 with all lines intact",
        "complete verse 2 with all lines intact"
    ],
    "verse_numbers": ["13-14", "15-16"],
    "tables": [{"title": "", "data": []}] if applicable
}

EXAMPLE OF PROPER SANSKRIT EXTRACTION:

If you see:
```
शीर्षोदयी    सुवीर्याऽह्यस्तुलः    कृष्णो रजोगुणी ।
पश्चिमो भूचरो धाती शुद्रो मध्यनदीर्द्रपात ॥१६॥
```

Extract EXACTLY as shown above (two complete lines), NOT broken into fragments.

Now extract all text from this page following these rules precisely.
"""
    
    def extract_page(self, pdf_path: str, page_num: int) -> Optional[Dict]:
        """
        Extract a single page
        
        Args:
            pdf_path: Path to PDF
            page_num: Page number (1-indexed)
            
        Returns:
            Extraction data dict or None if failed
        """
        try:
            # Convert PDF page to image
            print(f"  → Converting page {page_num} to image...")
            images = convert_from_path(
                pdf_path, 
                dpi=250, 
                first_page=page_num, 
                last_page=page_num
            )
            image = images[0]
            print(f"  → Image size: {image.size}")
            
            # Extract with Vision API
            print(f"  → Calling Gemini Vision API...")
            response = self.model.generate_content([self.extraction_prompt, image])
            extracted_text = response.text.strip()
            
            print(f"  → Received {len(extracted_text)} characters")
            
            # Parse JSON if possible
            try:
                # Remove markdown code blocks if present
                if extracted_text.startswith("```"):
                    print(f"  → Removing markdown code blocks...")
                    lines = extracted_text.split("\n")
                    extracted_text = "\n".join(lines[1:-1])
                
                data = json.loads(extracted_text)
                data['page_number'] = page_num
                print(f"  ✓ JSON parsed successfully")
                return data
            except json.JSONDecodeError as e:
                print(f"  → JSON parse failed, wrapping as text")
                print(f"  → First 200 chars: {extracted_text[:200]}")
                # If not JSON, wrap in basic structure
                return {
                    'page_number': page_num,
                    'page_type': 'text',
                    'content': extracted_text,
                    'title': None,
                    'raw_response': extracted_text
                }
                
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def extract_single_page(
        self, 
        pdf_path: str, 
        page_num: int,
        save_image: bool = True
    ) -> Optional[Dict]:
        """
        Extract and save single page
        
        Args:
            pdf_path: Path to PDF
            page_num: Page number
            save_image: Whether to save the page image
            
        Returns:
            Extraction data
        """
        print(f"\n{'='*70}")
        print(f"EXTRACTING PAGE {page_num}")
        print(f"{'='*70}")
        
        # Optionally save image
        if save_image:
            print(f"[1/2] Converting page to image...")
            images = convert_from_path(pdf_path, dpi=250, first_page=page_num, last_page=page_num)
            image_path = self.output_dir / f"page_{page_num}.png"
            images[0].save(image_path)
            print(f"  ✓ Saved: {image_path}")
        
        # Extract
        print(f"[2/2] Extracting content...")
        data = self.extract_page(pdf_path, page_num)
        
        if data:
            # Save extraction
            json_path = self.output_dir / f"page_{page_num}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            txt_path = self.output_dir / f"page_{page_num}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(data.get('content', ''))
            
            print(f"  ✓ Saved: {json_path}")
            print(f"  ✓ Saved: {txt_path}")
            print(f"\n{'='*70}")
            print("✅ EXTRACTION COMPLETE")
            print(f"{'='*70}")
            
        return data
    
    def extract_multiple_pages(
        self,
        pdf_path: str,
        start_page: int,
        end_page: int,
        combined_file: bool = True,
        delay_seconds: float = 4.5,
        save_images: bool = False
    ) -> List[Dict]:
        """
        Extract multiple pages
        
        Args:
            pdf_path: Path to PDF
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive)
            combined_file: Save all pages to one file
            delay_seconds: Delay between API calls
            save_images: Save page images
            
        Returns:
            List of extraction data dicts
        """
        total_pages = end_page - start_page + 1
        
        print(f"\n{'='*70}")
        print(f"BATCH EXTRACTION: Pages {start_page}-{end_page}")
        print(f"{'='*70}")
        print(f"Total pages: {total_pages}")
        print(f"Rate limit delay: {delay_seconds}s")
        print(f"Estimated time: {total_pages * delay_seconds / 60:.1f} minutes")
        print(f"Combined file: {'Yes' if combined_file else 'No'}")
        print(f"{'='*70}\n")
        
        results = []
        
        for page_num in range(start_page, end_page + 1):
            print(f"[{page_num - start_page + 1}/{total_pages}] Processing page {page_num}...")
            
            data = self.extract_page(pdf_path, page_num)
            
            if data:
                results.append(data)
                print(f"  ✓ Extracted ({len(data.get('content', ''))} chars)")
                
                # Save individual files if not combined
                if not combined_file:
                    json_path = self.output_dir / f"page_{page_num}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                print(f"  ✗ Failed")
            
            # Rate limiting
            if page_num < end_page:
                print(f"  ⏱  Waiting {delay_seconds}s...")
                time.sleep(delay_seconds)
        
        # Save combined file
        if combined_file and results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Combined JSON
            combined_json = self.output_dir / f"extracted_{start_page}-{end_page}_{timestamp}.json"
            with open(combined_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            # Combined text (all pages concatenated)
            combined_txt = self.output_dir / f"extracted_{start_page}-{end_page}_{timestamp}.txt"
            with open(combined_txt, 'w', encoding='utf-8') as f:
                for data in results:
                    f.write(f"\n{'='*70}\n")
                    f.write(f"PAGE {data.get('page_number', '?')}\n")
                    if data.get('title'):
                        f.write(f"TITLE: {data['title']}\n")
                    f.write(f"{'='*70}\n\n")
                    f.write(data.get('content', ''))
                    f.write("\n\n")
            
            print(f"\n{'='*70}")
            print("✅ BATCH EXTRACTION COMPLETE")
            print(f"{'='*70}")
            print(f"Pages extracted: {len(results)}/{total_pages}")
            print(f"Combined JSON: {combined_json}")
            print(f"Combined Text: {combined_txt}")
            print(f"{'='*70}")
        
        return results


def main():
    """Interactive extraction interface"""
    print("\n")
    print("="*70)
    print("  PDF EXTRACTION TOOL - Gemini Vision")
    print("="*70)
    print()
    
    # Get PDF path
    pdf_path = input("Enter PDF file path: ").strip().strip('"')
    
    if not os.path.exists(pdf_path):
        print(f"\n❌ File not found: {pdf_path}")
        return
    
    print(f"✓ PDF found: {pdf_path}\n")
    
    # Choose mode
    print("Select extraction mode:")
    print("  1. Single page")
    print("  2. Multiple pages (range)")
    print()
    
    mode = input("Choice (1 or 2): ").strip()
    
    # Output directory
    output_dir = input("\nOutput directory [./extracted]: ").strip() or "./extracted"
    
    extractor = PDFExtractor(output_dir)
    
    if mode == "1":
        # Single page
        page_num = int(input("\nPage number to extract: "))
        save_image = input("Save page image? (y/n) [y]: ").strip().lower() != 'n'
        
        extractor.extract_single_page(pdf_path, page_num, save_image=save_image)
        
    elif mode == "2":
        # Multiple pages
        start_page = int(input("\nStart page: "))
        end_page = int(input("End page: "))
        
        combined = input("Save to combined file? (y/n) [y]: ").strip().lower() != 'n'
        
        # Delay
        print(f"\nRate limit: 15 requests/min (AI Studio free tier)")
        delay = input("Delay between requests in seconds [4.5]: ").strip()
        delay = float(delay) if delay else 4.5
        
        extractor.extract_multiple_pages(
            pdf_path,
            start_page,
            end_page,
            combined_file=combined,
            delay_seconds=delay,
            save_images=False
        )
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Extraction cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
