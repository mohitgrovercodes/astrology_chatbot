#!/usr/bin/env python3
"""
Phase 5: Chunk Enrichment

Prepare semantic units for optimal embedding and retrieval by:
- Constructing embedding-optimized text
- Generating hypothetical questions
- Extracting astrological entities
- Creating summaries
"""

import re
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

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
    
    def __init__(self, use_llm: bool = True, tradition: str = "vedic"):
        """
        Initialize chunk enricher.
        
        Args:
            use_llm: Whether to use LLM for question generation and summaries
            tradition: "vedic" or "western"
        """
        self.use_llm = use_llm
        self.tradition = tradition
        self.model = None
        self.is_vertex_ai = False
        
        if use_llm:
            # Try Vertex AI first (GCP credits)
            try:
                from langchain_google_vertexai import ChatVertexAI
                project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
                
                if project:
                    self.model = ChatVertexAI(
                        model="gemini-2.0-flash-exp",
                        project=project,
                        location=location,
                        temperature=0.0,
                    )
                    self.is_vertex_ai = True
                    print(f"[OK] Using Vertex AI (GCP) - Project: {project}, Location: {location}")
                else:
                    print("[WARN] GOOGLE_CLOUD_PROJECT not set, trying AI Studio")
                    raise ValueError("No GCP project configured")
            except Exception as e:
                print(f"[INFO] Vertex AI init failed: {e}")
                # Fallback to AI Studio
                try:
                    import google.generativeai as genai
                    api_key = os.environ.get("GOOGLE_API_KEY")
                    if api_key:
                        genai.configure(api_key=api_key)
                        self.model = genai.GenerativeModel('models/gemini-2.0-flash-exp')
                        self.is_vertex_ai = False
                        print("[OK] Using AI Studio API (fallback)")
                    else:
                        print("[WARN] No API keys, using rule-based enrichment only")
                        self.use_llm = False
                except ImportError:
                    print("[WARN] google-generativeai not installed, using rule-based enrichment only")
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
        
        planets = [p for p in self.PLANETS if p.lower() in text_lower]
        houses = [h for h in self.HOUSES if h.lower() in text_lower]
        signs = [s for s in self.SIGNS if s.lower() in text_lower]
        nakshatras = [n for n in self.NAKSHATRAS if n.lower() in text_lower]
        concepts = [c for c in self.CONCEPTS if c.lower() in text_lower]
        
        # Deduplicate (e.g., "1st House" and "First House" are same)
        houses = list(set(houses))
        planets = list(set(planets))
        
        return AstrologicalEntities(
            planets=planets,
            houses=houses,
            signs=signs,
            nakshatras=nakshatras,
            yogas=[],  # Would need more sophisticated extraction
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

        try:
            # Different API calls for Vertex AI vs AI Studio
            if self.is_vertex_ai:
                # Vertex AI (LangChain ChatVertexAI)
                response = self.model.invoke(prompt)
                text = response.content.strip()
            else:
                # AI Studio (google.generativeai)
                response = self.model.generate_content(prompt)
                text = response.text.strip()
            return text
        except Exception as e:
            print(f"[WARN] LLM summary failed: {e}")
            return self.generate_summary_rule_based(unit)
    
    def generate_questions_rule_based(self, unit: SemanticUnit, entities: AstrologicalEntities) -> List[str]:
        """
        Generate hypothetical questions using rule-based templates.
        
        Args:
            unit: Semantic unit
            entities: Extracted entities
            
        Returns:
            List of question strings
        """
        questions = []
        
        # Planet in house questions
        for planet in entities.planets[:2]:
            for house in entities.houses[:2]:
                questions.append(f"What happens when {planet} is in the {house}?")
                questions.append(f"What are the effects of {planet} in {house}?")
        
        # General topic questions
        if unit.chapter:
            chapter_topic = unit.chapter.split(':')[-1].strip() if ':' in unit.chapter else unit.chapter
            questions.append(f"What does the text say about {chapter_topic}?")
        
        # Verse-specific questions
        if unit.verse:
            questions.append(f"What is the meaning of verse {unit.verse.number}?")
        
        # Concept questions
        for concept in entities.concepts[:2]:
            questions.append(f"How does this affect {concept}?")
        
        return questions[:5]  # Limit to 5 questions
    
    def generate_questions_llm(self, unit: SemanticUnit) -> List[str]:
        """
        Generate questions using LLM.
        
        Args:
            unit: Semantic unit
            
        Returns:
            List of question strings
        """
        if not self.model:
            entities = self.extract_entities(unit.combined_text)
            return self.generate_questions_rule_based(unit, entities)
        
        prompt = f"""Given this astrology text, generate 3-5 questions a user might ask that this text answers.

TEXT:
{unit.combined_text[:1500]}

Return questions as a JSON array of strings. Example: ["Question 1?", "Question 2?"]
Return ONLY the JSON array, no explanation."""

        try:
            # Different API calls for Vertex AI vs AI Studio
            if self.is_vertex_ai:
                # Vertex AI (LangChain ChatVertexAI)
                response = self.model.invoke(prompt)
                text = response.content.strip()
            else:
                # AI Studio (google.generativeai)
                response = self.model.generate_content(prompt)
                text = response.text.strip()
            
            # Extract JSON array
            if text.startswith('```'):
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            
            questions = json.loads(text)
            return questions[:5]
        except Exception as e:
            print(f"[WARN] LLM question generation failed: {e}")
            entities = self.extract_entities(unit.combined_text)
            return self.generate_questions_rule_based(unit, entities)
    
    def construct_embedding_text(
        self, 
        unit: SemanticUnit, 
        summary: str,
        questions: List[str]
    ) -> str:
        """
        Construct optimized text for embedding.
        
        Args:
            unit: Semantic unit
            summary: Generated summary
            questions: Generated questions
            
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
        
        # 4. Hypothetical questions (HyDE-style boost)
        if questions:
            parts.append("Related questions: " + " | ".join(questions[:3]))
        
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
        
        # Generate questions
        if self.use_llm:
            questions = self.generate_questions_llm(unit)
        else:
            questions = self.generate_questions_rule_based(unit, entities)
        
        # Construct embedding text
        embedding_text = self.construct_embedding_text(unit, summary, questions)
        
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
            hypothetical_questions=questions,
            summary=summary,
            related_chunks=[f"{uid}-chunk" for uid in unit.related_units],
            source_pages=unit.source_pages,
            embedding=None,  # Will be populated in Phase 6
        )
    
    def enrich_document(self, semantic_doc: SemanticDocument) -> EnrichedDocument:
        """
        Enrich all units in a document.
        
        Args:
            semantic_doc: Semantic document from Phase 4
            
        Returns:
            EnrichedDocument ready for embedding
        """
        chunks = []
        total_tokens = 0
        
        for unit in semantic_doc.units:
            chunk = self.enrich_unit(unit)
            chunks.append(chunk)
            total_tokens += chunk.token_count
        
        return EnrichedDocument(
            chunks=chunks,
            source_file=semantic_doc.source_file,
            total_tokens=total_tokens,
        )
    
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
        print(f"  Questions: {chunk.hypothetical_questions[:2]}")
        print(f"  Planets: {chunk.metadata.entities.planets}")
        print(f"  Houses: {chunk.metadata.entities.houses}")
    
    print(f"\nTotal chunks: {len(enriched_doc.chunks)}")
    print(f"Total tokens for embedding: {enriched_doc.total_tokens}")


if __name__ == "__main__":
    test_with_sample()
