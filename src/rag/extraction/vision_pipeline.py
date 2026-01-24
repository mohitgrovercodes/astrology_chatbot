"""
Complete Vision LLM Pipeline for Astrology Text Extraction.

This pipeline:
1. Converts PDF to images
2. Uses Gemini Vision to extract structured content
3. Outputs RAG-ready JSON with rich metadata
4. Supports both automatic and manual processing modes
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

import numpy as np
from pdf2image import convert_from_path
from PIL import Image

from vision_extractor import VisionExtractor, BatchExtractor, ExtractionConfig
from extraction_schemas import (
    PageType,
    ExtractedPage,
    ExtractionResult,
    RAGChunk,
    ContentType,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the Vision Pipeline"""
    # PDF Processing
    pdf_dpi: int = 200  # DPI for PDF to image conversion
    
    # Gemini Settings
    gemini_model: str = "gemini-2.5-flash"
    temperature: float = 0.1
    max_output_tokens: int = 8192
    
    # Rate Limiting
    requests_per_minute: int = 10
    delay_between_requests: float = 3.0  # Gemini rate limits
    
    # Output Settings
    output_dir: str = "./extraction_output"
    save_raw_responses: bool = True
    save_page_images: bool = False  # Save extracted page images
    
    # RAG Chunking Settings
    chunk_strategy: str = "semantic"  # "semantic", "fixed", "hybrid"
    max_chunk_size: int = 1500  # tokens (approximate)
    chunk_overlap: int = 200
    
    # Book Metadata (to be set per-book)
    book_title: str = "Unknown Book"
    book_author: str = "Unknown Author"
    astrology_system: str = "vedic"  # "vedic", "western", "both"


