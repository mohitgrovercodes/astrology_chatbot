# src/rag/extraction/vision_extractor.py
# src\rag\extraction\vision_extractor.py
"""
Vision LLM Extractor using Google Gemini 2.5 Flash/Lite/Pro
This module handles the actual extraction of content from page images.
"""

import os
import json
import base64
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Filter warnings from deprecated google.generativeai
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai
from PIL import Image
import numpy as np

# Set Google Application Credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_credentials.json'

# Vertex AI imports
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part, FinishReason
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False

from .extraction_prompts import (
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
from .extraction_schemas import (
    PageType,
    ExtractedPage,
    PageMetadata,
    ContentBlock,
    ContentType,
    ExtractedTable,
    VerseBlock,
    ExtractionResult,
    ConfidenceMetadata,
    RetryMetadata,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import cost tracking
try:
    from src.utils.cost_tracking import CostTrackingWrapper
    COST_TRACKING_AVAILABLE = True
except ImportError:
    COST_TRACKING_AVAILABLE = False
    logger.warning("Cost tracking not available")


@dataclass
class ExtractionConfig:
    """Configuration for VisionExtractor."""
    # Model configuration - Hybrid strategy with two-tier fallback
    primary_model: str = "gemini-2.5-flash-lite"  # Cost-effective for initial extraction
    upgrade_model: str = "gemini-2.5-pro"        # Higher quality for low-confidence pages
    confidence_threshold: float = 0.90 # Retry with upgrade_model if confidence < this
    enable_auto_upgrade: bool = True  # Enable automatic model upgrading
    
    # Hybrid Strategy: Use different models based on page type
    enable_hybrid_strategy: bool = True  # Use Flash-Lite for text_heavy, Pro for table_heavy
    hybrid_table_model: str = "gemini-2.5-pro"  # Model for table-heavy pages
    
    # Content Quality Validation
    enable_content_validation: bool = True  # Validate content blocks and adjust confidence
    
    # GCP Vertex AI Configuration
    use_vertex_ai: bool = False  # Enable to use Vertex AI instead of AI Studio
    project_id: Optional[str] = None
    location: Optional[str] = "us-central1"
    
    # Legacy model name (for backwards compatibility)
    model_name: str = field(default="", init=False)
    
    def __post_init__(self):
        # Set model_name to primary_model for backwards compatibility
        if not self.model_name:
            self.model_name = self.primary_model
            
    # Generation settings
    temperature: float = 0.1  # Low temperature for accurate extraction
    max_output_tokens: int = 8192
    top_p: float = 0.95
    
    # Rate limiting
    requests_per_minute: int = 10
    delay_between_requests: float = 3.5  # Increased from 2.0 to prevent 429 errors
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Parallel processing settings
    max_workers: int = 4  # Number of concurrent extraction workers (reduced from 5)
    enable_parallel: bool = True  # Enable parallel processing for batch extraction
    
    # Checkpoint settings
    enable_checkpoints: bool = True  # Save progress checkpoints
    checkpoint_interval: int = 10  # Save checkpoint every N pages
    checkpoint_dir: str = "./extraction_checkpoints"  # Directory for checkpoint files
    
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
        
        # Configure Google AI (either Vertex or AI Studio)
        self._setup_credentials(credentials_path)
        
        # Initialize the model
        self.model = self._create_model(self.config.model_name)
        
        # Create output directory
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Request tracking for rate limiting
        self._last_request_time = 0
        self._request_count = 0
        
        # Cost tracking
        if COST_TRACKING_AVAILABLE:
            self.cost_tracker = CostTrackingWrapper(
                model_name=self.config.primary_model,
                model_type="vision"
            )
            # Log provider type
            provider = "vertex_ai" if self.config.use_vertex_ai else "ai_studio"
            logger.info(f"Cost logging authorized for provider: {provider}")
        else:
            self.cost_tracker = None
        
        logger.info(f"VisionExtractor initialized with model: {self.config.model_name}")
    
    def _setup_credentials(self, credentials_path: str = None):
        """Set up Google AI credentials (Vertex AI or AI Studio)."""
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
        if self.config.use_vertex_ai:
            if not VERTEX_AI_AVAILABLE:
                raise ImportError(
                    "Vertex AI is requested but 'google-cloud-aiplatform' is not installed. "
                    "Install it with: pip install google-cloud-aiplatform"
                )
            
            # Check for Project ID
            project_id = self.config.project_id
            
            # Try to get from credentials file if not provided
            if not project_id and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                try:
                    with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], 'r') as f:
                        creds = json.load(f)
                        project_id = creds.get("project_id")
                except Exception as e:
                    logger.warning(f"Could not read project_id from credentials file: {e}")
            
            if not project_id:
                raise ValueError("project_id must be provided for Vertex AI")
                
            logger.info(f"Initializing Vertex AI (project={project_id}, location={self.config.location})")
            vertexai.init(project=project_id, location=self.config.location)
            
        else:
            # Fallback to AI Studio (original behavior)
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            
            if api_key:
                genai.configure(api_key=api_key)
                logger.info("Configured Gemini with API key (AI Studio)")
            else:
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
    
    def _create_model(self, model_name: str):
        """Create a GenerativeModel instance (Vertex AI or AI Studio)."""
        # Clean model name for Vertex AI (remove 'models/' prefix if present)
        if self.config.use_vertex_ai:
            vertex_model_name = model_name.replace("models/", "")
            return GenerativeModel(
                model_name=vertex_model_name,
                generation_config={
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_output_tokens,
                    "top_p": self.config.top_p,
                },
                system_instruction=[SYSTEM_PROMPT]
            )
        else:
            return genai.GenerativeModel(
                model_name=model_name,
                generation_config=genai.GenerationConfig(
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_output_tokens,
                    top_p=self.config.top_p,
                ),
                system_instruction=SYSTEM_PROMPT,
            )
    
    def _parse_confidence(self, extraction_result: Dict[str, Any]) -> Optional[ConfidenceMetadata]:
        """Parse confidence metadata from extraction result.
        
        Args:
            extraction_result: JSON response from LLM extraction
            
        Returns:
            ConfidenceMetadata if confidence data present, else None
        """
        confidence_data = extraction_result.get("confidence")
        
        if not confidence_data:
            # Fallback: derive from legacy extraction_quality field
            quality = extraction_result.get("extraction_quality", "fair")
            quality_map = {"good": 0.9, "fair": 0.7, "poor": 0.5}
            return ConfidenceMetadata(
                overall_score=quality_map.get(quality, 0.7),
                criteria={},
                reasoning=f"Derived from extraction_quality: {quality}",
                flags=["legacy_quality_only"]
            )
        
        try:
            score = float(confidence_data.get("overall_score", 0.7))
            
            # Only include reasoning if confidence is low (< threshold)
            # This saves storage and focuses debugging on problem pages
            reasoning = None
            threshold = getattr(self.config, "confidence_threshold", 0.9)
            if score < threshold:
                reasoning = confidence_data.get("reasoning")
            
            return ConfidenceMetadata(
                overall_score=score,
                criteria=confidence_data.get("criteria", {}),
                reasoning=reasoning,
                flags=confidence_data.get("flags", [])
            )
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to parse confidence data: {e}")
            return None
    
    def _validate_content_quality(
        self, 
        extraction_result: Dict[str, Any], 
        confidence_metadata: Optional[ConfidenceMetadata]
    ) -> Optional[ConfidenceMetadata]:
        """
        Validate content quality and adjust confidence if needed.
        Detects empty blocks and prevents false-positive high confidence scores.
        
        Args:
            extraction_result: JSON response from LLM
            confidence_metadata: Parsed confidence metadata
            
        Returns:
            Updated ConfidenceMetadata with adjusted score if validation fails
        """
        if not self.config.enable_content_validation or not confidence_metadata:
            return confidence_metadata
        
        # Check for empty content blocks
        content_blocks = extraction_result.get("content_blocks", [])
        
        if not content_blocks:
            # No blocks at all - critical failure
            logger.warning("Content validation failed: No content blocks found")
            return ConfidenceMetadata(
                overall_score=0.2,
                criteria=confidence_metadata.criteria if confidence_metadata else {},
                reasoning="VALIDATION OVERRIDE: No content blocks extracted",
                flags=["empty_extraction", "validation_override"]
            )
        
        # Count empty blocks
        empty_blocks = 0
        total_text_length = 0
        
        for block in content_blocks:
            # Check various text fields
            text = (
                block.get("text", "") or 
                block.get("english_text", "") or 
                block.get("sanskrit_text", "")
            )
            
            # For table blocks, check if table data exists
            if block.get("type") == "table":
                table_content = block.get("content", {})
                if table_content.get("rows") or table_content.get("markdown"):
                    # Table has data, count as non-empty
                    total_text_length += 100  # Arbitrary weight for tables
                    continue
            
            text_len = len(text.strip())
            total_text_length += text_len
            
            if text_len == 0:
                empty_blocks += 1
        
        # Calculate empty ratio
        empty_ratio = empty_blocks / len(content_blocks) if content_blocks else 1.0
        
        # Override confidence if too many empty blocks
        if empty_ratio > 0.5:  # More than 50% empty
            logger.warning(
                f"Content validation failed: {empty_blocks}/{len(content_blocks)} blocks empty "
                f"({empty_ratio*100:.1f}%)"
            )
            
            # Severely penalize confidence
            adjusted_score = min(confidence_metadata.overall_score, 0.4)
            
            return ConfidenceMetadata(
                overall_score=adjusted_score,
                criteria=confidence_metadata.criteria,
                reasoning=f"VALIDATION OVERRIDE: {empty_ratio*100:.0f}% empty blocks. " + 
                         (confidence_metadata.reasoning or ""),
                flags=confidence_metadata.flags + ["high_empty_ratio", "validation_override"]
            )
        
        # Check for garbage/replacement characters
        garbage_chars = 0
        replacement_char = "\ufffd"  # unicode replacement character
        
        combined_text = ""
        for block in content_blocks:
            text = (block.get("text", "") or block.get("english_text", "") or block.get("sanskrit_text", ""))
            combined_text += text
            garbage_chars += text.count(replacement_char)
            
        # Check for high density of garbage (allow some replacement chars, but not many)
        if len(combined_text) > 20:
            # Check for replacement character density
            garbage_ratio = garbage_chars / len(combined_text)
            if garbage_ratio > 0.15:  # RELAXED: > 15% replacement chars is definitely bad
                logger.warning(
                    f"Content validation failed: High garbage density ({garbage_ratio*100:.1f}%)"
                )
                return ConfidenceMetadata(
                    overall_score=0.1,  # Force retry
                    criteria=confidence_metadata.criteria,
                    reasoning=f"VALIDATION OVERRIDE: High garbage density detected ({garbage_ratio*100:.1f}%)",
                    flags=confidence_metadata.flags + ["garbage_detected", "validation_override"]
                )
                
            # Check for specific garbage patterns often seen in bad OCR
            # e.g., " .  < " sequences
            # NOTE: Use explicit patterns, avoid empty strings or common whitespace
            garbage_patterns = [" . <", ". <", "< .", " .  <"]
            pattern_matches = sum(combined_text.count(p) for p in garbage_patterns)
            if pattern_matches > 5:  # Strict threshold for specific garbage
                 logger.warning(
                    f"Content validation failed: High count of garbage patterns ({pattern_matches})"
                )
                 return ConfidenceMetadata(
                    overall_score=0.1,  # Force retry
                    criteria=confidence_metadata.criteria,
                    reasoning=f"VALIDATION OVERRIDE: detected {pattern_matches} garbage patterns",
                    flags=confidence_metadata.flags + ["garbage_patterns_detected", "validation_override"]
                )

        # Check for suspiciously low total text
        if total_text_length < 100 and confidence_metadata.overall_score > 0.7:
            logger.warning(
                f"Content validation warning: Only {total_text_length} chars extracted "
                f"but confidence is {confidence_metadata.overall_score:.2f}"
            )
            
            adjusted_score = min(confidence_metadata.overall_score, 0.6)
            
            return ConfidenceMetadata(
                overall_score=adjusted_score,
                criteria=confidence_metadata.criteria,
                reasoning=f"VALIDATION OVERRIDE: Low text volume ({total_text_length} chars). " +
                         (confidence_metadata.reasoning or ""),
                flags=confidence_metadata.flags + ["low_text_volume", "validation_override"]
            )
        
        # Validation passed
        return confidence_metadata
    
    def _call_gemini(self, prompt: str, image: Image.Image, retry_count: int = 0) -> str:
        """
        Call Gemini API (Vertex AI or AI Studio) with optimized retry logic.
        
        Args:
            prompt: Prompt text
            image: PIL Image
            retry_count: Current retry attempt
            
        Returns:
            Response text from Gemini
        """
        # Apply rate limiting
        self._rate_limit()
        
        try:
            # Prepare content
            if self.config.use_vertex_ai:
                # Vertex AI requires Part objects for images
                import io
                from vertexai.generative_models import Part
                
                # Convert PIL to bytes
                img_byte_arr = io.BytesIO()
                # Ensure we're saving as JPEG
                image.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()
                
                image_part = Part.from_data(img_bytes, mime_type="image/jpeg")
                content = [prompt, image_part]
                
                # Vertex AI call
                response = self.model.generate_content(content)
            else:
                # AI Studio accepts PIL images directly
                content = [prompt, image]
                
                # AI Studio call
                response = self.model.generate_content(
                    content,
                    request_options={"timeout": 120}  # 2 minute timeout
                )
            
            # Track cost if available
            if self.cost_tracker and hasattr(response, 'usage_metadata'):
                self.cost_tracker.log_manual(
                    input_tokens=response.usage_metadata.prompt_token_count,
                    output_tokens=response.usage_metadata.candidates_token_count,
                    operation="vision_extraction"
                )
            
            # Check for block reasons (handling library differences)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                    logger.warning(f"Response blocked: {response.prompt_feedback.block_reason}")
                    return '{"error": "Response blocked by safety filters", "extraction_quality": "poor", "issues": ["safety_filter_block"]}'
            
            return response.text
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Categorize errors - only retry transient errors
            is_retryable = any([
                "timeout" in error_str,
                "rate limit" in error_str,
                "503" in error_str,
                "429" in error_str,
                "connection" in error_str,
                "temporary" in error_str,
                "quota" in error_str, # Quota exceeded might be retryable after backoff
                "resource exhausted" in error_str, 
            ])
            
            # Don't retry non-transient errors (saves API calls)
            if not is_retryable:
                logger.error(f"Non-retryable error: {e}")
                raise RuntimeError(f"Gemini API error (non-retryable): {e}")
            
            # Check retry limit for transient errors
            if retry_count < self.config.max_retries:
                # Exponential backoff: 5s, 10s, 20s
                wait_time = self.config.retry_delay * (2 ** retry_count)
                logger.warning(f"Retryable error (attempt {retry_count + 1}): {e}")
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                return self._call_gemini(prompt, image, retry_count + 1)
            else:
                logger.error(f"Max retries ({self.config.max_retries}) exceeded")
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
        Extract content from a single page image with two-tier model strategy.
        
        Uses gemini-flash-lite-latest first (cost-effective), then retries with
        gemini-2.5-pro if confidence score is below threshold.
        
        Args:
            image: Page image as numpy array
            page_num: Page number
            book_title: Optional book title for metadata
            chapter_title: Optional chapter title for metadata
            force_type: Force a specific page type (skip classification)
            
        Returns:
            ExtractedPage with structured content and confidence metadata
        """
        logger.info(f"Processing page {page_num}...")
        
        # Step 1: Classify page type (or use forced type)
        if force_type:
            page_type = force_type
            classification = {"page_type": force_type.value, "confidence": 1.0}
        else:
            page_type, classification = self.classify_page(image)
        
        # Step 2: Extract content with primary model (cost-effective)
        extraction_result, used_model = self._extract_with_two_tier(
            image, page_type, page_num
        )
        
        # Step 3: Parse confidence from extraction result
        confidence_metadata = self._parse_confidence(extraction_result)
        
        # Step 3.5: Validate content quality and adjust confidence if needed
        confidence_metadata = self._validate_content_quality(extraction_result, confidence_metadata)
        
        # Check if extraction has errors (blocked, failed, etc.)
        has_errors = extraction_result.get("error") or "safety_filter_block" in extraction_result.get("issues", [])
        
        # Step 4: Check if we need to retry with upgraded model
        # Don't retry if: has errors, already used upgrade model, or confidence is acceptable
        retry_metadata = None
        if (
            self.config.enable_auto_upgrade 
            and confidence_metadata 
            and confidence_metadata.overall_score < self.config.confidence_threshold
            and used_model != self.config.upgrade_model
            and not has_errors  # NEW: Skip retry for error responses (saves API calls)
        ):
            logger.warning(
                f"Page {page_num}: Low confidence {confidence_metadata.overall_score:.2f}, "
                f"retrying with {self.config.upgrade_model}"
            )
            
            initial_confidence = confidence_metadata.overall_score
            
            # Retry with upgraded model
            extraction_result, used_model = self._extract_with_two_tier(
                image, page_type, page_num, use_upgrade_model=True
            )
            
            # Re-parse confidence from upgraded extraction
            confidence_metadata = self._parse_confidence(extraction_result)
            
            # Create retry metadata
            retry_metadata = RetryMetadata(
                initial_model=self.config.primary_model,
                retry_model=self.config.upgrade_model,
                initial_confidence=initial_confidence,
                retry_reason=f"Confidence below threshold ({self.config.confidence_threshold})",
                retry_count=1
            )
            
            # Log improvement
            if confidence_metadata:
                logger.info(
                    f"[OK] Page {page_num} upgraded: confidence improved "
                    f"{initial_confidence:.2f} -> {confidence_metadata.overall_score:.2f}"
                )
        else:
            # No retry needed
            retry_metadata = RetryMetadata(
                initial_model=used_model,
                retry_count=0
            )
        
        # Step 5: Build structured output
        extracted_page = self._create_extracted_page_object(
            page_num, extraction_result, page_type, used_model,
            classification, book_title, chapter_title, confidence_metadata,
            retry_metadata
        )
        
        # Save final formatted response (Consolidated)
        if self.config.save_raw_responses:
            # Save as the definitive JSON for this page
            self._save_formatted_json(page_num, extracted_page, suffix="")
        
        logger.info(
            f"Page {page_num} extracted: {len(extracted_page.content_blocks)} content blocks, "
            f"confidence: {extracted_page.extraction_confidence:.2f}, model: {used_model}"
        )
        return extracted_page

    def _create_extracted_page_object(
        self,
        page_num: int,
        extraction_result: Dict[str, Any],
        page_type: PageType,
        used_model: str,
        classification: Dict[str, Any],
        book_title: Optional[str] = None,
        chapter_title: Optional[str] = None,
        confidence_metadata: Optional[ConfidenceMetadata] = None,
        retry_metadata: Optional[RetryMetadata] = None
    ) -> ExtractedPage:
        """Helper to build the ExtractedPage object."""
        
        metadata = PageMetadata(
            page_number=page_num,
            book_title=book_title or classification.get("book_title"),
            chapter_title=chapter_title or classification.get("chapter_title"),
            chapter_number=classification.get("chapter_number"),
            page_type=page_type,
            has_tables=classification.get("has_tables", False) or "tables" in extraction_result,
            has_charts=classification.get("has_charts", False),
            languages_present=["english", "sanskrit"] if classification.get("has_sanskrit") else ["english"],
            astrology_system="vedic",
        )
        
        # Convert extraction result to content blocks
        content_blocks = self._build_content_blocks(extraction_result, page_type)
        
        # Get raw text for fallback
        raw_text = extraction_result.get("raw_text", "")
        if not raw_text:
            raw_text = self._extract_raw_text(extraction_result)
        
        # Build extraction quality assessment
        extraction_confidence = confidence_metadata.overall_score if confidence_metadata else 0.7
        
        return ExtractedPage(
            metadata=metadata,
            content_blocks=content_blocks,
            raw_text=raw_text,
            extraction_confidence=extraction_confidence,
            extraction_notes="; ".join(extraction_result.get("issues", [])),
            confidence=confidence_metadata,
            retry_metadata=retry_metadata,
        )

    def _save_formatted_json(self, page_num: int, page_obj: ExtractedPage, suffix: str = ""):
        """Save the formatted ExtractedPage object as JSON."""
        output_path = self.output_dir / f"raw_response_page_{page_num:03d}{suffix}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            # Use model_dump if using Pydantic v2
            data = page_obj.model_dump() if hasattr(page_obj, 'model_dump') else page_obj.dict()
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _extract_with_two_tier(
        self,
        image: np.ndarray,
        page_type: PageType,
        page_num: int,
        use_upgrade_model: bool = False
    ) -> tuple[Dict[str, Any], str]:
        """
        Extract content using hybrid strategy or two-tier model selection.
        
        Hybrid Strategy:
        - Use Flash-Lite for text_heavy pages (faster, prose-based)
        - Use Flash for mixed/table_heavy pages (better table structure)
        - Fall back to Pro model if confidence is low
        
        Args:
            image: Page image
            page_type: Classified page type
            page_num: Page number for logging
            use_upgrade_model: If True, use upgrade model instead of primary
            
        Returns:
            Tuple of (extraction_result dict, model_name used)
        """
        # Select model based on page type (Strict Rule)
        if use_upgrade_model:
            model_name = self.config.upgrade_model
        elif page_type in [PageType.TABLE_HEAVY, PageType.MIXED, PageType.CHART]:
            # Use Flash for better table/structure understanding
            model_name = self.config.hybrid_table_model
            logger.info(f"[HYBRID] Strict Rule: Using {model_name} for {page_type.value} page")
        else:
            # Use Flash-Lite for text-heavy pages (cost optimized)
            model_name = self.config.primary_model
            logger.info(f"[HYBRID] Strict Rule: Using {model_name} for {page_type.value} page")
        
        # Temporarily switch model
        original_model = self.model
        self.model = self._create_model(model_name)
        
        try:
            logger.debug(f"Extracting page {page_num} with model: {model_name}")
            
            # Use existing extraction methods based on page type
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
            
            return extraction_result, model_name
            
        finally:
            # Restore original model
            self.model = original_model
    
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
    
    def _save_raw_response(self, page_num: int, result: Dict[str, Any], suffix: str = ""):
        """Save raw extraction response for debugging."""
        output_path = self.output_dir / f"raw_response_page_{page_num:03d}{suffix}.json"
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
    
    def get_extraction_summary(self, pages: list) -> Dict[str, Any]:
        """
        Generate summary statistics for a batch of extracted pages.
        
        Args:
            pages: List of ExtractedPage objects
            
        Returns:
            Summary dict with confidence and upgrade statistics
        """
        if not pages:
            return {"total_pages": 0}
        
        confidences = []
        upgrades = []
        
        for page in pages:
            if page.confidence:
                confidences.append(page.confidence.overall_score)
            elif page.extraction_confidence:
                confidences.append(page.extraction_confidence)
            
            if page.retry_metadata and page.retry_metadata.retry_count > 0:
                upgrades.append(page)
        
        summary = {
            "total_pages": len(pages),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
            "min_confidence": min(confidences) if confidences else None,
            "max_confidence": max(confidences) if confidences else None,
            "low_confidence_count": sum(1 for c in confidences if c < 0.8),
            "upgrade_count": len(upgrades),
            "upgrade_rate": f"{len(upgrades) / len(pages) * 100:.1f}%" if pages else "0%",
        }
        
        # Estimate cost savings
        if pages:
            non_upgraded = len(pages) - len(upgrades)
            # Assume flash-lite is ~10x cheaper than pro
            cost_all_pro = len(pages)  # 100% cost
            actual_cost = (non_upgraded * 0.1) + (len(upgrades) * 1.1)  # flash + retry
            savings = ((cost_all_pro - actual_cost) / cost_all_pro * 100) if len(pages) > 0 else 0
            summary["estimated_cost_savings"] = f"{savings:.1f}%"
        
        return summary


class BatchExtractor:
    """
    Batch extraction of multiple pages from a PDF.
    """
    
    def __init__(self, extractor: VisionExtractor):
        self.extractor = extractor
        self.checkpoint_dir = Path(extractor.config.checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_checkpoint_path(self, book_title: str, start_page: int, total_pages: int) -> Path:
        """Generate checkpoint file path."""
        safe_title = "".join(c for c in (book_title or "unknown") if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
        filename = f"{safe_title}_p{start_page}-{start_page + total_pages - 1}_checkpoint.json"
        return self.checkpoint_dir / filename
    
    def _save_checkpoint(
        self, 
        checkpoint_path: Path, 
        pages: List[ExtractedPage], 
        stats: Dict,
        book_title: str,
        start_page: int
    ):
        """Save extraction checkpoint to disk."""
        try:
            checkpoint_data = {
                "book_title": book_title,
                "start_page": start_page,
                "total_pages_expected": stats["total_pages"],
                "pages_completed": len(pages),
                "stats": stats,
                "pages": [
                    {
                        "page_number": p.metadata.page_number,
                        "page_type": p.metadata.page_type.value,
                        "extraction_confidence": p.extraction_confidence,
                        "content_blocks_count": len(p.content_blocks),
                        # Store full page data for resume
                        "metadata": p.metadata.dict(),
                        "content_blocks": [b.dict() for b in p.content_blocks],
                        "raw_text": p.raw_text,
                        "extraction_notes": p.extraction_notes,
                        "confidence": p.confidence.dict() if p.confidence else None,
                        "retry_metadata": p.retry_metadata.dict() if p.retry_metadata else None,
                    }
                    for p in pages
                ],
                "timestamp": time.time(),
            }
            
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[SAVE] Checkpoint saved: {len(pages)}/{stats['total_pages']} pages")
            
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def _load_checkpoint(self, checkpoint_path: Path) -> Optional[Dict]:
        """Load extraction checkpoint from disk."""
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            logger.info(f"📂 Checkpoint found: {checkpoint_data['pages_completed']}/{checkpoint_data['total_pages_expected']} pages completed")
            return checkpoint_data
            
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return None
    
    def _reconstruct_page(self, page_data: Dict) -> ExtractedPage:
        """Reconstruct ExtractedPage from checkpoint data."""
        from .extraction_schemas import PageMetadata, ContentBlock, ConfidenceMetadata, RetryMetadata
        
        # Reconstruct metadata
        metadata = PageMetadata(**page_data["metadata"])
        
        # Reconstruct content blocks
        content_blocks = [ContentBlock(**b) for b in page_data["content_blocks"]]
        
        # Reconstruct confidence and retry metadata
        confidence = ConfidenceMetadata(**page_data["confidence"]) if page_data.get("confidence") else None
        retry_metadata = RetryMetadata(**page_data["retry_metadata"]) if page_data.get("retry_metadata") else None
        
        return ExtractedPage(
            metadata=metadata,
            content_blocks=content_blocks,
            raw_text=page_data.get("raw_text", ""),
            extraction_confidence=page_data.get("extraction_confidence", 0.7),
            extraction_notes=page_data.get("extraction_notes"),
            confidence=confidence,
            retry_metadata=retry_metadata,
        )
    
    def extract_pages(
        self,
        images: List[np.ndarray],
        book_title: str = None,
        start_page: int = 1,
        progress_callback: callable = None,
        resume_from_checkpoint: bool = True,  # NEW: Enable checkpoint resume
    ) -> ExtractionResult:
        """
        Extract content from multiple page images.
        
        Args:
            images: List of page images as numpy arrays
            book_title: Book title for metadata
            start_page: Starting page number
            progress_callback: Optional callback for progress updates
            resume_from_checkpoint: If True, resume from saved checkpoint if available
            
        Returns:
            ExtractionResult with all pages
        """
        # Initialize stats
        pages = []
        stats = {
            "total_pages": len(images),
            "successful": 0,
            "failed": 0,
            "page_types": {},
            "total_content_blocks": 0,
            # Confidence tracking
            "confidence_scores": [],
            "upgrades": 0,
            "low_confidence_pages": [],
        }
        
        # Check for existing checkpoint
        checkpoint_path = None
        checkpoint_data = None
        skip_pages = set()
        
        if self.extractor.config.enable_checkpoints and resume_from_checkpoint:
            checkpoint_path = self._get_checkpoint_path(book_title, start_page, len(images))
            checkpoint_data = self._load_checkpoint(checkpoint_path)
            
            if checkpoint_data:
                logger.info(f"🔄 Resuming from checkpoint...")
                
                # Reconstruct already-processed pages
                for page_data in checkpoint_data["pages"]:
                    page = self._reconstruct_page(page_data)
                    pages.append(page)
                    skip_pages.add(page.metadata.page_number)
                    self._update_stats(stats, page, page.metadata.page_number)
                
                logger.info(f"[OK] Loaded {len(pages)} pages from checkpoint")
                logger.info(f"⏭️  Skipping pages: {sorted(skip_pages)}")
        
        # Determine if we should use parallel processing
        use_parallel = (
            self.extractor.config.enable_parallel 
            and len(images) > 1 
            and self.extractor.config.max_workers > 1
        )
        
        if use_parallel:
            logger.info(f"Using parallel processing with {self.extractor.config.max_workers} workers")
            new_pages = self._extract_parallel(images, book_title, start_page, stats, progress_callback, skip_pages)
        else:
            logger.info("Using sequential processing")
            new_pages = self._extract_sequential(images, book_title, start_page, stats, progress_callback, skip_pages)
        
        # Combine pages from checkpoint and new extractions
        pages.extend(new_pages)

        # Calculate summary statistics
        if stats["confidence_scores"]:
            stats["avg_confidence"] = sum(stats["confidence_scores"]) / len(stats["confidence_scores"])
            stats["min_confidence"] = min(stats["confidence_scores"])
            stats["upgrade_rate"] = f"{stats['upgrades'] / len(images) * 100:.1f}%"
        
        # Log summary
        logger.info(f"\n{'='*60}")
        logger.info("EXTRACTION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"  Pages: {stats['successful']}/{stats['total_pages']} successful")
        if stats.get("avg_confidence"):
            logger.info(f"  Avg Confidence: {stats['avg_confidence']:.2f}")
            logger.info(f"  Upgrades: {stats['upgrades']} ({stats['upgrade_rate']})")
        logger.info(f"{'='*60}\n")
        
        return ExtractionResult(
            source_file=book_title or "unknown",
            total_pages=len(images),
            pages=pages,
            extraction_stats=stats,
        )
    
    def _extract_sequential(
        self,
        images: List,
        book_title: str,
        start_page: int,
        stats: Dict,
        progress_callback: callable = None,
        skip_pages: set = None
    ) -> List[ExtractedPage]:
        """Extract pages sequentially with checkpoint support."""
        pages = []
        skip_pages = skip_pages or set()
        checkpoint_path = self._get_checkpoint_path(book_title, start_page, len(images))
        
        for i, image in enumerate(images):
            page_num = start_page + i
            
            # Skip already-processed pages from checkpoint
            if page_num in skip_pages:
                logger.info(f"⏭️ Skipping page {page_num} (from checkpoint)")
                continue
            
            try:
                logger.info(f"Extracting page {page_num} ({i+1}/{len(images)})...")
                
                extracted_page = self.extractor.extract_page(
                    image=image,
                    page_num=page_num,
                    book_title=book_title,
                )
                
                pages.append(extracted_page)
                self._update_stats(stats, extracted_page, page_num)
                
                # Save checkpoint periodically
                if (
                    self.extractor.config.enable_checkpoints 
                    and len(pages) % self.extractor.config.checkpoint_interval == 0
                ):
                    self._save_checkpoint(checkpoint_path, pages, stats, book_title, start_page)
                
                if progress_callback:
                    progress_callback(i + 1, len(images), page_num)
                    
            except Exception as e:
                logger.error(f"Failed to extract page {page_num}: {e}")
                stats["failed"] += 1
                pages.append(self._create_failed_page(page_num, e))
        
        return pages
    
    def _extract_parallel(
        self,
        images: List,
        book_title: str,
        start_page: int,
        stats: Dict,
        progress_callback: callable = None,
        skip_pages: set = None
    ) -> List[ExtractedPage]:
        """Extract pages in parallel with checkpoint support."""
        pages = [None] * len(images)  # Pre-allocate to maintain order
        skip_pages = skip_pages or set()
        completed = 0
        
        def extract_single(index_and_image):
            """Extract a single page - used for parallel execution."""
            i, image = index_and_image
            page_num = start_page + i
            
            # Skip already-processed pages from checkpoint
            if page_num in skip_pages:
                logger.info(f"⏭️ Skipping page {page_num} (from checkpoint)")
                return i, None, None  # Return None to indicate skip
            
            try:
                logger.info(f"Extracting page {page_num} ({i+1}/{len(images)})...")
                
                extracted_page = self.extractor.extract_page(
                    image=image,
                    page_num=page_num,
                    book_title=book_title,
                )
                
                return i, extracted_page, None
                
            except Exception as e:
                logger.error(f"Failed to extract page {page_num}: {e}")
                return i, None, e
        
        # Execute extractions in parallel
        with ThreadPoolExecutor(max_workers=self.extractor.config.max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(extract_single, (i, img)): i 
                for i, img in enumerate(images)
            }
            
            # Process completed tasks
            for future in as_completed(future_to_index):
                i, extracted_page, error = future.result()
                page_num = start_page + i
                completed += 1
                
                if extracted_page:
                    pages[i] = extracted_page
                    self._update_stats(stats, extracted_page, page_num)
                else:
                    stats["failed"] += 1
                    pages[i] = self._create_failed_page(page_num, error)
                
                if progress_callback:
                    progress_callback(completed, len(images), page_num)
        
        return pages
    
    def _update_stats(self, stats: Dict, page: ExtractedPage, page_num: int):
        """Update statistics with page data."""
        stats["successful"] += 1
        stats["total_content_blocks"] += len(page.content_blocks)
        
        # Track page types
        page_type = page.metadata.page_type.value
        stats["page_types"][page_type] = stats["page_types"].get(page_type, 0) + 1
        
        # Track confidence
        if page.confidence:
            stats["confidence_scores"].append(page.confidence.overall_score)
            if page.confidence.overall_score < 0.8:
                stats["low_confidence_pages"].append(page_num)
        
        # Track upgrades
        if page.retry_metadata and page.retry_metadata.retry_count > 0:
            stats["upgrades"] += 1
    
    def _create_failed_page(self, page_num: int, error: Exception) -> ExtractedPage:
        """Create a failed page entry."""
        return ExtractedPage(
            metadata=PageMetadata(
                page_number=page_num,
                page_type=PageType.MIXED,
            ),
            content_blocks=[],
            raw_text="",
            extraction_confidence=0.0,
            extraction_notes=f"Extraction failed: {str(error)}",
        )



if __name__ == "__main__":
    # Quick test
    config = ExtractionConfig(
        output_dir="./test_output",
        save_raw_responses=True,
    )
    
    extractor = VisionExtractor(config)
    print(f"Extractor initialized: {extractor.config.model_name}")
