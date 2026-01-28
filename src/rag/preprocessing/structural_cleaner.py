#!/usr/bin/env python3
"""
Phase 2: Structural Cleaning

Deterministic, rule-based cleaning of extracted PDF content.
Removes artifacts, normalizes text, validates structure without losing semantic meaning.
"""

import re
import json
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter

# Handle both relative and direct imports
try:
    from .schemas import (
        ExtractedPage,
        CleanedPage,
        CleanedDocument,
        PageType,
    )
except ImportError:
    from schemas import (
        ExtractedPage,
        CleanedPage,
        CleanedDocument,
        PageType,
        PageType,
    )

# Try importing LLM Factory (Standardized absolute/relative fallback)
try:
    from src.llm.factory import LLMFactory
except ImportError:
    try:
        from ..llm.factory import LLMFactory
    except ImportError:
        LLMFactory = None

class StructuralCleaner:
    """
    Rule-based structural cleaning for extracted PDF content.
    Rule-based structural cleaning for extracted PDF content.
    Optionally supports LLM-based cleaning for higher quality.
    """
    
    CLEANING_PROMPT = """You are an expert editor for classical Sanskrit-English texts.
Your task is to CLEAN the following extracted text page from a PDF.

INPUT CONTENT:
{content}

INSTRUCTIONS:
1. Remove running headers/footers (e.g., page numbers like "108", "Chapter 7").
2. Merge broken lines (e.g., hyphenated words split across lines).
3. Fix sentence breaks where a sentence is split by a newline incorrectly.
4. Normalize Sanskrit diacritics if they look corrupted (e.g., " . <" garbage).
5. Do NOT rewrite, summarize, or change the meaning. Keep the exact wording otherwise.
6. If the page is empty or just garbage, return empty string.

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{{
  "clean_content": "The cleaned text string...",
  "changes_made": ["list", "of", "changes"]
}}
"""
    
    CLEANING_PROMPT = """You are an expert editor for classical Sanskrit-English texts.
Your task is to CLEAN the following extracted text page from a PDF.

INPUT CONTENT:
{content}

INSTRUCTIONS:
1. Remove running headers/footers (e.g., page numbers like "108", "Chapter 7").
2. Merge broken lines (e.g., hyphenated words split across lines).
3. Fix sentence breaks where a sentence is split by a newline incorrectly.
4. Normalize Sanskrit diacritics if they look corrupted (e.g., " . <" garbage).
5. Do NOT rewrite, summarize, or change the meaning. Keep the exact wording otherwise.
6. If the page is empty or just garbage, return empty string.

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{{
  "clean_content": "The cleaned text string...",
  "changes_made": ["list", "of", "changes"]
}}
"""
    
    # Common book headers/footers to detect
    COMMON_HEADER_PATTERNS = [
        r'^\s*\d+\s*$',  # Just page numbers
        r'^Page\s+\d+',  # "Page X"
        r'^\s*-\s*\d+\s*-\s*$',  # "- X -"
        r'^\s*\[\s*\d+\s*\]\s*$',  # "[X]"
    ]
    
    # Sanskrit danda normalization
    DANDA_PATTERNS = [
        (r'।।', '॥'),  # Double danda variant
        (r'\|\|', '॥'),  # ASCII double pipe to double danda
        (r'।\s*।', '॥'),  # Spaced dandas
    ]
    
    # Common OCR artifacts in Sanskrit
    SANSKRIT_OCR_FIXES = [
        (r'॥\s*(\d+)\s*॥', r'॥\1॥'),  # Normalize verse number spacing
        (r'(\d+)\s*।', r'\1॥'),  # Single danda after number to double
    ]
    
    
    
    def __init__(self, min_header_frequency: int = 2, use_llm: bool = False):
        """
        Initialize structural cleaner.
        
        Args:
            min_header_frequency: Minimum times a string must appear across pages
            use_llm: Whether to use LLM for cleaning (slower but better)
        """
        self.min_header_frequency = min_header_frequency
        self.use_llm = use_llm
        self.detected_headers: List[str] = []
        self.llm_client = None
        
        if use_llm and LLMFactory:
            try:
                # Initialize LLM using the factory with rate limiting
                self.llm_client = LLMFactory.create(
                    provider="google",
                    model="gemini-2.5-flash",
                    temperature=0.0,
                    use_rate_limiting=True,  # Enable built-in rate limiting
                    rate_limit_delay=1.5      # 1.5s minimum between requests
                )
                print("[âœ…] LLM Cleaning Enabled (gemini-2.5-flash with rate limiting)")
            except Exception as e:
                print(f"[WARN] Failed to initialize LLM for cleaning: {e}")
                self.use_llm = False
    
    def detect_global_headers(self, pages: List[ExtractedPage]) -> List[str]:
        """
        Detect strings that appear as headers/footers across multiple pages.
        
        Args:
            pages: List of extracted pages
            
        Returns:
            List of detected header/footer strings
        """
        # Collect potential headers from first/last lines of each page
        potential_headers: List[str] = []
        
        for page in pages:
            lines = page.content.strip().split('\n')
            if not lines:
                continue
            
            # First few and last few lines are potential headers/footers
            for line in lines[:3] + lines[-2:]:
                line = line.strip()
                if line and len(line) < 100:  # Headers are usually short
                    potential_headers.append(line)
        
        # Count frequencies
        header_counts = Counter(potential_headers)
        
        # Headers appear on multiple pages
        headers = [
            text for text, count in header_counts.items()
            if count >= self.min_header_frequency
        ]
        
        self.detected_headers = headers
        return headers
    
    def validate_title(
        self, 
        title: Optional[str], 
        content: str,
        global_headers: List[str]
    ) -> Tuple[Optional[str], bool]:
        """
        Validate if title is a real section header or a running header.
        
        Args:
            title: Extracted title from page
            content: Page content
            global_headers: Headers detected across document
            
        Returns:
            Tuple of (validated_title, was_header_flag)
        """
        if not title:
            return None, False
        
        title_clean = title.strip()
        
        # Check if title matches a global header
        if title_clean in global_headers:
            return None, True
        
        # Check if title is just a number (page number misidentified)
        if re.match(r'^\d+\s*$', title_clean):
            return None, True
        
        # Check if title ends with page number pattern (e.g., "Book Name 57")
        if re.match(r'.*\s+\d+\s*$', title_clean):
            # Might be "Book Name PageNum" format
            parts = title_clean.rsplit(' ', 1)
            if len(parts) == 2 and parts[1].isdigit():
                # Check if the text part is in headers
                if parts[0].strip() in global_headers:
                    return None, True
        
        return title_clean, False
    
    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace while preserving paragraph structure.
        
        Args:
            text: Raw text
            
        Returns:
            Normalized text
        """
        # Collapse multiple spaces to single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Collapse multiple blank lines to double newline (paragraph break)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def normalize_sanskrit(self, text: str) -> str:
        """
        Normalize Sanskrit/Devanagari text.
        
        Args:
            text: Text containing Devanagari
            
        Returns:
            Normalized text
        """
        # Unicode NFC normalization (canonical composition)
        text = unicodedata.normalize('NFC', text)
        
        # Apply danda normalizations
        for pattern, replacement in self.DANDA_PATTERNS:
            text = re.sub(pattern, replacement, text)
        
        # Apply OCR fixes
        for pattern, replacement in self.SANSKRIT_OCR_FIXES:
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def fix_hyphenation(self, text: str) -> str:
        """
        Fix words split by hyphens at line breaks.
        
        Args:
            text: Text with potential hyphenated line breaks
            
        Returns:
            Text with hyphenation fixed
        """
        # Pattern: word-\nword (hyphen at end of line followed by continuation)
        # Only join if both parts look like word fragments
        text = re.sub(
            r'([a-zA-Z]{2,})-\s*\n\s*([a-z]{2,})',
            r'\1\2',
            text
        )
        return text
    
    def fix_sentence_breaks(self, text: str) -> str:
        """
        Fix sentences broken across lines (not paragraphs).
        
        Args:
            text: Text with broken sentences
            
        Returns:
            Text with sentences rejoined
        """
        # If a line doesn't end with sentence-ending punctuation
        # and the next line starts with lowercase, join them
        lines = text.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this line should be joined with next
            if i < len(lines) - 1:
                current_stripped = line.rstrip()
                next_line = lines[i + 1].lstrip()
                
                # Join conditions:
                # 1. Current line doesn't end with terminal punctuation
                # 2. Next line starts with lowercase letter
                # 3. This isn't a paragraph break (blank line)
                if (
                    current_stripped and
                    not re.search(r'[.!?।॥:]\s*$', current_stripped) and
                    next_line and
                    next_line[0].islower()
                ):
                    # Join with space
                    result.append(current_stripped + ' ' + next_line)
                    i += 2
                    continue
            
            result.append(line)
            i += 1
        
        return '\n'.join(result)
    
    def remove_headers_footers(
        self, 
        text: str, 
        headers: List[str]
    ) -> Tuple[str, List[str]]:
        """
        Remove detected headers and footers from text.
        
        Args:
            text: Page text
            headers: List of header/footer strings to remove
            
        Returns:
            Tuple of (cleaned_text, removed_items)
        """
        removed = []
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check against known headers
            if line_stripped in headers:
                removed.append(line_stripped)
                continue
            
            # Check against common patterns
            is_header = False
            for pattern in self.COMMON_HEADER_PATTERNS:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    removed.append(line_stripped)
                    is_header = True
                    break
            
            if not is_header:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines), removed
    
    def validate_verse_numbers(
        self, 
        content: str, 
        verse_numbers: List[str]
    ) -> List[str]:
        """
        Validate and extract verse numbers from content.
        
        Args:
            content: Page content
            verse_numbers: Extracted verse numbers from Vision LLM
            
        Returns:
            Validated list of verse numbers
        """
        # Extract verse numbers from double danda patterns
        # Pattern: ॥ followed by number(s) followed by ॥
        pattern = r'॥\s*(\d+(?:\s*[-–]\s*\d+)?)\s*॥'
        found_in_content = re.findall(pattern, content)
        
        # Also check for Devanagari numerals
        devanagari_pattern = r'॥\s*([०-९]+(?:\s*[-–]\s*[०-९]+)?)\s*॥'
        devanagari_found = re.findall(devanagari_pattern, content)
        
        # Combine and deduplicate
        all_found = list(set(found_in_content + devanagari_found))
        
        # If Vision LLM found verses, use those but validate
        if verse_numbers:
            # Keep verse numbers that appear in content
            validated = []
            for vn in verse_numbers:
                vn_clean = vn.strip()
                if vn_clean in content or any(vn_clean in f for f in all_found):
                    validated.append(vn_clean)
            return validated if validated else all_found
        
        return all_found
    
    def normalize_quotes(self, text: str) -> str:
        """Normalize various quote styles to standard quotes."""
        # Curly quotes to straight
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        return text
    
    def clean_page(
        self, 
        page: ExtractedPage,
        global_headers: Optional[List[str]] = None
    ) -> CleanedPage:
        """
        Apply all cleaning operations to a single page.
        
        Args:
            page: Extracted page data
            global_headers: Headers detected across document
            
        Returns:
            Cleaned page data
        """
        if global_headers is None:
            global_headers = self.detected_headers
        
        cleaning_applied = []
        content = page.content
        original_content = content
        
        # 1. Remove headers/footers
        content, removed_headers = self.remove_headers_footers(content, global_headers)
        if removed_headers:
            cleaning_applied.append("header_footer_removal")
        
        # 2. Normalize whitespace
        content = self.normalize_whitespace(content)
        cleaning_applied.append("whitespace_normalization")
        
        # 3. Fix hyphenation
        content_before = content
        content = self.fix_hyphenation(content)
        if content != content_before:
            cleaning_applied.append("hyphenation_fix")
        
        # 4. Fix sentence breaks
        content_before = content
        content = self.fix_sentence_breaks(content)
        if content != content_before:
            cleaning_applied.append("sentence_break_fix")
        
        # 5. Sanskrit normalization
        if page.has_sanskrit:
            content = self.normalize_sanskrit(content)
            cleaning_applied.append("sanskrit_normalization")
        
        # 6. Quote normalization
        content = self.normalize_quotes(content)
        cleaning_applied.append("quote_normalization")
        
        # 7. Validate title
        validated_title, was_header = self.validate_title(
            page.title, content, global_headers
        )
        if was_header:
            cleaning_applied.append("title_header_detection")
        
        # 8. Validate verse numbers
        validated_verses = self.validate_verse_numbers(
            content, page.verse_numbers
        )
        
        # Clean verses too
        cleaned_verses = []
        for verse in page.verses:
            cleaned_verse = self.normalize_whitespace(verse)
            if page.has_sanskrit:
                cleaned_verse = self.normalize_sanskrit(cleaned_verse)
            cleaned_verses.append(cleaned_verse)
        
        return CleanedPage(
            page_number=page.page_number,
            page_type=page.page_type,
            title=validated_title,
            content=content,
            original_content=original_content,
            has_sanskrit=page.has_sanskrit,
            verses=cleaned_verses,
            verse_numbers=validated_verses,
            tables=page.tables,
            cleaning_applied=cleaning_applied,
            detected_headers=removed_headers,
            title_was_header=was_header,
        )

    def clean_page_llm(self, page: ExtractedPage) -> CleanedPage:
        """
        Clean page using LLM (slower but higher quality).
        """
        if not self.llm_client:
            print("[WARN] LLM client not initialized, falling back to regex")
            return self.clean_page(page)
            
        original_content = page.content
        if not original_content.strip():
            return self.clean_page(page) # fast track empty pages
            
        try:
            prompt = self.CLEANING_PROMPT.format(content=original_content[:30000]) # Safety limit
            # Use LangChain invoke
            response = self.llm_client.invoke(prompt)
            # Handle response content safely
            text = response.content if hasattr(response, 'content') else str(response)
            text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            clean_content = result.get("clean_content", "")
            changes = result.get("changes_made", [])
            
            # Fallback if LLM failed to produce content
            if not clean_content and original_content:
                clean_content = original_content
                
            return CleanedPage(
                page_number=page.page_number,
                page_type=page.page_type,
                title=page.title, 
                content=clean_content,
                original_content=original_content,
                has_sanskrit=page.has_sanskrit,
                verses=page.verses, # Keep original verse extraction for now
                verse_numbers=page.verse_numbers,
                tables=page.tables,
                cleaning_applied=["llm_cleaning"] + changes,
                detected_headers=[],
                title_was_header=False,
            )
            
        except Exception as e:
            print(f"[ERROR] LLM Cleaning failed for page {page.page_number}: {e}")
            return self.clean_page(page) # Fallback to regex    
    def clean_document(
        self, 
        pages: List[ExtractedPage],
        source_file: Optional[str] = None
    ) -> CleanedDocument:
        """
        Clean all pages in a document.
        
        Args:
            pages: List of extracted pages
            source_file: Optional source file path
            
        Returns:
            Cleaned document with all pages
        """
        # First pass: detect global headers
        global_headers = self.detect_global_headers(pages)
        
        # Second pass: clean each page
        # Second pass: clean each page
        if self.use_llm:
            print(f"[INFO] Cleaning {len(pages)} pages using LLM...")
            cleaned_pages = []
            for page in pages:
                print(f"  > Cleaning Page {page.page_number}...")
                cleaned_pages.append(self.clean_page_llm(page))
        else:
            cleaned_pages = [
                self.clean_page(page, global_headers)
                for page in pages
            ]
        
        return CleanedDocument(
            pages=cleaned_pages,
            source_file=source_file,
            global_headers=global_headers,
        )
    
    def process_file(
        self, 
        input_file: str, 
        output_file: Optional[str] = None
    ) -> CleanedDocument:
        """
        Process an extracted JSON file.
        
        Args:
            input_file: Path to extracted JSON file
            output_file: Optional output path (auto-generated if None)
            
        Returns:
            Cleaned document
        """
        input_path = Path(input_file)
        
        # Load extracted data
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to ExtractedPage objects
        if isinstance(data, list):
            pages = [ExtractedPage(**page) for page in data]
        else:
            pages = [ExtractedPage(**data)]
        
        # Clean
        cleaned_doc = self.clean_document(pages, source_file=str(input_path))
        
        # Save output
        if output_file is None:
            output_file = str(input_path.parent / f"{input_path.stem}_cleaned.json")
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                cleaned_doc.model_dump(), 
                f, 
                ensure_ascii=False, 
                indent=2
            )
        
        print(f"[OK] Cleaned {len(cleaned_doc.pages)} pages")
        print(f"[OK] Detected {len(cleaned_doc.global_headers)} global headers")
        print(f"[OK] Saved to: {output_path}")
        
        return cleaned_doc


def test_with_sample():
    """Test structural cleaner with sample extracted data."""
    sample_file = Path(__file__).parent.parent.parent.parent / "extracted" / "extracted_1-3_20260122_164926.json"
    
    if not sample_file.exists():
        print(f"Sample file not found: {sample_file}")
        return
    
    cleaner = StructuralCleaner()
    result = cleaner.process_file(str(sample_file))
    
    print("\n" + "="*70)
    print("CLEANING RESULTS")
    print("="*70)
    
    for page in result.pages:
        print(f"\nPage {page.page_number}:")
        print(f"  Title: {page.title}")
        print(f"  Title was header: {page.title_was_header}")
        print(f"  Cleaning applied: {page.cleaning_applied}")
        print(f"  Verses found: {page.verse_numbers}")
        print(f"  Content preview: {page.content[:200]}...")


if __name__ == "__main__":
    test_with_sample()
