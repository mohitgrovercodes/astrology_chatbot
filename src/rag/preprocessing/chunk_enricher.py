# src/rag/preprocessing/chunk_enricher.py
# src\rag\preprocessing\chunk_enricher.py
#!/usr/bin/env python3
"""
Phase 5: Chunk Enrichment

Prepare semantic units for optimal embedding and retrieval by:
- Constructing embedding-optimized text
- Extracting astrological entities
- Creating summaries
"""

import re
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Handle both relative and direct imports
try:
    from .schemas import (
        SemanticUnit,
        SemanticDocument,
        EnrichedChunk,
        EnrichedDocument,
        ChunkMetadata,
        AstrologicalEntities,
        UnitType,
    )
    from .yoga_catalog import extract_yogas
    from .planet_catalog import extract_planets
except ImportError:
    from schemas import (
        SemanticUnit,
        SemanticDocument,
        EnrichedChunk,
        EnrichedDocument,
        ChunkMetadata,
        AstrologicalEntities,
        UnitType,
    )
    from yoga_catalog import extract_yogas
    from planet_catalog import extract_planets

try:
    from src.llm.factory import create_llm
except ImportError:
    try:
        from ...llm.factory import create_llm
    except ImportError:
        create_llm = None

class ChunkEnricher:
    """
    Enrich semantic units with metadata for optimal RAG retrieval.
    """
    
    # Astrological entity catalogs
    PLANETS = [
        'Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn',
        'Rahu', 'Ketu', 'Gulika', 'Mandi',
        # Sanskrit names
        'Surya', 'Chandra', 'Mangal', 'Budh', 'Guru', 'Shukra', 'Shani',
    ]
    
    HOUSES = [
        '1st House', '2nd House', '3rd House', '4th House', '5th House', '6th House',
        '7th House', '8th House', '9th House', '10th House', '11th House', '12th House',
        'Lagna', 'Ascendant', 'First House', 'Second House', 'Third House',
        'Fourth House', 'Fifth House', 'Sixth House', 'Seventh House',
        'Eighth House', 'Ninth House', 'Tenth House', 'Eleventh House', 'Twelfth House',
    ]
    
    SIGNS = [
        'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
        'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
        # Sanskrit names
        'Mesha', 'Vrishabha', 'Mithuna', 'Karka', 'Simha', 'Kanya',
        'Tula', 'Vrischika', 'Dhanu', 'Makara', 'Kumbha', 'Meena',
    ]
    
    NAKSHATRAS = [
        'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
        'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
        'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
        'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha',
        'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati',
    ]
    
    CONCEPTS = [
        'horoscope', 'birth chart', 'natal chart', 'dasha', 'mahadasha', 'antardasha',
        'aspect', 'conjunction', 'opposition', 'trine', 'yoga', 'dosha', 'remedies',
        'transit', 'prediction', 'compatibility', 'marriage', 'career', 'wealth',
        'health', 'progeny', 'children', 'education', 'property', 'vehicle',
        'enemies', 'litigation', 'death', 'longevity', 'spirituality',
    ]
    
    # Approximate chars per token
    CHARS_PER_TOKEN = 4
    
    def __init__(self, use_llm: bool = True, tradition: str = "vedic", parallel_workers: int =1, model_name: str = "gemini-2.5-flash"):
        self.use_llm = use_llm
        self.tradition = tradition
        self.parallel_workers = parallel_workers
        self.model = None
        
        if use_llm:
            try:
                # Create LLM using factory
                self.model = create_llm(
                    provider="google",
                    model=model_name,
                    temperature=0.1,
                    use_rate_limiting=True,
                    rate_limit_delay=5.0  # Optimized: 5s delay is safer than 2s but faster than 12s 
                )
                
                # Determine which provider was used
                from langchain_google_vertexai import ChatVertexAI
                self.is_vertex_ai = isinstance(self.model, ChatVertexAI)
                
                provider_name = "Vertex AI" if self.is_vertex_ai else "AI Studio"
                print(f"[âœ…] Using {provider_name} via LLMFactory with rate limiting")
                
            except Exception as e:
                print(f"[WARN] LLM initialization failed: {e}")
                print("[INFO] Using rule-based analysis only")
                self.use_llm = False
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from character count."""
        return len(text) // self.CHARS_PER_TOKEN
    
    def extract_entities(self, text: str) -> AstrologicalEntities:
        """
        Extract astrological entities from text using rule-based matching.
        
        Args:
            text: Content text
            
        Returns:
            AstrologicalEntities object
        """
        text_lower = text.lower()
        
        # Planets go through planet_catalog: it canonicalizes every Sanskrit
        # alias (Surya, Chandra, Mangal, Kuja, Shani, Bṛhaspati, ...) back to
        # the English canonical (Sun, Moon, Mars, Jupiter, Saturn, ...) and
        # uses word-boundary regex so author names like "Suryanarain" and
        # adjectives like "Manda" don't generate false positives.
        planets = extract_planets(text)

        houses = [h for h in self.HOUSES if h.lower() in text_lower]
        signs = [s for s in self.SIGNS if s.lower() in text_lower]
        nakshatras = [n for n in self.NAKSHATRAS if n.lower() in text_lower]
        concepts = [c for c in self.CONCEPTS if c.lower() in text_lower]

        # Deduplicate (e.g., "1st House" and "First House" are same)
        houses = list(set(houses))

        # Yogas use a dedicated catalog (yoga_catalog.py) because the naming
        # is much more specific than the substring matching above can handle —
        # generic Sanskrit words like "mala", "gada", "raja" only count as a
        # yoga when followed by a "Yoga"/"Yog"/"Yogas" qualifier, and compound
        # yogas like "Kala Sarpa" or "Vipreet Raja Yoga" need to suppress the
        # generic single-word match they would otherwise also trigger.
        yogas = extract_yogas(text)

        return AstrologicalEntities(
            planets=planets,
            houses=houses,
            signs=signs,
            nakshatras=nakshatras,
            yogas=yogas,
            concepts=concepts,
        )
    
    def generate_summary_rule_based(self, unit: SemanticUnit) -> str:
        """
        Generate a simple summary using rule-based approach.
        
        Args:
            unit: Semantic unit
            
        Returns:
            Summary string
        """
        # Extract key elements
        parts = []
        
        if unit.verse and unit.verse.number:
            parts.append(f"Verse {unit.verse.number}")
        
        if unit.chapter:
            chapter_short = unit.chapter.split(':')[-1].strip() if ':' in unit.chapter else unit.chapter
            parts.append(f"from {chapter_short}")
        
        # Extract main subject from first sentence of commentary
        if unit.commentary:
            first_sentence = unit.commentary.split('.')[0]
            if len(first_sentence) > 20:
                # Truncate if too long
                first_sentence = first_sentence[:100] + "..."
            parts.append(f"- {first_sentence}")
        
        return ' '.join(parts) if parts else "Astrological teaching"
    
    def generate_summary_llm(self, unit: SemanticUnit) -> str:
        """
        Generate summary using LLM.
        
        Args:
            unit: Semantic unit
            
        Returns:
            Summary string
        """
        if not self.model:
            return self.generate_summary_rule_based(unit)
        
        prompt = f"""Summarize this astrological text in 1-2 sentences. Focus on the key teaching or prediction.

