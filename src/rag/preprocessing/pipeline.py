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
from vector_db_builder import VectorDBBuilder


class PreprocessingPipeline:
    """
    End-to-end preprocessing pipeline orchestrator.
    """
    
    def __init__(
        self,
        source_book: str = "Unknown Source",
        tradition: str = "vedic",
        use_llm: bool = False,
        use_llm_cleaning: bool = False,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize pipeline.
        
        Args:
            source_book: Name of the source book
            tradition: "vedic" or "western"
            use_llm: Whether to use LLM for analysis/enrichment
            use_llm_cleaning: Whether to use LLM for Phase 2 cleaning
            output_dir: Directory for intermediate outputs
        """
        self.source_book = source_book
        self.tradition = tradition
        self.use_llm = use_llm
        self.use_llm_cleaning = use_llm_cleaning
        self.output_dir = Path(output_dir) if output_dir else None
        
        # Initialize phase processors
        self.cleaner = StructuralCleaner(use_llm=use_llm_cleaning)
        # Phase 3: Use Lite model if LLM is enabled (Cost Optimization)
        self.analyzer = PageAnalyzer(use_llm=use_llm, model_name="gemini-2.5-flash-lite")
        self.segmenter = SemanticSegmenter(source_book=source_book)
        # Phase 5: Compulsory LLM usage with Flash model (Quality Assurance)
        self.enricher = ChunkEnricher(use_llm=True, tradition=tradition, model_name="gemini-2.5-flash")
        self.embedder = Embedder()
        self.vector_db_builder = VectorDBBuilder()
    
    def _save_checkpoint(self, data, phase_name: str, input_path: Path):
        """Save intermediate output."""
        if self.output_dir:
            output_path = self.output_dir / f"{input_path.stem}_{phase_name}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data.model_dump(), f, ensure_ascii=False, indent=2)
            print(f"  [CHECKPOINT] Saved: {output_path.name}")
            return output_path
        return None
    
    def run_phase1_extraction(self, input_pdf: str, output_dir: Optional[str] = None, start_page: int = None, end_page: int = None) -> str:
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
            gemini_model="gemini-2.5-flash-lite",  # Use Lite for text-heavy efficiency
            book_title=self.source_book,
            save_raw_responses=True
        )
        
        vision_pipeline = VisionPipeline(config)
        
        # Process PDF
        result = vision_pipeline.process_pdf(
            pdf_path=str(pdf_path),
            book_title=self.source_book,
            start_page=start_page,
            end_page=end_page
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
            pages = []
            for item in data:
                if isinstance(item, dict) and "metadata" in item and "content_blocks" in item:
                    pages.append(self._convert_rich_to_simple_page(item))
                else:
                    pages.append(ExtractedPage(**item))
        elif isinstance(data, dict):
            # NEW: Handle complete ExtractionResult
            if "pages" in data and isinstance(data["pages"], list):
                print(f"  Detected ExtractionResult format (Source: {data.get('source_file', 'unknown')})")
                pages = []
                for item in data["pages"]:
                     # Convert each page in the list
                     if isinstance(item, dict):
                        # Determine if it needs conversion or direct instantiation
                        # For now, assume it matches ExtractedPage schema
                        try:
                            pages.append(ExtractedPage(**item))
                        except Exception:
                             # Try conversion if direct init fails
                            pages.append(self._convert_rich_to_simple_page(item))
            elif "metadata" in data and "content_blocks" in data:
                pages = [self._convert_rich_to_simple_page(data)]
            else:
                # Fallback for unexpected single objects
                pages = [ExtractedPage(**data)]
        
        print(f"  Input: {len(pages)} pages")
        
        # Clean
        cleaned_doc = self.cleaner.clean_document(pages, source_file=str(input_path))
        
        print(f"  Cleaned: {len(cleaned_doc.pages)} pages")
        print(f"  Global headers detected: {len(cleaned_doc.global_headers)}")
        
        self._save_checkpoint(cleaned_doc, "phase2_cleaned", input_path)
        
        return cleaned_doc
    
    def _convert_rich_to_simple_page(self, rich_data: dict) -> ExtractedPage:
        """
        Convert from the rich VisionExtractor schema to the simple Preprocessing schema.
        Handles field mapping and PageType translation.
        """
        metadata = rich_data.get("metadata", {})
        
        # 1. Map PageType
        # Rich: text_heavy, table_heavy, mixed, chart, title, index
        # Simple: text, table, mixed, title_page
        rich_type = metadata.get("page_type")
        if rich_type == "text_heavy":
            simple_type = "text"
        elif rich_type == "table_heavy":
            simple_type = "table"
        elif rich_type == "title":
            simple_type = "title_page"
        elif rich_type in ["mixed", "chart", "index"]:
            simple_type = "mixed" # Fallback
        else:
            simple_type = "mixed"

        # 2. Extract content (use raw_text or join blocks)
        content = rich_data.get("raw_text")
        if not content and "content_blocks" in rich_data:
            content = "\n\n".join([b.get("text", "") for b in rich_data["content_blocks"]])
        
        # 3. Extract tables
        tables = []
        for b in rich_data.get("content_blocks", []):
            if b.get("content_type") == "table" and b.get("table_data"):
                tables.append(b["table_data"])

        # 4. Build flattened object
        return ExtractedPage(
            page_number=metadata.get("page_number", 0),
            page_type=simple_type,
            title=metadata.get("chapter_title"),
            content=content or "",
            has_sanskrit="sanskrit" in "".join(metadata.get("languages_present", [])).lower(),
            verses=[], # Simple schema doesn't strictly require these at start
            verse_numbers=[],
            tables=tables,
            confidence=rich_data.get("confidence"),
            retry_metadata=rich_data.get("retry_metadata")
        )

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
    
    def run_phase7(
        self,
        embedded_doc: EnrichedDocument,
        collection_name: Optional[str] = None,
        reset_collection: bool = False,
    ) -> dict:
        """
        Run Phase 7: Vector Database Creation.
        
        Args:
            embedded_doc: Document with embeddings from Phase 6
            collection_name: ChromaDB collection name (default: from source_book)
            reset_collection: Clear existing collection before inserting
            
        Returns:
            Statistics dictionary
        """
        print("\n" + "=" * 60)
        print("PHASE 7: VECTOR DATABASE CREATION")
        print("=" * 60)
        
        # Determine collection name
        if not collection_name and embedded_doc.chunks:
            source_book = embedded_doc.chunks[0].metadata.source_book
            collection_name = source_book.lower().replace(" ", "_").replace("-", "_")
        elif not collection_name:
            collection_name = "astrology_default"
        
        # Create collection
        self.vector_db_builder.create_collection(collection_name, reset=reset_collection)
        
        # Insert chunks
        inserted = self.vector_db_builder.insert_chunks(embedded_doc)
        
        # Get stats
        stats = self.vector_db_builder.get_collection_stats()
        stats["inserted_this_run"] = inserted
        
        print(f"  Collection: {collection_name}")
        print(f"  Inserted: {inserted} chunks")
        print(f"  Total size: {stats.get('total_chunks', 0)}")
        
        return stats
    
    def run_full_pipeline(
        self,
        input_file: str,
        skip_embedding: bool = False,
        skip_vectordb: bool = False,
        reset_collection: bool = False,
        start_page: int = None,
        end_page: int = None,
    ) -> EnrichedDocument:
        """
        Run the complete pipeline from Phase 1/2 to Phase 7.
        
        Args:
            input_file: Path to input file (PDF for Phase 1, or JSON for Phase 2)
            skip_embedding: Skip Phase 6 embedding
            skip_vectordb: Skip Phase 7 vector database creation
            reset_collection: Clear existing collection before inserting
            
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
            current_input = self.run_phase1_extraction(
                input_file, 
                str(extract_dir) if extract_dir else None,
                start_page=start_page,
                end_page=end_page
            )
            
        # Determine starting phase based on input JSON structure
        # (Naive check: load json header to guess type)
        input_data = {}
        if not input_file.lower().endswith('.pdf'):
            try:
                with open(input_file, 'r', encoding='utf-8') as f:
                    input_data = json.load(f)
            except Exception:
                pass

        # Resume Logic
        enriched_doc = None
        
        # If input has 'chunks' -> It is EnrichedDocument (Resume at Phase 6)
        if "chunks" in input_data:
            print(f"\n[INFO] Detected EnrichedDocument (Phase 5 output). Resuming at Phase 6...")
            from schemas import EnrichedDocument
            enriched_doc = EnrichedDocument(**input_data)
        else:
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
        
        # Phase 6
        final_doc = self.run_phase6(enriched_doc, skip_embedding)
        
        # Phase 7
        if not skip_vectordb and not skip_embedding:
            self.run_phase7(final_doc, reset_collection=reset_collection)
        elif skip_vectordb:
            print("\n[SKIP] Phase 7: Vector DB creation skipped (--skip-vectordb flag)")
        elif skip_embedding:
            print("\n[SKIP] Phase 7: Vector DB creation skipped (no embeddings)")
        
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
  python pipeline.py
  python pipeline.py input.json --output-dir ./processed --source-book "BPHS"
        """
    )
    
    # Make input optional to allow interactive mode
    parser.add_argument("input", nargs="?", help="Input file (PDF or JSON)")
    parser.add_argument("-o", "--output-dir", help="Directory for intermediate outputs")
    parser.add_argument("-s", "--source-book", help="Name of the source book")
    parser.add_argument("-t", "--tradition", choices=["vedic", "western"], 
                       help="Astrology tradition")
    parser.add_argument("--use-llm", action="store_true",
                       help="Use LLM for enhanced analysis")
    parser.add_argument("--skip-embedding", action="store_true",
                       help="Skip Phase 6 embedding")
    parser.add_argument("--skip-vectordb", action="store_true",
                       help="Skip Phase 7 vector database creation")
    parser.add_argument("--reset-collection", action="store_true",
                       help="Clear existing collection before inserting")
    
    args = parser.parse_args()

    # ==========================================
    # Interactive Mode
    # ==========================================
    is_interactive = not args.input
    input_file = args.input
    source_book = args.source_book
    tradition = args.tradition
    output_dir = args.output_dir
    
    print("\n" + "=" * 60)
    print("🌟 Astrology RAG Pipeline Configurator 🌟")
    print("=" * 60)

    # 1. Input File
    if not input_file:
        # Check defaults
        default_dir = Path("data/raw")
        default_dir.mkdir(parents=True, exist_ok=True)
        processed_dir = Path("processed_data")
        
        # Gather candidates
        candidates = []
        
        # 1. Raw PDFs/JSONs
        candidates.extend(list(default_dir.glob("*.pdf")))
        candidates.extend(list(default_dir.glob("*.json")))
        
        # 2. Processed Outputs (for resuming)
        if processed_dir.exists():
            candidates.extend(list(processed_dir.glob("*.json")))
            
        # 3. Extraction Outputs (if any)
        extract_dir = Path("extraction_output")
        if extract_dir.exists():
             candidates.extend(list(extract_dir.glob("*.json")))
        
        if candidates:
            print(f"\nFound available files:")
            for i, f in enumerate(candidates, 1):
                # Show parent dir for context if not in default raw
                label = f.name if f.parent == default_dir else f"{f.parent.name}/{f.name}"
                print(f"  {i}. {label}")

        while not input_file:
            prompt = "\n[1/4] Enter input file path (PDF/JSON)"
            if candidates:
                prompt += f" (or enter number 1-{len(candidates)}): "
            else:
                prompt += ": "

            val = input(prompt).strip().strip('"')
            
            # Check if user entered a number
            if val.isdigit() and candidates:
                idx = int(val) - 1
                if 0 <= idx < len(candidates):
                    input_file = str(candidates[idx])
                    print(f"     Selected: {input_file}")
                    break

            if os.path.exists(val):
                input_file = val
            elif os.path.exists(default_dir / val):
                 input_file = str(default_dir / val)
            else:
                print(f"❌ File not found: {val}")
                input_file = None
    
    # 1b. Page Range (If PDF)
    start_page = None
    end_page = None
    if input_file and input_file.lower().endswith('.pdf'):
        print(f"\n[1b/4] Page Range Extraction (Optional)")
        sp = input(f"       Start Page [1]: ").strip()
        if sp.isdigit():
            start_page = int(sp)
            ep = input(f"       End Page [All]: ").strip()
            if ep.isdigit():
                end_page = int(ep)
        else:
            print("       Using default: Start=1, End=All")
    
    # 2. Source Book
    if not source_book:
        default_name = Path(input_file).stem.replace("_", " ").title()
        print(f"\n[2/4] Enter Source Book Name (e.g., 'Jataka Parijata Vol 1')")
        user_book = input(f"      Default [{default_name}]: ").strip()
        source_book = user_book if user_book else default_name

    # 3. Tradition
    if not tradition:
        print(f"\n[3/4] Select Astrology Tradition:")
        print("      1. Vedic (Parasara/Jaimini)")
        print("      2. Western (Tropical)")
        while True:
            choice = input("      Enter choice [1]: ").strip()
            if choice == "1" or choice == "":
                tradition = "vedic"
                break
            elif choice == "2":
                tradition = "western"
                break
            elif choice.lower() in ["vedic", "western"]:
                tradition = choice.lower()
                break
            else:
                print("❌ Invalid choice.")
    
    # 3b. LLM Usage
    # Default to False for speed (can enable with --use-llm)
    use_llm_flag = False
    
    # 4. Output Dir
    if not output_dir:
        default_out = "processed_data"
        user_out = input(f"\n[4/4] Output Directory (Default: {default_out}): ").strip()
        output_dir = user_out if user_out else default_out

    # Create output directory
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "-" * 60)
    print(f"✅ Ready to process:")
    print(f"   File:      {input_file}")
    print(f"   Book:      {source_book}")
    print(f"   Tradition: {tradition}")
    print(f"   Output:    {output_dir}")
    print("-" * 60 + "\n")
    
    # Run pipeline
    pipeline = PreprocessingPipeline(
        source_book=source_book,
        tradition=tradition,
        use_llm=use_llm_flag,
        output_dir=output_dir,
    )
    
    result = pipeline.run_full_pipeline(
        input_file,
        skip_embedding=args.skip_embedding,
        skip_vectordb=args.skip_vectordb,
        reset_collection=args.reset_collection,
        start_page=start_page,
        end_page=end_page,
    )
    
    # Save final output
    input_path = Path(input_file)
    final_filename = f"{input_path.stem}_final.json"
    
    if output_dir:
        output_path = Path(output_dir) / final_filename
    else:
        output_path = input_path.parent / final_filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Final output saved to: {output_path}")


if __name__ == "__main__":
    main()
