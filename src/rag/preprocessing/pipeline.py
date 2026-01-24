#!/usr/bin/env python3
"""
Text Pre-Processing Pipeline Orchestration

Runs all phases from extraction to embedding-ready chunks.
Supports checkpointing and resuming from any phase.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directories to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(project_root))

# Import Vision Pipeline
from src.rag.extraction.vision_pipeline import VisionPipeline, PipelineConfig

# Import all phase modules
from schemas import ExtractedPage, CleanedDocument, LinkedDocument, SemanticDocument, EnrichedDocument
from structural_cleaner import StructuralCleaner
from page_analyzer import PageAnalyzer
from semantic_segmenter import SemanticSegmenter
from chunk_enricher import ChunkEnricher
from embedder import Embedder


class PreprocessingPipeline:
    """
    End-to-end preprocessing pipeline orchestrator.
    """
    
    def __init__(
        self,
        source_book: str = "Unknown Source",
        tradition: str = "vedic",
        use_llm: bool = False,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize pipeline.
        
        Args:
            source_book: Name of the source book
            tradition: "vedic" or "western"
            use_llm: Whether to use LLM for analysis/enrichment
            output_dir: Directory for intermediate outputs
        """
        self.source_book = source_book
        self.tradition = tradition
        self.use_llm = use_llm
        self.output_dir = Path(output_dir) if output_dir else None
        
        # Initialize phase processors
        self.cleaner = StructuralCleaner()
        self.analyzer = PageAnalyzer(use_llm=use_llm)
        self.segmenter = SemanticSegmenter(source_book=source_book)
        self.enricher = ChunkEnricher(use_llm=use_llm, tradition=tradition)
        self.embedder = Embedder()
    
    def _save_checkpoint(self, data, phase_name: str, input_path: Path):
        """Save intermediate output."""
        if self.output_dir:
            output_path = self.output_dir / f"{input_path.stem}_{phase_name}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data.model_dump(), f, ensure_ascii=False, indent=2)
            print(f"  [CHECKPOINT] Saved: {output_path.name}")
            return output_path
        return None
    
    def run_phase1_extraction(self, input_pdf: str, output_dir: Optional[str] = None) -> str:
        """Run Phase 1: PDF Extraction using Vision Pipeline."""
        print("\n" + "=" * 60)
        print("PHASE 1: EXTRACTION (Vision LLM)")
        print("=" * 60)
        
        pdf_path = Path(input_pdf)
        if not output_dir:
            output_dir = str(pdf_path.parent / "extracted")
            
        print(f"  Input PDF: {pdf_path.name}")
        print(f"  Output Dir: {output_dir}")
        
        config = PipelineConfig(
            output_dir=output_dir,
            gemini_model="gemini-2.5-flash",  # Standardized model
            book_title=self.source_book,
            save_raw_responses=True
        )
        
        vision_pipeline = VisionPipeline(config)
        
        # Process PDF
        result = vision_pipeline.process_pdf(
            pdf_path=str(pdf_path),
            book_title=self.source_book
        )
        
        # Return path to the extraction JSON
        extraction_json = Path(output_dir) / f"{pdf_path.stem}_extraction.json"
        
        if not extraction_json.exists():
             # Fallback if naming differs
             extraction_json = Path(output_dir) / "extraction_output" / f"{pdf_path.stem}_extraction.json"
        
        print(f"  Extraction complete: {extraction_json}")
        return str(extraction_json)

    def run_phase2(self, input_file: str) -> CleanedDocument:
        """Run Phase 2: Structural Cleaning."""
        print("\n" + "=" * 60)
        print("PHASE 2: STRUCTURAL CLEANING")
        print("=" * 60)
        
        input_path = Path(input_file)
        
        # Load extracted pages
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            pages = [ExtractedPage(**page) for page in data]
        else:
            pages = [ExtractedPage(**data)]
        
        print(f"  Input: {len(pages)} pages")
        
        # Clean
        cleaned_doc = self.cleaner.clean_document(pages, source_file=str(input_path))
        
        print(f"  Cleaned: {len(cleaned_doc.pages)} pages")
        print(f"  Global headers detected: {len(cleaned_doc.global_headers)}")
        
        self._save_checkpoint(cleaned_doc, "phase2_cleaned", input_path)
        
        return cleaned_doc
    
    def run_phase3(self, cleaned_doc: CleanedDocument) -> LinkedDocument:
        """Run Phase 3: Cross-Page Analysis."""
        print("\n" + "=" * 60)
        print("PHASE 3: CROSS-PAGE ANALYSIS")
        print("=" * 60)
        
        linked_doc = self.analyzer.analyze_document(cleaned_doc)
        
        # Count continuations
        continuations = sum(1 for p in linked_doc.pages if p.continues_from_previous)
        print(f"  Analyzed: {len(linked_doc.pages)} pages")
        print(f"  Continuations detected: {continuations}")
        print(f"  Chapters found: {len(linked_doc.chapters)}")
        print(f"  Topic clusters: {len(linked_doc.topic_clusters)}")
        
        if cleaned_doc.source_file:
            self._save_checkpoint(linked_doc, "phase3_linked", Path(cleaned_doc.source_file))
        
        return linked_doc
    
    def run_phase4(self, linked_doc: LinkedDocument) -> SemanticDocument:
        """Run Phase 4: Semantic Segmentation."""
        print("\n" + "=" * 60)
        print("PHASE 4: SEMANTIC SEGMENTATION")
        print("=" * 60)
        
        semantic_doc = self.segmenter.segment_document(linked_doc)
        
        # Count by type
        verse_units = sum(1 for u in semantic_doc.units if u.unit_type == "verse_commentary")
        table_units = sum(1 for u in semantic_doc.units if u.unit_type == "table_context")
        concept_units = len(semantic_doc.units) - verse_units - table_units
        
        print(f"  Created: {len(semantic_doc.units)} semantic units")
        print(f"    - Verse-commentary: {verse_units}")
        print(f"    - Table-context: {table_units}")
        print(f"    - Concept/intro: {concept_units}")
        
        if linked_doc.source_file:
            self._save_checkpoint(semantic_doc, "phase4_segmented", Path(linked_doc.source_file))
        
        return semantic_doc
    
    def run_phase5(self, semantic_doc: SemanticDocument) -> EnrichedDocument:
        """Run Phase 5: Chunk Enrichment."""
        print("\n" + "=" * 60)
        print("PHASE 5: CHUNK ENRICHMENT")
        print("=" * 60)
        
        enriched_doc = self.enricher.enrich_document(semantic_doc)
        
        print(f"  Enriched: {len(enriched_doc.chunks)} chunks")
        print(f"  Total tokens: {enriched_doc.total_tokens}")
        
        # Sample entity stats
        all_planets = set()
        all_houses = set()
        for chunk in enriched_doc.chunks:
            all_planets.update(chunk.metadata.entities.planets)
            all_houses.update(chunk.metadata.entities.houses)
        
        print(f"  Unique planets: {len(all_planets)}")
        print(f"  Unique houses: {len(all_houses)}")
        
        if semantic_doc.source_file:
            self._save_checkpoint(enriched_doc, "phase5_enriched", Path(semantic_doc.source_file))
        
        return enriched_doc
    
    def run_phase6(self, enriched_doc: EnrichedDocument, skip_embedding: bool = False) -> EnrichedDocument:
        """Run Phase 6: Embedding."""
        print("\n" + "=" * 60)
        print("PHASE 6: EMBEDDING")
        print("=" * 60)
        
        if skip_embedding:
            print("  [SKIP] Embedding skipped (--skip-embedding flag)")
            return enriched_doc
        
        if not self.embedder.client:
            print("  [SKIP] No OpenAI API key, skipping embedding")
            return enriched_doc
        
        embedded_doc = self.embedder.embed_document(enriched_doc)
        
        # Count successful embeddings
        embedded_count = sum(1 for c in embedded_doc.chunks if c.embedding and any(e != 0 for e in c.embedding))
        print(f"  Embedded: {embedded_count}/{len(embedded_doc.chunks)} chunks")
        
        if enriched_doc.source_file:
            self._save_checkpoint(embedded_doc, "phase6_embedded", Path(enriched_doc.source_file))
        
        return embedded_doc
    
    def run_full_pipeline(
        self,
        input_file: str,
        skip_embedding: bool = False,
    ) -> EnrichedDocument:
        """
        Run the complete pipeline from Phase 1/2 to Phase 6.
        
        Args:
            input_file: Path to input file (PDF for Phase 1, or JSON for Phase 2)
            skip_embedding: Skip Phase 6 embedding
            
        Returns:
            Final EnrichedDocument
        """
        start_time = datetime.now()
        
        print("\n" + "=" * 70)
        print("TEXT PRE-PROCESSING PIPELINE")
        print("=" * 70)
        print(f"Input: {input_file}")
        print(f"Source Book: {self.source_book}")
        print(f"Tradition: {self.tradition}")
        print(f"Use LLM: {self.use_llm}")
        print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Phase 1: Extraction (if input is PDF)
        current_input = input_file
        if input_file.lower().endswith('.pdf'):
            # Determine output directory for extraction
            extract_dir = self.output_dir if self.output_dir else None
            current_input = self.run_phase1_extraction(input_file, str(extract_dir) if extract_dir else None)
        
        # Phase 2
        cleaned_doc = self.run_phase2(current_input)
        
        # Phase 3
        linked_doc = self.run_phase3(cleaned_doc)
        
        # Phase 4
        semantic_doc = self.run_phase4(linked_doc)
        
        # Phase 5
        enriched_doc = self.run_phase5(semantic_doc)
        
        # Phase 6
        final_doc = self.run_phase6(enriched_doc, skip_embedding)
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Chunks ready for VectorDB: {len(final_doc.chunks)}")
        print(f"Total tokens: {final_doc.total_tokens}")
        
        return final_doc