TEXT:
{unit.combined_text[:1000]}

Return ONLY the summary, no explanation."""

        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                # Different API calls for Vertex AI vs AI Studio
                # LangChain invoke (works for all providers from factory)
                response = self.model.invoke(prompt)
                text = response.content.strip() if hasattr(response, 'content') else str(response)
                return text
                
            except Exception as e:
                is_last_attempt = (attempt == max_retries - 1)
                
                # Check for rate limits (429)
                if "429" in str(e):
                    wait_time = base_delay * (2 ** attempt)
                    print(f"  [WARN] Rate limit hit. Waiting {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                else:
                    print(f"  [WARN] LLM summary failed (Attempt {attempt+1}/{max_retries}): {e}")
                
                if is_last_attempt:
                    # If strict mode is preferred, we return an empty string or raise error
                    # But returning empty string is safer than crashing the whole enrichment
                    print(f"  [ERROR] Failed to generate summary for unit. Returning empty string.")
                    return ""
    
    def construct_embedding_text(
        self, 
        unit: SemanticUnit, 
        summary: str
    ) -> str:
        """
        Construct optimized text for embedding.
        
        Args:
            unit: Semantic unit
            summary: Generated summary
            
        Returns:
            Optimized embedding text
        """
        parts = []
        
        # 1. Contextual header
        if unit.chapter:
            parts.append(f"Topic: {unit.chapter}")
        if unit.section:
            parts.append(f"Section: {unit.section}")
        
        # 2. Summary (front-loads key concepts for embedding)
        if summary:
            parts.append(f"Summary: {summary}")
        
        # 3. Main content
        parts.append(unit.combined_text)
        
        return "\n\n".join(parts)
    
    def enrich_unit(self, unit: SemanticUnit) -> EnrichedChunk:
        """
        Enrich a single semantic unit.
        
        Args:
            unit: Semantic unit from Phase 4
            
        Returns:
            EnrichedChunk ready for embedding
        """
        # Extract entities
        entities = self.extract_entities(unit.combined_text)
        
        # Generate summary
        if self.use_llm:
            summary = self.generate_summary_llm(unit)
        else:
            summary = self.generate_summary_rule_based(unit)
        
        # Construct embedding text
        embedding_text = self.construct_embedding_text(unit, summary)
        
        # Build metadata
        metadata = ChunkMetadata(
            source_book=unit.source_book or "Unknown",
            chapter=unit.chapter,
            section=unit.section,
            verse_number=unit.verse.number if unit.verse else None,
            tradition=self.tradition,
            entities=entities,
        )
        
        return EnrichedChunk(
            chunk_id=f"{unit.unit_id}-chunk",
            unit_id=unit.unit_id,
            text_for_embedding=embedding_text,
            token_count=self.estimate_tokens(embedding_text),
            display_text=unit.combined_text,
            verse_sanskrit=unit.verse.sanskrit if unit.verse else None,
            metadata=metadata,
            hypothetical_questions=[],
            summary=summary,
            related_chunks=[f"{uid}-chunk" for uid in unit.related_units],
            source_pages=unit.source_pages,
            embedding=None,  # Will be populated in Phase 6
        )
    
    def enrich_document(self, semantic_doc: SemanticDocument, use_parallel: bool = True) -> EnrichedDocument:
        """
        Enrich all units in a document with optional parallel processing.
        
        Args:
            semantic_doc: Semantic document from Phase 4
            use_parallel: Whether to use parallel processing (default: True)
            
        Returns:
            EnrichedDocument ready for embedding
        """
        if use_parallel and self.parallel_workers > 1:
            # Parallel processing for significant speedup
            chunks = self._enrich_parallel(semantic_doc.units)
        else:
            # Sequential processing
            chunks = [self.enrich_unit(unit) for unit in semantic_doc.units]
        
        total_tokens = sum(chunk.token_count for chunk in chunks)
        
        return EnrichedDocument(
            chunks=chunks,
            source_file=semantic_doc.source_file,
            total_tokens=total_tokens,
        )
    
    def _enrich_parallel(self, units: List[SemanticUnit]) -> List[EnrichedChunk]:
        """
        Enrich units in parallel using ThreadPoolExecutor.
        
        Args:
            units: List of semantic units to enrich
            
        Returns:
            List of enriched chunks (order preserved)
        """
        print(f"  [PARALLEL] Processing {len(units)} units with {self.parallel_workers} workers...")
        
        chunks = [None] * len(units)  # Pre-allocate to preserve order
        
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            # Submit all enrichment tasks
            future_to_index = {
                executor.submit(self.enrich_unit, unit): i 
                for i, unit in enumerate(units)
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    chunks[index] = future.result()
                    completed += 1
                    if completed % 10 == 0:  # Progress indicator
                        print(f"  [PROGRESS] {completed}/{len(units)} chunks enriched")
                except Exception as e:
                    print(f"  [ERROR] Failed to enrich unit {index}: {e}")
                    # Create a minimal fallback chunk
                    unit = units[index]
                    chunks[index] = EnrichedChunk(
                        chunk_id=f"{unit.unit_id}-chunk",
                        unit_id=unit.unit_id,
                        text_for_embedding=unit.combined_text,
                        token_count=self.estimate_tokens(unit.combined_text),
                        display_text=unit.combined_text,
                        verse_sanskrit=unit.verse.sanskrit if unit.verse else None,
                        metadata=ChunkMetadata(
                            source_book=unit.source_book or "Unknown",
                            chapter=unit.chapter,
                            section=unit.section,
                            verse_number=unit.verse.number if unit.verse else None,
                            tradition=self.tradition,
                            entities=AstrologicalEntities(),
                        ),
                        hypothetical_questions=[],
                        summary="",
                        related_chunks=[],
                        source_pages=unit.source_pages,
                        embedding=None,
                    )
        
        print(f"  [COMPLETE] All {len(units)} chunks enriched")
        return chunks
    
    def process_file(
        self,
        input_file: str,
        output_file: Optional[str] = None,
    ) -> EnrichedDocument:
        """
        Process a semantic JSON file through Phase 5 enrichment.
        
        Args:
            input_file: Path to semantic JSON from Phase 4
            output_file: Optional output path
            
        Returns:
            EnrichedDocument
        """
        input_path = Path(input_file)
        
        # Load semantic document
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        semantic_doc = SemanticDocument(**data)
        
        # Enrich
        enriched_doc = self.enrich_document(semantic_doc)
        
        # Save output
        if output_file is None:
            output_file = str(input_path.parent / f"{input_path.stem}_enriched.json")
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(enriched_doc.model_dump(), f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Enriched {len(enriched_doc.chunks)} chunks")
        print(f"[OK] Total tokens: {enriched_doc.total_tokens}")
        print(f"[OK] Saved to: {output_path}")
        
        return enriched_doc


def test_with_sample():
    """Test chunk enricher with sample data."""
    from structural_cleaner import StructuralCleaner
    from page_analyzer import PageAnalyzer
    from semantic_segmenter import SemanticSegmenter
    
    sample_file = Path(__file__).parent.parent.parent.parent / "extracted" / "sample_bphs_pages.json"
    
    if not sample_file.exists():
        print(f"Sample file not found: {sample_file}")
        return
    
    # Phase 2: Clean
    print("Phase 2: Cleaning...")
    cleaner = StructuralCleaner()
    import schemas
    cleaned_doc = cleaner.clean_document(
        [schemas.ExtractedPage(**p) for p in json.loads(sample_file.read_text(encoding='utf-8'))],
        source_file=str(sample_file)
    )
    
    # Phase 3: Analyze
    print("Phase 3: Analyzing...")
    analyzer = PageAnalyzer(use_llm=False)
    linked_doc = analyzer.analyze_document(cleaned_doc)
    
    # Phase 4: Segment
    print("Phase 4: Segmenting...")
    segmenter = SemanticSegmenter(source_book="Brihat Parasara Hora Shastra")
    semantic_doc = segmenter.segment_document(linked_doc)
    
    # Phase 5: Enrich (without LLM for testing)
    print("Phase 5: Enriching...")
    enricher = ChunkEnricher(use_llm=False, tradition="vedic")
    enriched_doc = enricher.enrich_document(semantic_doc)
    
    print("\n" + "=" * 70)
    print("PHASE 5 ENRICHMENT RESULTS")
    print("=" * 70)
    
    for chunk in enriched_doc.chunks[:3]:  # Show first 3
        print(f"\nChunk: {chunk.chunk_id}")
        print(f"  Tokens: {chunk.token_count}")
        summary_display = (chunk.summary[:100] if chunk.summary else 'N/A').encode('ascii', 'replace').decode('ascii')
        print(f"  Summary: {summary_display}...")
        print(f"  Planets: {chunk.metadata.entities.planets}")
        print(f"  Houses: {chunk.metadata.entities.houses}")
    
    print(f"\nTotal chunks: {len(enriched_doc.chunks)}")
    print(f"Total tokens for embedding: {enriched_doc.total_tokens}")


if __name__ == "__main__":
    test_with_sample()