class VisionPipeline:
    """
    Complete pipeline for extracting astrology texts using Vision LLM.
    """
    
    def __init__(self, config: PipelineConfig = None, api_key: str = None):
        """
        Initialize the Vision Pipeline.
        
        Args:
            config: Pipeline configuration
            api_key: Google API key (or set GOOGLE_API_KEY env var)
        """
        self.config = config or PipelineConfig()
        
        # Set API key if provided
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        
        # Create output directory
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the Vision Extractor
        extractor_config = ExtractionConfig(
            model_name=self.config.gemini_model,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            delay_between_requests=self.config.delay_between_requests,
            save_raw_responses=self.config.save_raw_responses,
            output_dir=str(self.output_dir / "raw_responses"),
        )
        
        self.extractor = VisionExtractor(extractor_config)
        self.batch_extractor = BatchExtractor(self.extractor)
        
        logger.info(f"VisionPipeline initialized")
        logger.info(f"Output directory: {self.output_dir}")
    
    def pdf_to_images(
        self, 
        pdf_path: str, 
        start_page: int = None, 
        end_page: int = None
    ) -> Tuple[List[np.ndarray], int]:
        """
        Convert PDF pages to images.
        
        Args:
            pdf_path: Path to PDF file
            start_page: First page to process (1-indexed)
            end_page: Last page to process (1-indexed)
            
        Returns:
            Tuple of (list of images as numpy arrays, actual start page number)
        """
        logger.info(f"Converting PDF to images at {self.config.pdf_dpi} DPI...")
        logger.info(f"PDF: {pdf_path}")
        logger.info(f"Pages: {start_page or 'start'} to {end_page or 'end'}")
        
        images = convert_from_path(
            pdf_path,
            dpi=self.config.pdf_dpi,
            first_page=start_page,
            last_page=end_page,
        )
        
        np_images = [np.array(img) for img in images]
        actual_start = start_page or 1
        
        logger.info(f"Converted {len(np_images)} pages")
        
        # Optionally save page images
        if self.config.save_page_images:
            images_dir = self.output_dir / "page_images"
            images_dir.mkdir(exist_ok=True)
            for i, img in enumerate(images):
                page_num = actual_start + i
                img.save(images_dir / f"page_{page_num:03d}.png")
            logger.info(f"Saved page images to {images_dir}")
        
        return np_images, actual_start
    
    def process_pdf(
        self,
        pdf_path: str,
        start_page: int = None,
        end_page: int = None,
        book_title: str = None,
        progress_callback: callable = None,
    ) -> ExtractionResult:
        """
        Process a PDF file and extract structured content.
        
        Args:
            pdf_path: Path to PDF file
            start_page: First page to process (1-indexed)
            end_page: Last page to process (1-indexed)
            book_title: Override book title from config
            progress_callback: Optional callback(current, total, page_num)
            
        Returns:
            ExtractionResult with all extracted pages
        """
        pdf_path = Path(pdf_path)
        title = book_title or self.config.book_title
        
        logger.info("="*70)
        logger.info("VISION LLM EXTRACTION PIPELINE")
        logger.info("="*70)
        logger.info(f"Book: {title}")
        logger.info(f"PDF: {pdf_path.name}")
        logger.info(f"Model: {self.config.gemini_model}")
        logger.info("="*70)
        
        # Step 1: Convert PDF to images
        images, actual_start = self.pdf_to_images(pdf_path, start_page, end_page)
        
        # Step 2: Extract content from all pages
        logger.info("\n" + "="*70)
        logger.info("EXTRACTING CONTENT WITH VISION LLM")
        logger.info("="*70)
        
        result = self.batch_extractor.extract_pages(
            images=images,
            book_title=title,
            start_page=actual_start,
            progress_callback=progress_callback,
        )
        
        # Update source file
        result.source_file = pdf_path.name
        
        # Step 3: Save results
        self._save_results(result, pdf_path.stem)
        
        # Step 4: Print summary
        self._print_summary(result)
        
        return result
    
    def process_single_page(
        self,
        image: np.ndarray,
        page_num: int,
        book_title: str = None,
        force_type: PageType = None,
    ) -> ExtractedPage:
        """
        Process a single page image.
        
        Args:
            image: Page image as numpy array
            page_num: Page number
            book_title: Book title for metadata
            force_type: Force specific page type (skip classification)
            
        Returns:
            ExtractedPage with structured content
        """
        return self.extractor.extract_page(
            image=image,
            page_num=page_num,
            book_title=book_title or self.config.book_title,
            force_type=force_type,
        )
    
    def _save_results(self, result: ExtractionResult, base_name: str):
        """Save extraction results in multiple formats."""
        
        # 1. Save complete JSON result
        json_path = self.output_dir / f"{base_name}_extraction.json"
        with open(json_path, "w", encoding="utf-8") as f:
            # Convert to dict for JSON serialization
            result_dict = self._result_to_dict(result)
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved JSON: {json_path}")
        
        # 2. Save RAG-ready chunks
        chunks = self.create_rag_chunks(result)
        chunks_path = self.output_dir / f"{base_name}_rag_chunks.json"
        with open(chunks_path, "w", encoding="utf-8") as f:
            chunks_dict = [chunk.model_dump() for chunk in chunks]
            json.dump(chunks_dict, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved RAG chunks: {chunks_path}")
        
        # 3. Save plain text (for reference)
        text_path = self.output_dir / f"{base_name}_text.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(f"# {result.source_file}\n")
            f.write(f"# Extracted: {datetime.now().isoformat()}\n")
            f.write("="*70 + "\n\n")
            
            for page in result.pages:
                f.write(f"\n{'='*70}\n")
                f.write(f"PAGE {page.metadata.page_number}\n")
                f.write(f"Type: {page.metadata.page_type.value}\n")
                f.write(f"{'='*70}\n\n")
                
                for block in page.content_blocks:
                    f.write(f"[{block.content_type.value.upper()}]\n")
                    f.write(block.text)
                    f.write("\n\n")
        logger.info(f"Saved text: {text_path}")
        
        # 4. Save markdown (tables formatted nicely)
        md_path = self.output_dir / f"{base_name}_content.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {result.source_file}\n\n")
            
            for page in result.pages:
                f.write(f"\n---\n\n## Page {page.metadata.page_number}\n\n")
                
                if page.metadata.chapter_title:
                    f.write(f"**Chapter:** {page.metadata.chapter_title}\n\n")
                
                for block in page.content_blocks:
                    if block.content_type == ContentType.TABLE:
                        if block.table_data and block.table_data.title:
                            f.write(f"### {block.table_data.title}\n\n")
                        f.write(block.text + "\n\n")
                    elif block.content_type == ContentType.SHLOKA:
                        f.write(f"**Verse{' ' + block.verse_data.verse_number if block.verse_data and block.verse_data.verse_number else ''}:**\n\n")
                        f.write(f"_{block.text}_\n\n")
                    elif block.content_type == ContentType.HEADING:
                        f.write(f"### {block.text}\n\n")
                    else:
                        f.write(block.text + "\n\n")
        logger.info(f"Saved markdown: {md_path}")
    
    def _result_to_dict(self, result: ExtractionResult) -> Dict[str, Any]:
        """Convert ExtractionResult to JSON-serializable dict."""
        return {
            "source_file": result.source_file,
            "total_pages": result.total_pages,
            "extraction_stats": result.extraction_stats,
            "pages": [
                {
                    "metadata": {
                        "page_number": page.metadata.page_number,
                        "book_title": page.metadata.book_title,
                        "chapter_title": page.metadata.chapter_title,
                        "chapter_number": page.metadata.chapter_number,
                        "section_title": page.metadata.section_title,
                        "page_type": page.metadata.page_type.value,
                        "has_tables": page.metadata.has_tables,
                        "has_charts": page.metadata.has_charts,
                        "languages_present": page.metadata.languages_present,
                        "astrology_system": page.metadata.astrology_system,
                    },
                    "content_blocks": [
                        {
                            "content_type": block.content_type.value,
                            "text": block.text,
                            "sequence_order": block.sequence_order,
                            "verse_data": block.verse_data.model_dump() if block.verse_data else None,
                            "table_data": block.table_data.model_dump() if block.table_data else None,
                        }
                        for block in page.content_blocks
                    ],
                    "raw_text": page.raw_text,
                    "extraction_confidence": page.extraction_confidence,
                    "extraction_notes": page.extraction_notes,
                }
                for page in result.pages
            ],
        }
    
    def create_rag_chunks(self, result: ExtractionResult) -> List[RAGChunk]:
        """
        Create RAG-ready chunks from extraction result.
        
        This implements semantic chunking that respects content boundaries:
        - Verses (shloka + translation) stay together
        - Tables stay intact
        - Prose is chunked by paragraphs
        """
        chunks = []
        chunk_counter = 0
        
        for page in result.pages:
            # Group related content blocks
            current_group = []
            current_group_type = None
            
            for block in page.content_blocks:
                # Decide if this block starts a new chunk
                should_start_new = self._should_start_new_chunk(
                    block.content_type, 
                    current_group_type,
                    current_group,
                )
                
                if should_start_new and current_group:
                    # Create chunk from current group
                    chunk = self._create_chunk(
                        blocks=current_group,
                        page=page,
                        chunk_id=f"chunk_{chunk_counter:05d}",
                        source_file=result.source_file,
                    )
                    if chunk:
                        chunks.append(chunk)
                        chunk_counter += 1
                    current_group = []
                
                current_group.append(block)
                current_group_type = block.content_type
            
            # Don't forget the last group
            if current_group:
                chunk = self._create_chunk(
                    blocks=current_group,
                    page=page,
                    chunk_id=f"chunk_{chunk_counter:05d}",
                    source_file=result.source_file,
                )
                if chunk:
                    chunks.append(chunk)
                    chunk_counter += 1
        
        return chunks
    
    def _should_start_new_chunk(
        self, 
        current_type: ContentType, 
        previous_type: ContentType,
        current_group: List,
    ) -> bool:
        """Determine if we should start a new chunk."""
        
        # Always start new chunk for these types
        standalone_types = {
            ContentType.TABLE,
            ContentType.HEADING,
        }
        
        if current_type in standalone_types:
            return True
        
        # Keep verse + translation together
        if previous_type == ContentType.SHLOKA and current_type == ContentType.TRANSLATION:
            return False
        
        # Keep notes with preceding translation
        if previous_type == ContentType.TRANSLATION and current_type == ContentType.NOTES:
            return False
        
        # Check size limit (approximate)
        total_text = sum(len(b.text) for b in current_group)
        if total_text > self.config.max_chunk_size * 4:  # ~4 chars per token
            return True
        
        return False
    
    def _create_chunk(
        self,
        blocks: List,
        page: ExtractedPage,
        chunk_id: str,
        source_file: str,
    ) -> Optional[RAGChunk]:
        """Create a RAGChunk from a group of content blocks."""
        
        if not blocks:
            return None
        
        # Combine text from blocks
        texts = []
        for block in blocks:
            if block.content_type == ContentType.SHLOKA and block.verse_data:
                # Format verse nicely
                if block.verse_data.verse_number:
                    texts.append(f"[Verse {block.verse_data.verse_number}]")
                texts.append(block.verse_data.sanskrit_text)
            elif block.content_type == ContentType.TABLE and block.table_data:
                if block.table_data.title:
                    texts.append(f"Table: {block.table_data.title}")
                texts.append(block.table_data.markdown)
            else:
                texts.append(block.text)
        
        combined_text = "\n\n".join(filter(None, texts))
        
        if not combined_text.strip():
            return None
        
        # Determine content type for the chunk
        primary_type = blocks[0].content_type.value
        if any(b.content_type == ContentType.TABLE for b in blocks):
            primary_type = "table"
        elif any(b.content_type == ContentType.SHLOKA for b in blocks):
            primary_type = "verse"
        
        # Check for Sanskrit
        has_sanskrit = any(
            b.verse_data and b.verse_data.sanskrit_text
            for b in blocks
        )
        
        # Get topic from verse data if available
        topic = None
        verse_numbers = None
        for block in blocks:
            if block.verse_data:
                if block.verse_data.topic:
                    topic = block.verse_data.topic
                if block.verse_data.verse_number:
                    verse_numbers = block.verse_data.verse_number
        
        # Get topic from table data
        for block in blocks:
            if block.table_data and block.table_data.table_type:
                topic = block.table_data.table_type
        
        return RAGChunk(
            chunk_id=chunk_id,
            text=combined_text,
            metadata={
                "page_type": page.metadata.page_type.value,
                "has_tables": page.metadata.has_tables,
                "languages": page.metadata.languages_present,
                "extraction_confidence": page.extraction_confidence,
            },
            source_book=page.metadata.book_title or source_file,
            source_chapter=page.metadata.chapter_title,
            source_page=page.metadata.page_number,
            content_type=primary_type,
            topic=topic,
            verse_numbers=verse_numbers,
            has_sanskrit=has_sanskrit,
        )
    
    def _print_summary(self, result: ExtractionResult):
        """Print extraction summary."""
        stats = result.extraction_stats
        
        print("\n" + "="*70)
        print("EXTRACTION COMPLETE")
        print("="*70)
        print(f"Source: {result.source_file}")
        print(f"Total pages: {result.total_pages}")
        print(f"Successful: {stats.get('successful', 0)}")
        print(f"Failed: {stats.get('failed', 0)}")
        print(f"Total content blocks: {stats.get('total_content_blocks', 0)}")
        print("\nPage types:")
        for ptype, count in stats.get("page_types", {}).items():
            print(f"  {ptype}: {count}")
        print(f"\nOutput directory: {self.output_dir}")
        print("="*70)


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command line interface for the Vision Pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract structured content from astrology PDFs using Vision LLM"
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--start", type=int, help="Start page (1-indexed)")
    parser.add_argument("--end", type=int, help="End page (1-indexed)")
    parser.add_argument("--title", help="Book title")
    parser.add_argument("--output", default="./extraction_output", help="Output directory")
    parser.add_argument("--dpi", type=int, default=200, help="PDF rendering DPI")
    parser.add_argument("--api-key", help="Google API key (or set GOOGLE_API_KEY env)")
    
    args = parser.parse_args()
    
    # Create configuration
    config = PipelineConfig(
        output_dir=args.output,
        pdf_dpi=args.dpi,
        book_title=args.title or Path(args.pdf_path).stem,
    )
    
    # Initialize pipeline
    pipeline = VisionPipeline(config, api_key=args.api_key)
    
    # Process PDF
    result = pipeline.process_pdf(
        pdf_path=args.pdf_path,
        start_page=args.start,
        end_page=args.end,
        book_title=args.title,
    )
    
    print(f"\nExtraction complete. Check {args.output} for results.")


if __name__ == "__main__":
    main()
