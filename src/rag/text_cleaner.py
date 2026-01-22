#!/usr/bin/env python3
"""
Text Cleaning Pipeline for Extracted PDF Content
Prepares raw extracted text for chunking and vector DB ingestion
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import google.generativeai as genai


class TextCleaner:
    """
    Intelligent text cleaning for astrology PDF extractions
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize text cleaner
        
        Args:
            use_llm: Whether to use LLM for context-aware cleaning
        """
        self.use_llm = use_llm
        
        if use_llm:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('models/gemini-flash-lite-latest')
            else:
                print("[WARN] GOOGLE_API_KEY not set, falling back to rule-based cleaning")
                self.use_llm = False
    
    def rule_based_clean(self, text: str) -> str:
        """
        Rule-based text cleaning (fast, no API calls)
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # 1. Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # 2. Fix hyphenated words split across lines
        text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)
        
        # 3. Remove page numbers (common patterns)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'Page \d+', '', text, flags=re.IGNORECASE)
        
        # 4. Remove common headers/footers patterns
        text = re.sub(r'^(Chapter|Section)\s+\d+\s*$', '', text, flags=re.MULTILINE)
        
        # 5. Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # 6. Fix multiple periods
        text = re.sub(r'\.{3,}', '...', text)
        
        # 7. Remove trailing/leading whitespace
        text = text.strip()
        
        # 8. Collapse multiple newlines to single newline
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text
    
    def llm_clean(self, text: str, preserve_sanskrit: bool = True) -> str:
        """
        LLM-based context-aware cleaning (slower, higher quality)
        
        Args:
            text: Raw extracted text
            preserve_sanskrit: Whether to preserve Sanskrit text formatting
            
        Returns:
            Cleaned text
        """
        if not self.use_llm:
            return self.rule_based_clean(text)
        
        prompt = f"""
You are a text cleaning specialist for astrology documents. Clean the following extracted text:

RULES:
1. **Remove artifacts**: Page numbers, headers, footers, running titles
2. **Fix line breaks**: Join sentences broken across lines (but keep paragraph breaks)
3. **Handle page transitions**: Remove page break markers and redundant headers
4. **Preserve structure**: Keep verse numbers, section headings, chapter titles
5. {f"**Preserve Sanskrit**: Keep transliterated Sanskrit and Devanagari text intact" if preserve_sanskrit else "**Sanskrit**: Standardize formatting"}
6. **Fix hyphenation**: Join words split by hyphens at line breaks
7. **Normalize whitespace**: Remove excessive spaces but keep logical paragraph breaks
8. **Keep tables**: If table data exists, preserve its structure
9. **Preserve lists**: Keep bullet points and numbered lists
10. **Remove duplicates**: Remove repeated headers/footers from page transitions

OUTPUT FORMAT:
Return ONLY the cleaned text. Do not add explanations or comments.

TEXT TO CLEAN:
{text}
"""
        
        try:
            response = self.model.generate_content(prompt)
            cleaned = response.text.strip()
            return cleaned
        except Exception as e:
            print(f"[WARN] LLM cleaning failed: {e}, falling back to rule-based")
            return self.rule_based_clean(text)
    
    def clean_extraction(
        self, 
        extraction_data: Dict,
        method: str = "hybrid"
    ) -> Dict:
        """
        Clean extracted content from PDF extraction
        
        Args:
            extraction_data: Dict from test_pdf_extraction.py output
            method: "rule", "llm", or "hybrid" (rule first, then LLM for complex cases)
            
        Returns:
            Cleaned extraction data
        """
        content = extraction_data.get("content", "")
        
        if method == "rule":
            cleaned_content = self.rule_based_clean(content)
        elif method == "llm":
            cleaned_content = self.llm_clean(content)
        else:  # hybrid
            # Rule-based first
            cleaned_content = self.rule_based_clean(content)
            # LLM for refinement if needed
        if self.use_llm and len(cleaned_content) > 100:
                cleaned_content = self.llm_clean(cleaned_content)
        
        # Create cleaned version
        cleaned_data = extraction_data.copy()
        cleaned_data["content"] = cleaned_content
        cleaned_data["cleaned_method"] = method
        
        return cleaned_data
    
    def process_file(
        self, 
        input_file: str, 
        output_file: Optional[str] = None,
        method: str = "hybrid"
    ) -> Dict:
        """
        Process extracted text file
        
        Args:
            input_file: Path to extracted text (JSON or TXT)
            output_file: Path to save cleaned text (auto-generated if None)
            method: Cleaning method ("rule", "llm", "hybrid")
            
        Returns:
            Cleaned data dict
        """
        print(f"Processing: {input_file}")
        print(f"Method: {method}")
        
        # Read input
        input_path = Path(input_file)
        if input_path.suffix == '.json':
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = {"content": f.read()}
        
        # Clean
        cleaned_data = self.clean_extraction(data, method=method)
        
        # Save output
        if output_file is None:
            output_file = str(input_path.parent / f"{input_path.stem}_cleaned{input_path.suffix}")
        
        output_path = Path(output_file)
        if output_path.suffix == '.json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_data["content"])
        
        print(f"✓ Saved cleaned text to: {output_path}")
        
        return cleaned_data


def batch_clean_directory(
    input_dir: str,
    output_dir: Optional[str] = None,
    method: str = "hybrid",
    pattern: str = "*_extracted.txt"
):
    """
    Batch clean all extracted files in a directory
    
    Args:
        input_dir: Directory containing extracted text files
        output_dir: Output directory (creates _cleaned suffix if None)
        method: Cleaning method
        pattern: Glob pattern for files to process
    """
    input_path = Path(input_dir)
    
    if output_dir is None:
        output_path = input_path.parent / f"{input_path.name}_cleaned"
    else:
        output_path = Path(output_dir)
    
    output_path.mkdir(exist_ok=True, parents=True)
    
    cleaner = TextCleaner(use_llm=(method in ["llm", "hybrid"]))
    
    files = list(input_path.glob(pattern))
    print(f"\nFound {len(files)} files to process")
    print(f"Output directory: {output_path}")
    print("=" * 70)
    
    for i, file in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {file.name}")
        
        output_file = output_path / f"{file.stem}_cleaned{file.suffix}"
        cleaner.process_file(str(file), str(output_file), method=method)
    
    print("\n" + "=" * 70)
    print(f"✓ Processed {len(files)} files")
    print(f"✓ Output: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean extracted PDF text")
    parser.add_argument("input", help="Input file or directory")
    parser.add_argument("-o", "--output", help="Output file or directory")
    parser.add_argument(
        "-m", "--method", 
        choices=["rule", "llm", "hybrid"],
        default="hybrid",
        help="Cleaning method (default: hybrid)"
    )
    parser.add_argument(
        "-b", "--batch",
        action="store_true",
        help="Batch process directory"
    )
    parser.add_argument(
        "-p", "--pattern",
        default="*_extracted.txt",
        help="File pattern for batch mode (default: *_extracted.txt)"
    )
    
    args = parser.parse_args()
    
    if args.batch:
        batch_clean_directory(
            args.input,
            args.output,
            args.method,
            args.pattern
        )
    else:
        cleaner = TextCleaner(use_llm=(args.method in ["llm", "hybrid"]))
        cleaner.process_file(args.input, args.output, args.method)
