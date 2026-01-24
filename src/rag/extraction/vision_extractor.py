"""
Vision LLM Extractor using Google Gemini 1.5 Pro.
This module handles the actual extraction of content from page images.
"""

import os
import json
import base64
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

import google.generativeai as genai
from PIL import Image
import numpy as np

from extraction_prompts import (
    SYSTEM_PROMPT,
    PAGE_CLASSIFICATION_PROMPT,
    TEXT_EXTRACTION_PROMPT,
    TABLE_EXTRACTION_PROMPT,
    MIXED_EXTRACTION_PROMPT,
    COMPLEX_TABLE_PROMPT,
    CHART_EXTRACTION_PROMPT,
    TOPIC_CLASSIFICATION_PROMPT,
    get_prompt_for_page_type,
)
from extraction_schemas import (
    PageType,
    ExtractedPage,
    PageMetadata,
    ContentBlock,
    ContentType,
    ExtractedTable,
    VerseBlock,
    ExtractionResult,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExtractionConfig:
    """Configuration for the Vision Extractor"""
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.1  # Low temperature for accurate extraction
    max_output_tokens: int = 8192
    top_p: float = 0.95
    
    # Rate limiting
    requests_per_minute: int = 10
    delay_between_requests: float = 2.0  # seconds
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Output settings
    save_raw_responses: bool = True
    output_dir: str = "./extraction_output"


class VisionExtractor:
    """
    Extracts structured content from astrology book page images using Gemini Vision.
    """
    
    def __init__(self, config: ExtractionConfig = None, credentials_path: str = None):
        """
        Initialize the Vision Extractor.
        
        Args:
            config: Extraction configuration
            credentials_path: Path to Google Cloud credentials JSON (optional if env var set)
        """
        self.config = config or ExtractionConfig()
        
        # Configure Google AI
        self._setup_credentials(credentials_path)
        
        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name=self.config.model_name,
            generation_config=genai.GenerationConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
                top_p=self.config.top_p,
            ),
            system_instruction=SYSTEM_PROMPT,
        )
        
        # Create output directory
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Request tracking for rate limiting
        self._last_request_time = 0
        self._request_count = 0
        
        logger.info(f"VisionExtractor initialized with model: {self.config.model_name}")
    
    def _setup_credentials(self, credentials_path: str = None):
        """Set up Google AI credentials."""
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        
        # Get API key from environment
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        
        if api_key:
            genai.configure(api_key=api_key)
            logger.info("Configured Gemini with API key")
        else:
            # Try to use application default credentials
            logger.info("Using application default credentials for Gemini")
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        if elapsed < self.config.delay_between_requests:
            sleep_time = self.config.delay_between_requests - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
        self._request_count += 1
    
    def _image_to_pil(self, image: np.ndarray) -> Image.Image:
        """Convert numpy array to PIL Image."""
        if isinstance(image, Image.Image):
            return image
        return Image.fromarray(image)
    
    def _call_gemini(self, prompt: str, image: Image.Image, retry_count: int = 0) -> str:
        """
        Call Gemini API with retry logic.
        
        Args:
            prompt: The extraction prompt
            image: PIL Image to process
            retry_count: Current retry attempt
            
        Returns:
            Raw response text from Gemini
        """
        self._rate_limit()
        
        try:
            response = self.model.generate_content([prompt, image])
            
            # Check if response was blocked
            if response.prompt_feedback.block_reason:
                logger.warning(f"Response blocked: {response.prompt_feedback.block_reason}")
                return '{"error": "Response blocked by safety filters"}'
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API error (attempt {retry_count + 1}): {e}")
            
            if retry_count < self.config.max_retries:
                time.sleep(self.config.retry_delay * (retry_count + 1))
                return self._call_gemini(prompt, image, retry_count + 1)
            else:
                raise RuntimeError(f"Failed after {self.config.max_retries} retries: {e}")
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            return {"error": "JSON parse error", "raw": response}
    
    def classify_page(self, image: np.ndarray) -> Tuple[PageType, Dict[str, Any]]:
        """
        Classify the page type and extract basic metadata.
        
        Args:
            image: Page image as numpy array
            
        Returns:
            Tuple of (PageType, metadata dict)
        """
        logger.info("Classifying page type...")
        
        pil_image = self._image_to_pil(image)
        response = self._call_gemini(PAGE_CLASSIFICATION_PROMPT, pil_image)
        result = self._parse_json_response(response)
        
        # Map string to PageType enum
        page_type_str = result.get("page_type", "mixed").lower()
        try:
            page_type = PageType(page_type_str)
        except ValueError:
            page_type = PageType.MIXED
        
        logger.info(f"Page classified as: {page_type.value}")
        return page_type, result
    
    def extract_text_page(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract content from a text-heavy page."""
        logger.info("Extracting text-heavy page...")
        
        pil_image = self._image_to_pil(image)
        response = self._call_gemini(TEXT_EXTRACTION_PROMPT, pil_image)
        return self._parse_json_response(response)
    
    def extract_table_page(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract content from a table-heavy page."""
        logger.info("Extracting table-heavy page...")
        
        pil_image = self._image_to_pil(image)
        response = self._call_gemini(TABLE_EXTRACTION_PROMPT, pil_image)
        return self._parse_json_response(response)
    
    def extract_mixed_page(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract content from a mixed (text + tables) page."""
        logger.info("Extracting mixed page...")
        
        pil_image = self._image_to_pil(image)
        response = self._call_gemini(MIXED_EXTRACTION_PROMPT, pil_image)
        return self._parse_json_response(response)
    
    def extract_complex_table(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract a complex table that needs special handling."""
        logger.info("Extracting complex table...")
        
        pil_image = self._image_to_pil(image)
        response = self._call_gemini(COMPLEX_TABLE_PROMPT, pil_image)
        return self._parse_json_response(response)
    
    def extract_chart(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract an astrological chart/diagram."""
        logger.info("Extracting chart/diagram...")
        
        pil_image = self._image_to_pil(image)
        response = self._call_gemini(CHART_EXTRACTION_PROMPT, pil_image)
        return self._parse_json_response(response)
    
    def extract_page(
        self, 
        image: np.ndarray, 
        page_num: int,
        book_title: str = None,
        chapter_title: str = None,
        force_type: PageType = None,
    ) -> ExtractedPage:
        """
        Extract content from a single page image.
        
        Args:
            image: Page image as numpy array
            page_num: Page number
            book_title: Optional book title for metadata
            chapter_title: Optional chapter title for metadata
            force_type: Force a specific page type (skip classification)
            
        Returns:
            ExtractedPage with structured content
        """
        logger.info(f"Processing page {page_num}...")
        
        # Step 1: Classify page type (or use forced type)
        if force_type:
            page_type = force_type
            classification = {"page_type": force_type.value, "confidence": 1.0}
        else:
            page_type, classification = self.classify_page(image)
        
        # Step 2: Extract content based on type
        extraction_map = {
            PageType.TEXT_HEAVY: self.extract_text_page,
            PageType.TABLE_HEAVY: self.extract_table_page,
            PageType.MIXED: self.extract_mixed_page,
            PageType.CHART: self.extract_chart,
            PageType.TITLE: self.extract_text_page,
            PageType.INDEX: self.extract_text_page,
        }
        
        extractor = extraction_map.get(page_type, self.extract_mixed_page)
        extraction_result = extractor(image)
        
        # Step 3: Build structured output
        metadata = PageMetadata(
            page_number=page_num,
            book_title=book_title or classification.get("book_title"),
            chapter_title=chapter_title or classification.get("chapter_title"),
            chapter_number=classification.get("chapter_number"),
            page_type=page_type,
            has_tables=classification.get("has_tables", False) or "tables" in extraction_result,
            has_charts=classification.get("has_charts", False),
            languages_present=["english", "sanskrit"] if classification.get("has_sanskrit") else ["english"],
            astrology_system="vedic",  # Default for BPHS
        )
        
        # Convert extraction result to content blocks
        content_blocks = self._build_content_blocks(extraction_result, page_type)
        
        # Get raw text for fallback
        raw_text = extraction_result.get("raw_text", "")
        if not raw_text:
            raw_text = self._extract_raw_text(extraction_result)
        
        # Build extraction quality assessment
        quality = extraction_result.get("extraction_quality", "fair")
        confidence_map = {"good": 0.9, "fair": 0.7, "poor": 0.5}
        confidence = confidence_map.get(quality, 0.7)
        
        extracted_page = ExtractedPage(
            metadata=metadata,
            content_blocks=content_blocks,
            raw_text=raw_text,
            extraction_confidence=confidence,
            extraction_notes="; ".join(extraction_result.get("issues", [])),
        )
        
        # Save raw response if configured
        if self.config.save_raw_responses:
            self._save_raw_response(page_num, extraction_result)
        
        logger.info(f"Page {page_num} extracted: {len(content_blocks)} content blocks")
        return extracted_page
    
    def _build_content_blocks(
        self, 
        extraction_result: Dict[str, Any], 
        page_type: PageType
    ) -> List[ContentBlock]:
        """Convert extraction result to ContentBlock list."""
        blocks = []
        sequence = 1
        
        # Handle content_blocks if present (from mixed/text pages)
        if "content_blocks" in extraction_result:
            for block in extraction_result["content_blocks"]:
                content_type = self._map_content_type(block.get("type", "prose"))
                
                # Build text content
                text = block.get("english_text", "") or block.get("text", "")
                sanskrit_text = block.get("sanskrit_text", "")
                
                if sanskrit_text:
                    text = f"{sanskrit_text}\n\n{text}"
                
                # Build verse data if applicable
                verse_data = None
                if content_type in [ContentType.SHLOKA, ContentType.TRANSLATION]:
                    verse_data = VerseBlock(
                        verse_number=block.get("verse_number"),
                        sanskrit_text=sanskrit_text or "",
                        translation=block.get("english_text", ""),
                        notes=block.get("notes"),
                        topic=block.get("topic"),
                    )
                
                # Handle table content
                table_data = None
                if content_type == ContentType.TABLE and "content" in block:
                    table_content = block["content"]
                    table_data = ExtractedTable(
                        title=table_content.get("table_title"),
                        headers=table_content.get("headers", []),
                        rows=table_content.get("rows", []),
                        markdown=table_content.get("markdown", ""),
                        table_type=table_content.get("table_type"),
                    )
                
                blocks.append(ContentBlock(
                    content_type=content_type,
                    text=text,
                    verse_data=verse_data,
                    table_data=table_data,
                    sequence_order=sequence,
                ))
                sequence += 1
        
        # Handle tables from table-heavy pages
        if "tables" in extraction_result:
            for table in extraction_result["tables"]:
                # Add context before table
                if table.get("context_before"):
                    blocks.append(ContentBlock(
                        content_type=ContentType.PROSE,
                        text=table["context_before"],
                        sequence_order=sequence,
                    ))
                    sequence += 1
                
                # Add table
                table_data = ExtractedTable(
                    title=table.get("title"),
                    headers=table.get("headers", []),
                    rows=table.get("rows", []),
                    markdown=table.get("markdown", ""),
                    context=table.get("context_before"),
                    table_type=table.get("table_type"),
                )
                
                blocks.append(ContentBlock(
                    content_type=ContentType.TABLE,
                    text=table.get("markdown", ""),
                    table_data=table_data,
                    sequence_order=sequence,
                ))
                sequence += 1
                
                # Add context after table
                if table.get("context_after"):
                    blocks.append(ContentBlock(
                        content_type=ContentType.PROSE,
                        text=table["context_after"],
                        sequence_order=sequence,
                    ))
                    sequence += 1
        
        return blocks
    
    def _map_content_type(self, type_str: str) -> ContentType:
        """Map string type to ContentType enum."""
        mapping = {
            "heading": ContentType.HEADING,
            "shloka": ContentType.SHLOKA,
            "verse": ContentType.SHLOKA,
            "translation": ContentType.TRANSLATION,
            "notes": ContentType.NOTES,
            "note": ContentType.NOTES,
            "prose": ContentType.PROSE,
            "text": ContentType.PROSE,
            "table": ContentType.TABLE,
            "list": ContentType.LIST,
            "example": ContentType.EXAMPLE,
            "formula": ContentType.FORMULA,
        }
        return mapping.get(type_str.lower(), ContentType.PROSE)
    
    def _extract_raw_text(self, extraction_result: Dict[str, Any]) -> str:
        """Extract raw text from extraction result for fallback."""
        texts = []
        
        # From content blocks
        if "content_blocks" in extraction_result:
            for block in extraction_result["content_blocks"]:
                if block.get("sanskrit_text"):
                    texts.append(block["sanskrit_text"])
                if block.get("english_text"):
                    texts.append(block["english_text"])
                if block.get("text"):
                    texts.append(block["text"])
        
        # From tables
        if "tables" in extraction_result:
            for table in extraction_result["tables"]:
                if table.get("markdown"):
                    texts.append(table["markdown"])
        
        # From other_text
        if extraction_result.get("other_text"):
            texts.append(extraction_result["other_text"])
        
        return "\n\n".join(texts)
    
    def _save_raw_response(self, page_num: int, result: Dict[str, Any]):
        """Save raw extraction response for debugging."""
        output_path = self.output_dir / f"raw_response_page_{page_num:03d}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    def classify_topic(self, content: str) -> Dict[str, Any]:
        """
        Classify the astrological topic of extracted content.
        
        Args:
            content: Extracted text content
            
        Returns:
            Topic classification result
        """
        prompt = TOPIC_CLASSIFICATION_PROMPT.format(content=content[:2000])  # Limit content length
        
        # Use text-only model for this (no image needed)
        response = self.model.generate_content(prompt)
        return self._parse_json_response(response.text)


class BatchExtractor:
    """
    Batch extraction of multiple pages from a PDF.
    """
    
    def __init__(self, extractor: VisionExtractor):
        self.extractor = extractor
    
    def extract_pages(
        self,
        images: List[np.ndarray],
        book_title: str = None,
        start_page: int = 1,
        progress_callback: callable = None,
    ) -> ExtractionResult:
        """
        Extract content from multiple page images.
        
        Args:
            images: List of page images as numpy arrays
            book_title: Book title for metadata
            start_page: Starting page number
            progress_callback: Optional callback for progress updates
            
        Returns:
            ExtractionResult with all pages
        """
        pages = []
        stats = {
            "total_pages": len(images),
            "successful": 0,
            "failed": 0,
            "page_types": {},
            "total_content_blocks": 0,
        }
        
        for i, image in enumerate(images):
            page_num = start_page + i
            
            try:
                logger.info(f"Extracting page {page_num} ({i+1}/{len(images)})...")
                
                extracted_page = self.extractor.extract_page(
                    image=image,
                    page_num=page_num,
                    book_title=book_title,
                )
                
                pages.append(extracted_page)
                stats["successful"] += 1
                stats["total_content_blocks"] += len(extracted_page.content_blocks)
                
                # Track page types
                page_type = extracted_page.metadata.page_type.value
                stats["page_types"][page_type] = stats["page_types"].get(page_type, 0) + 1
                
                if progress_callback:
                    progress_callback(i + 1, len(images), page_num)
                    
            except Exception as e:
                logger.error(f"Failed to extract page {page_num}: {e}")
                stats["failed"] += 1
                
                # Create a minimal failed page entry
                failed_page = ExtractedPage(
                    metadata=PageMetadata(
                        page_number=page_num,
                        page_type=PageType.MIXED,
                    ),
                    content_blocks=[],
                    raw_text="",
                    extraction_confidence=0.0,
                    extraction_notes=f"Extraction failed: {str(e)}",
                )
                pages.append(failed_page)
        
        return ExtractionResult(
            source_file=book_title or "unknown",
            total_pages=len(images),
            pages=pages,
            extraction_stats=stats,
        )


if __name__ == "__main__":
    # Quick test
    config = ExtractionConfig(
        output_dir="./test_output",
        save_raw_responses=True,
    )
    
    extractor = VisionExtractor(config)
    print(f"Extractor initialized: {extractor.config.model_name}")
