# src/rag/preprocessing/page_analyzer.py
# src\rag\preprocessing\page_analyzer.py
#!/usr/bin/env python3
"""
Phase 3: Cross-Page Analysis & Relationship Inference

LLM-assisted analysis to detect cross-page continuations and semantic relationships.
"""

import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import os

# Handle both relative and direct imports
try:
    from .schemas import (
        CleanedPage,
        CleanedDocument,
        LinkedPage,
        LinkedDocument,
        PageType,
    )
except ImportError:
    from schemas import (
        CleanedPage,
        CleanedDocument,
        LinkedPage,
        LinkedDocument,
        PageType,
    )

try:
    from src.llm.factory import create_llm
except ImportError:
    try:
        from ...llm.factory import create_llm
    except ImportError:
        create_llm = None

class PageAnalyzer:
    """
    Analyze pages for cross-page relationships and semantic metadata.
    Uses LLM for complex analysis, rule-based for simple patterns.
    """
    
    # Sentence-ending punctuation (English and Sanskrit)
    SENTENCE_ENDINGS = r'[.!?।॥]'
    
    # Chapter/section header patterns
    CHAPTER_PATTERNS = [
        r'^Chapter\s+\d+[:\s]',
        r'^Section\s+\d+[:\s]',
        r'^अध्याय\s*\d+',  # Sanskrit chapter
    ]
    
    
    def __init__(self, use_llm: bool = True, model_name: str = "gemini-2.5-flash"):
        """
        Initialize page analyzer.
        
        Args:
            use_llm: Whether to use LLM for complex analysis
            model_name: Model to use (default: gemini-2.5-flash-lite)
        """
        self.use_llm = use_llm
        self.model = None
        self.is_vertex_ai = False
        self.embedding_model = None
        
        # Initialize Vertex AI Embedder for semantic continuity
        try:
            from src.rag.preprocessing.embedder import Embedder
            self.embedding_model = Embedder()
            print("[[DONE]] Vertex AI Embedder initialized for semantic continuity")
        except ImportError:
            print("[WARN] Embedder not found. Semantic checks will be skipped.")
        except Exception as e:
            print(f"[WARN] Failed to load Embedder: {e}")

        if use_llm:
            try:
                # Create LLM using factory with rate limiting
                self.model = create_llm(
                    provider="google",
                    model=model_name,
                    temperature=0.0,
                    use_rate_limiting=True,
                    rate_limit_delay=5.0
                )
                
                # Determine which provider was used
                from langchain_google_vertexai import ChatVertexAI
                self.is_vertex_ai = isinstance(self.model, ChatVertexAI)
                
                provider_name = "Vertex AI" if self.is_vertex_ai else "AI Studio"
                print(f"[[DONE]] Using {provider_name} via LLMFactory with rate limiting")
                
            except Exception as e:
                print(f"[WARN] LLM initialization failed: {e}")
                print("[INFO] Using rule-based analysis only")
                self.use_llm = False
    
    def detect_sentence_boundaries(self, content: str) -> Tuple[bool, bool]:
        """
        Detect if content starts/ends mid-sentence.
        
        Args:
            content: Page content
            
        Returns:
            Tuple of (starts_mid_sentence, ends_mid_sentence)
        """
        lines = content.strip().split('\n')
        if not lines:
            return False, False
        
        # Check first meaningful line
        first_line = ''
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.isdigit():
                first_line = stripped
                break
        
        # Starts mid-sentence if first char is lowercase
        starts_mid = bool(first_line and first_line[0].islower())
        
        # Check last meaningful line
        last_line = ''
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and not stripped.isdigit():
                last_line = stripped
                break
        
        # Ends mid-sentence if no terminal punctuation
        ends_mid = bool(last_line and not re.search(self.SENTENCE_ENDINGS + r'\s*$', last_line))
        
        return starts_mid, ends_mid
    
    def detect_chapter_section(self, content: str, title: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect chapter and section from content.
        
        Args:
            content: Page content
            title: Page title if any
            
        Returns:
            Tuple of (chapter, section)
        """
        chapter = None
        section = None
        
        # Look for chapter pattern in content
        for pattern in self.CHAPTER_PATTERNS:
            match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
            if match:
                # Extract chapter title (rest of the line)
                line_start = match.start()
                line_end = content.find('\n', line_start)
                if line_end == -1:
                    line_end = len(content)
                chapter = content[line_start:line_end].strip()
                break
        
        # Section could be a sub-heading (numbered like "1. Introduction")
        section_match = re.search(r'^\d+\.\s+([A-Z][^.\n]+)', content, re.MULTILINE)
        if section_match:
            section = section_match.group(0).strip()
        
        return chapter, section
    
    def extract_main_topic(self, content: str) -> Optional[str]:
        """
        Extract the main astrological topic from content.
        Rule-based extraction of key entities.
        
        Args:
            content: Page content
            
        Returns:
            Main topic string or None
        """
        # Common astrological entities to detect
        planets = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 
                   'Rahu', 'Ketu', 'Gulika', 'Mandi']
        houses = [f'{i}th House' for i in range(1, 13)] + \
                 [f'{i}st House' for i in [1]] + \
                 [f'{i}nd House' for i in [2]] + \
                 [f'{i}rd House' for i in [3]] + \
                 ['Lagna', 'Ascendant']
        signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
                 'Mesha', 'Vrishabha', 'Mithuna', 'Karka', 'Simha', 'Kanya',
                 'Tula', 'Vrischika', 'Dhanu', 'Makara', 'Kumbha', 'Meena']
        
        found_planets = [p for p in planets if p.lower() in content.lower()]
        found_houses = [h for h in houses if h.lower() in content.lower()]
        found_signs = [s for s in signs if s.lower() in content.lower()]
        
        parts = []
        if found_planets:
            parts.append(found_planets[0])
        if found_houses:
            parts.append(f"in {found_houses[0]}" if found_planets else found_houses[0])
        if found_signs and not found_houses:
            parts.append(f"in {found_signs[0]}" if found_planets else found_signs[0])
        
        return ' '.join(parts) if parts else None
    
    def calculate_semantic_continuity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between end of text1 and start of text2.
        """
        if not self.embedding_model:
            return 0.5 # Neutral if no model
            
        try:
            import numpy as np
            
            # Take last 300 chars of page 1 and first 300 of page 2
            t1_end = text1[-300:] if len(text1) > 300 else text1
            t2_start = text2[:300] if len(text2) > 300 else text2
            
            embeddings = self.embedding_model.embed_texts([t1_end, t2_start])
            
            emb1 = np.array(embeddings[0])
            emb2 = np.array(embeddings[1])
            
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.5
                
            sim = np.dot(emb1, emb2) / (norm1 * norm2)
            return float(sim)
        except Exception as e:
            print(f"[WARN] Semantic check failed: {e}")
            return 0.5

    def analyze_continuation_rule_based(
        self, 
        page1: CleanedPage, 
        page2: CleanedPage
    ) -> Tuple[bool, float]:
        """
        Rule-based continuation detection with Semantic Augmentation.
        """
        confidence = 0.0
        
        # 1. Grammar: Check sentence boundaries (Strong signal)
        _, ends_mid = self.detect_sentence_boundaries(page1.content)
        starts_mid, _ = self.detect_sentence_boundaries(page2.content)
        
        if ends_mid:
            confidence += 0.4
        if starts_mid:
            confidence += 0.2 # Boosting this slightly less than trailing sentence
        
        # 2. Semantic: Check meaning continuity (New!)
        semantic_score = self.calculate_semantic_continuity(page1.content, page2.content)
        if semantic_score > 0.6:
            confidence += 0.3
        elif semantic_score < 0.3:
            confidence -= 0.2 # Likely topic shift
            
        # 3. Topic: Keyword matching (Simple fallback)
        topic1 = self.extract_main_topic(page1.content)
        topic2 = self.extract_main_topic(page2.content)
        if topic1 and topic2 and topic1 == topic2:
            confidence += 0.1
        
        # 4. Verse continuity
        if page1.verse_numbers and page2.verse_numbers:
            try:
                last_verse = int(page1.verse_numbers[-1].split('-')[-1])
                first_verse = int(page2.verse_numbers[0].split('-')[0])
                if first_verse == last_verse + 1:
                    confidence += 0.3
            except ValueError:
                pass
        
        # 5. Chapter boundaries (Strong Negative)
        chapter2, _ = self.detect_chapter_section(page2.content, page2.title)
        if chapter2:
            confidence = max(0, confidence - 0.5)
        
        # Ensure confidence is clamped to valid range [0.0, 1.0]
        confidence = max(0.0, min(confidence, 1.0))
        
        return confidence >= 0.5, confidence
    
    def analyze_continuation_llm(
        self,
        page1: CleanedPage,
        page2: CleanedPage
    ) -> Dict:
        """
        LLM-based continuation analysis.
        
        Args:
            page1: First page
            page2: Second page
            
        Returns:
            Analysis dict with continuation info
        """
        if not self.model:
            # Fallback to rule-based
            continues, confidence = self.analyze_continuation_rule_based(page1, page2)
            return {
                "continues": continues,
                "confidence": confidence,
                "chapter": None,
                "section": None,
                "main_topic": self.extract_main_topic(page2.content),
            }
        
        # Prepare content snippets (last 500 chars of page1, first 500 of page2)
        page1_end = page1.content[-500:] if len(page1.content) > 500 else page1.content
        page2_start = page2.content[:500] if len(page2.content) > 500 else page2.content
        
        prompt = f"""Analyze these two consecutive pages from an astrology text for continuity.

PAGE {page1.page_number} (end):
{page1_end}

PAGE {page2.page_number} (start):
{page2_start}

Answer these questions in JSON format:
{{
  "continues_from_previous": true/false (does page {page2.page_number} continue the discussion from page {page1.page_number}?),
  "confidence": 0.0-1.0 (how confident are you?),
  "chapter": "chapter name if identifiable, else null",
  "section": "section name if identifiable, else null",
  "main_topic": "main astrological topic discussed (e.g., 'Gulika in 5th House')",
  "starts_mid_sentence": true/false,
  "ends_mid_sentence": true/false
}}

Return ONLY the JSON, no explanation."""

        try:
            # Use LangChain invoke
            response = self.model.invoke(prompt)
            # Handle response content safely
            text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            if text.startswith('```'):
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            
            result = json.loads(text)
            return {
                "continues": result.get("continues_from_previous", False),
                "confidence": result.get("confidence", 0.5),
                "chapter": result.get("chapter"),
                "section": result.get("section"),
                "main_topic": result.get("main_topic"),
                "starts_mid_sentence": result.get("starts_mid_sentence", False),
                "ends_mid_sentence": result.get("ends_mid_sentence", False),
            }
        except Exception as e:
            print(f"[WARN] LLM analysis failed: {e}, using rule-based")
            continues, confidence = self.analyze_continuation_rule_based(page1, page2)
            return {
                "continues": continues,
                "confidence": confidence,
                "chapter": None,
                "section": None,
                "main_topic": self.extract_main_topic(page2.content),
            }
    
    def analyze_page(
        self,
        page: CleanedPage,
        prev_page: Optional[CleanedPage] = None,
        next_page: Optional[CleanedPage] = None,
    ) -> LinkedPage:
        """
        Analyze a single page with context from adjacent pages.
        
        Args:
            page: Current page to analyze
            prev_page: Previous page (if any)
            next_page: Next page (if any)
            
        Returns:
            LinkedPage with relationship metadata
        """
        # Detect sentence boundaries
        starts_mid, ends_mid = self.detect_sentence_boundaries(page.content)
        
        # Detect chapter/section
        chapter, section = self.detect_chapter_section(page.content, page.title)
        
        # Extract main topic
        main_topic = self.extract_main_topic(page.content)
        
        # Analyze continuation from previous
        continues_from = False
        continuation_confidence = 0.0
        
        if prev_page:
            if self.use_llm:
                analysis = self.analyze_continuation_llm(prev_page, page)
                continues_from = analysis["continues"]
                continuation_confidence = analysis["confidence"]
                # Use LLM's chapter/section/topic if available
                if analysis.get("chapter"):
                    chapter = analysis["chapter"]
                if analysis.get("section"):
                    section = analysis["section"]
                if analysis.get("main_topic"):
                    main_topic = analysis["main_topic"]
            else:
                continues_from, continuation_confidence = self.analyze_continuation_rule_based(prev_page, page)
        
        # Analyze continuation to next
        continues_to = False
        if next_page:
            if self.use_llm:
                analysis = self.analyze_continuation_llm(page, next_page)
                continues_to = analysis["continues"]
            else:
                continues_to, _ = self.analyze_continuation_rule_based(page, next_page)
        
        return LinkedPage(
            page_number=page.page_number,
            page_type=page.page_type,
            title=page.title,
            content=page.content,
            original_content=page.original_content,
            has_sanskrit=page.has_sanskrit,
            verses=page.verses,
            verse_numbers=page.verse_numbers,
            tables=page.tables,
            cleaning_applied=page.cleaning_applied,
            continues_from_previous=continues_from,
            continues_to_next=continues_to,
            continuation_confidence=continuation_confidence,
            chapter=chapter,
            section=section,
            main_topic=main_topic,
            topic_id=main_topic.lower().replace(' ', '-') if main_topic else None,
            related_pages=[],  # Will be populated in document-level analysis
            starts_mid_sentence=starts_mid,
            ends_mid_sentence=ends_mid,
        )
    
    def analyze_document(
        self,
        cleaned_doc: CleanedDocument,
    ) -> LinkedDocument:
        """
        Analyze all pages in a document for relationships.
        
        Args:
            cleaned_doc: Cleaned document from Phase 2
            
        Returns:
            LinkedDocument with all relationship metadata
        """
        pages = cleaned_doc.pages
        linked_pages: List[LinkedPage] = []
        
        for i, page in enumerate(pages):
            prev_page = pages[i - 1] if i > 0 else None
            next_page = pages[i + 1] if i < len(pages) - 1 else None
            
            linked_page = self.analyze_page(page, prev_page, next_page)
            linked_pages.append(linked_page)
        
        # Build topic clusters
        topic_clusters: Dict[str, List[int]] = {}
        for page in linked_pages:
            if page.topic_id:
                if page.topic_id not in topic_clusters:
                    topic_clusters[page.topic_id] = []
                topic_clusters[page.topic_id].append(page.page_number)
        
        # Add related pages based on topic clusters
        for page in linked_pages:
            if page.topic_id and page.topic_id in topic_clusters:
                page.related_pages = [
                    p for p in topic_clusters[page.topic_id] 
                    if p != page.page_number
                ]
        
        # Collect chapters
        chapters = list(set(
            page.chapter for page in linked_pages if page.chapter
        ))
        
        return LinkedDocument(
            pages=linked_pages,
            source_file=cleaned_doc.source_file,
            chapters=chapters,
            topic_clusters=topic_clusters,
        )
    
    def process_file(
        self,
        input_file: str,
        output_file: Optional[str] = None,
    ) -> LinkedDocument:
        """
        Process a cleaned JSON file through Phase 3 analysis.
        
        Args:
            input_file: Path to cleaned JSON from Phase 2
            output_file: Optional output path
            
        Returns:
            LinkedDocument
        """
        input_path = Path(input_file)
        
        # Load cleaned document
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to CleanedDocument
        if 'pages' in data:
            cleaned_doc = CleanedDocument(**data)
        else:
            # Single page format
            pages = [CleanedPage(**data)]
            cleaned_doc = CleanedDocument(pages=pages, source_file=str(input_path))
        
        # Analyze
        linked_doc = self.analyze_document(cleaned_doc)
        
        # Save output
        if output_file is None:
            output_file = str(input_path.parent / f"{input_path.stem}_linked.json")
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(linked_doc.model_dump(), f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Analyzed {len(linked_doc.pages)} pages")
        print(f"[OK] Found {len(linked_doc.chapters)} chapters")
        print(f"[OK] Found {len(linked_doc.topic_clusters)} topic clusters")
        print(f"[OK] Saved to: {output_path}")
        
        return linked_doc


def test_with_sample():
    """Test page analyzer with sample data."""
    # First run structural cleaner to get cleaned data
    from structural_cleaner import StructuralCleaner
    
    sample_file = Path(__file__).parent.parent.parent.parent / "extracted" / "sample_bphs_pages.json"
    
    if not sample_file.exists():
        print(f"Sample file not found: {sample_file}")
        return
    
    # Phase 2: Clean
    cleaner = StructuralCleaner()
    cleaned_doc = cleaner.process_file(str(sample_file))
    
    # Phase 3: Analyze (without LLM for testing)
    analyzer = PageAnalyzer(use_llm=False)
    linked_doc = analyzer.analyze_document(cleaned_doc)
    
    print("\n" + "=" * 70)
    print("PHASE 3 ANALYSIS RESULTS")
    print("=" * 70)
    
    for page in linked_doc.pages:
        print(f"\nPage {page.page_number}:")
        print(f"  Continues from previous: {page.continues_from_previous}")
        print(f"  Continues to next: {page.continues_to_next}")
        print(f"  Confidence: {page.continuation_confidence:.2f}")
        print(f"  Chapter: {page.chapter}")
        print(f"  Main topic: {page.main_topic}")
        print(f"  Starts mid-sentence: {page.starts_mid_sentence}")
        print(f"  Ends mid-sentence: {page.ends_mid_sentence}")
    
    print(f"\nTopic Clusters: {linked_doc.topic_clusters}")


if __name__ == "__main__":
    test_with_sample()