def main():
    parser = argparse.ArgumentParser(
        description="Text Pre-Processing Pipeline for Astrology RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py input.json
  python pipeline.py input.json --output-dir ./processed --source-book "BPHS"
  python pipeline.py input.json --use-llm --skip-embedding
        """
    )
    
    parser.add_argument("input", help="Input file (PDF or JSON)")
    parser.add_argument("-o", "--output-dir", help="Directory for intermediate outputs")
    parser.add_argument("-s", "--source-book", default="Brihat Parasara Hora Shastra",
                       help="Name of the source book")
    parser.add_argument("-t", "--tradition", choices=["vedic", "western"], default="vedic",
                       help="Astrology tradition")
    parser.add_argument("--use-llm", action="store_true",
                       help="Use LLM for enhanced analysis")
    parser.add_argument("--skip-embedding", action="store_true",
                       help="Skip Phase 6 embedding")
    
    args = parser.parse_args()
    
    # Create output directory if specified
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
    
    # Run pipeline
    pipeline = PreprocessingPipeline(
        source_book=args.source_book,
        tradition=args.tradition,
        use_llm=args.use_llm,
        output_dir=args.output_dir,
    )
    
    result = pipeline.run_full_pipeline(
        args.input,
        skip_embedding=args.skip_embedding,
    )
    
    # Save final output
    input_path = Path(args.input)
    if args.output_dir:
        output_path = Path(args.output_dir) / f"{input_path.stem}_final.json"
    else:
        output_path = input_path.parent / f"{input_path.stem}_final.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Final output: {output_path}")


if __name__ == "__main__":
    main()
