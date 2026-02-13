# src\rag\preprocessing\schemas.py
#!/usr/bin/env python3
"""
Pydantic Schemas for Text Pre-Processing Pipeline

Defines data contracts between each phase of the pipeline.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# Phase 1: Raw Extraction Output (Input to Pipeline)
# =============================================================================

class PageType(str, Enum):
    """Type of page content"""
    TEXT = "text"
    TABLE = "table"
    MIXED = "mixed"
    TITLE_PAGE = "title_page"


class ConfidenceMetadata(BaseModel):
    """Metadata about LLM confidence in generated output."""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    criteria: Dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown by criteria (e.g., image_quality, text_clarity)"
    )
    reasoning: Optional[str] = Field(None, description="Explanation of confidence score")
    flags: List[str] = Field(
        default_factory=list,
        description="Quality flags (e.g., 'low_ocr_quality', 'partial_page')"
    )


class RetryMetadata(BaseModel):
    """Track extraction retries with upgraded models."""
    initial_model: str = Field(..., description="Model used for initial extraction")
    retry_model: Optional[str] = Field(None, description="Model used for retry (if any)")
    initial_confidence: Optional[float] = Field(
        None,
        description="Confidence score from initial extraction"
    )
    retry_reason: Optional[str] = Field(None, description="Reason for retry")
    retry_count: int = Field(default=0, description="Number of retries performed")


class ExtractedPage(BaseModel):
    """
    Schema for raw extracted page from Vision LLM (Phase 1 output).
    This is the INPUT to the preprocessing pipeline.
    """
    page_number: int = Field(..., description="1-indexed page number")
    page_type: PageType = Field(default=PageType.MIXED)
    title: Optional[str] = Field(None, description="Chapter/section title if detected")
    content: str = Field(..., description="Full extracted text content")
    has_sanskrit: bool = Field(default=False)
    verses: List[str] = Field(default_factory=list, description="Extracted Sanskrit verses")
    verse_numbers: List[str] = Field(default_factory=list, description="Verse numbers found")
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Quality tracking
    confidence: Optional[ConfidenceMetadata] = Field(
        None,
        description="Confidence score for extraction quality"
    )
    retry_metadata: Optional[RetryMetadata] = Field(
        None,
        description="Metadata about extraction retries and model upgrades"
    )
    
    class Config:
        use_enum_values = True


# =============================================================================
# Phase 2: Structural Cleaning Output
# =============================================================================

class CleanedPage(BaseModel):
    """
    Schema for cleaned page (Phase 2 output).
    Adds cleaning metadata and preserves original for audit.
    """
    page_number: int
    page_type: PageType
    title: Optional[str] = Field(None, description="Validated title (null if was running header)")
    content: str = Field(..., description="Cleaned content")
    original_content: str = Field(..., description="Original content before cleaning")
    has_sanskrit: bool = False
    verses: List[str] = Field(default_factory=list)
    verse_numbers: List[str] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Cleaning metadata
    cleaning_applied: List[str] = Field(
        default_factory=list, 
        description="List of cleaning operations applied"
    )
    detected_headers: List[str] = Field(
        default_factory=list,
        description="Headers/footers detected and removed"
    )
    title_was_header: bool = Field(
        default=False,
        description="True if title was detected as running header"
    )
    
    class Config:
        use_enum_values = True


# =============================================================================
# Phase 3: Cross-Page Analysis Output
# =============================================================================

class LinkedPage(BaseModel):
    """
    Schema for analyzed page with cross-page relationships (Phase 3 output).
    """
    page_number: int
    page_type: PageType
    title: Optional[str] = None
    content: str
    original_content: str
    has_sanskrit: bool = False
    verses: List[str] = Field(default_factory=list)
    verse_numbers: List[str] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    cleaning_applied: List[str] = Field(default_factory=list)
    
    # Cross-page relationship metadata
    continues_from_previous: bool = Field(
        default=False,
        description="True if this page continues content from previous page"
    )
    continues_to_next: bool = Field(
        default=False,
        description="True if content continues to next page"
    )
    continuation_confidence: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="Confidence score for continuation detection"
    )
    
    # Semantic metadata
    chapter: Optional[str] = Field(None, description="Chapter name if identified")
    section: Optional[str] = Field(None, description="Section name if identified")
    main_topic: Optional[str] = Field(None, description="Main astrological topic")
    topic_id: Optional[str] = Field(None, description="Topic cluster identifier")
    related_pages: List[int] = Field(
        default_factory=list,
        description="Page numbers with related content"
    )
    
    # Boundary analysis
    starts_mid_sentence: bool = Field(
        default=False,
        description="True if page starts in middle of a sentence"
    )
    ends_mid_sentence: bool = Field(
        default=False,
        description="True if page ends in middle of a sentence"
    )
    
    class Config:
        use_enum_values = True


# =============================================================================
# Phase 4: Semantic Segmentation Output
# =============================================================================

class UnitType(str, Enum):
    """Type of semantic unit"""
    VERSE_COMMENTARY = "verse_commentary"
    CONCEPT_EXPLANATION = "concept_explanation"
    TABLE_CONTEXT = "table_context"
    CHAPTER_INTRO = "chapter_intro"


class VerseData(BaseModel):
    """Sanskrit verse with transliteration"""
    number: str = Field(..., description="Verse number (e.g., '66', '17-18')")
    sanskrit: str = Field(..., description="Devanagari text")
    iast: Optional[str] = Field(None, description="IAST transliteration for search")


class SemanticUnit(BaseModel):
    """
    Schema for semantic unit (Phase 4 output).
    Represents a complete knowledge unit (verse + commentary, concept, etc.)
    """
    unit_id: str = Field(..., description="Unique identifier (e.g., 'bphs-gulika-verse-66')")
    unit_type: UnitType
    source_pages: List[int] = Field(..., description="Page numbers this unit spans")
    
    # Hierarchical context
    source_book: Optional[str] = Field(None, description="Book title")
    chapter: Optional[str] = None
    section: Optional[str] = None
    
    # Content
    verse: Optional[VerseData] = Field(None, description="Verse data if applicable")
    commentary: Optional[str] = Field(None, description="Commentary/interpretation text")
    notes: Optional[str] = Field(None, description="Additional notes or explanations")
    combined_text: str = Field(..., description="Full searchable text combining all parts")
    
    # Relationships
    related_units: List[str] = Field(
        default_factory=list,
        description="IDs of related semantic units"
    )
    
    # Token info for chunking
    token_count: Optional[int] = Field(None, description="Estimated token count")
    
    class Config:
        use_enum_values = True


# =============================================================================
# Phase 5: Chunk Enrichment Output
# =============================================================================

class AstrologicalEntities(BaseModel):
    """Extracted astrological entities for filtering"""
    planets: List[str] = Field(default_factory=list, description="Planets mentioned")
    houses: List[str] = Field(default_factory=list, description="Houses mentioned")
    signs: List[str] = Field(default_factory=list, description="Zodiac signs mentioned")
    nakshatras: List[str] = Field(default_factory=list, description="Nakshatras mentioned")
    yogas: List[str] = Field(default_factory=list, description="Yogas mentioned")
    concepts: List[str] = Field(default_factory=list, description="Other astrological concepts")


class ChunkMetadata(BaseModel):
    """Metadata for VectorDB filtering"""
    source_book: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    verse_number: Optional[str] = None
    tradition: str = Field(default="vedic", description="vedic or western")
    entities: AstrologicalEntities = Field(default_factory=AstrologicalEntities)


class EnrichedChunk(BaseModel):
    """
    Schema for enriched chunk ready for embedding (Phase 5 output).
    Final format before embedding and VectorDB ingestion.
    """
    chunk_id: str = Field(..., description="Unique chunk identifier")
    unit_id: str = Field(..., description="Parent semantic unit ID")
    
    # For Embedding
    text_for_embedding: str = Field(
        ..., 
        description="Optimized text for embedding (includes context header)"
    )
    token_count: int = Field(..., description="Token count of text_for_embedding")
    
    # For Display in Chatbot Response
    display_text: str = Field(..., description="Original text for showing to user")
    verse_sanskrit: Optional[str] = Field(None, description="Sanskrit verse if applicable")
    
    # For Filtering
    metadata: ChunkMetadata
    
    # For Retrieval Boost
    hypothetical_questions: List[str] = Field(
        default_factory=list,
        description="Questions this chunk can answer (for HyDE-style retrieval)"
    )
    summary: Optional[str] = Field(
        None, 
        description="1-2 sentence summary of chunk content"
    )
    
    # For Context Expansion
    related_chunks: List[str] = Field(
        default_factory=list,
        description="IDs of related chunks for context expansion"
    )
    source_pages: List[int] = Field(default_factory=list)
    
    # Embedding (populated in Phase 6)
    embedding: Optional[List[float]] = Field(
        None, 
        description="Embedding vector (populated in Phase 6)"
    )


# =============================================================================
# Batch Containers
# =============================================================================

class ExtractedDocument(BaseModel):
    """Container for multiple extracted pages"""
    pages: List[ExtractedPage]
    source_file: Optional[str] = None


class CleanedDocument(BaseModel):
    """Container for multiple cleaned pages"""
    pages: List[CleanedPage]
    source_file: Optional[str] = None
    global_headers: List[str] = Field(
        default_factory=list,
        description="Headers detected across all pages"
    )


class LinkedDocument(BaseModel):
    """Container for multiple linked pages"""
    pages: List[LinkedPage]
    source_file: Optional[str] = None
    chapters: List[str] = Field(default_factory=list, description="All chapters found")
    topic_clusters: Dict[str, List[int]] = Field(
        default_factory=dict,
        description="Topic ID to page numbers mapping"
    )


class SemanticDocument(BaseModel):
    """Container for semantic units from a document"""
    units: List[SemanticUnit]
    source_file: Optional[str] = None
    source_book: Optional[str] = None


class EnrichedDocument(BaseModel):
    """Container for enriched chunks ready for embedding"""
    chunks: List[EnrichedChunk]
    source_file: Optional[str] = None
    total_tokens: int = 0
