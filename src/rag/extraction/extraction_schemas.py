"""
Pydantic schemas for structured extraction output.
These schemas define the RAG-ready format for astrology texts.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class PageType(str, Enum):
    """Classification of page content type"""
    TEXT_HEAVY = "text_heavy"       # Primarily verses and prose
    TABLE_HEAVY = "table_heavy"     # Primarily tabular data
    MIXED = "mixed"                 # Both text and tables
    CHART = "chart"                 # Astrological charts/diagrams
    TITLE = "title"                 # Title/chapter pages
    INDEX = "index"                 # Table of contents or index


class ContentType(str, Enum):
    """Type of content block"""
    SHLOKA = "shloka"               # Sanskrit verse
    TRANSLATION = "translation"     # English translation of verse
    NOTES = "notes"                 # Commentary/notes section
    PROSE = "prose"                 # Regular prose text
    TABLE = "table"                 # Tabular data
    LIST = "list"                   # Enumerated or bulleted list
    HEADING = "heading"             # Section/chapter heading
    SUBHEADING = "subheading"       # Sub-section heading
    EXAMPLE = "example"             # Worked example
    FORMULA = "formula"             # Mathematical/astronomical formula
    REFERENCE = "reference"         # Cross-reference


class TableCell(BaseModel):
    """Single cell in a table"""
    value: str = Field(description="Cell content")
    row_span: int = Field(default=1, description="Number of rows this cell spans")
    col_span: int = Field(default=1, description="Number of columns this cell spans")
    is_header: bool = Field(default=False, description="Whether this is a header cell")


class ExtractedTable(BaseModel):
    """Structured representation of a table"""
    title: Optional[str] = Field(None, description="Table title/caption if present")
    headers: List[str] = Field(default_factory=list, description="Column headers")
    rows: List[List[str]] = Field(default_factory=list, description="Table rows as list of lists")
    markdown: str = Field(description="Markdown representation of the table")
    context: Optional[str] = Field(None, description="Surrounding context explaining the table")
    table_type: Optional[str] = Field(None, description="Type of table (e.g., planetary_friendships, exaltation_degrees)")


class VerseBlock(BaseModel):
    """A verse (shloka) with its translation and notes"""
    verse_number: Optional[str] = Field(None, description="Verse number (e.g., '13-14', '॥९५॥')")
    sanskrit_text: str = Field(description="Original Sanskrit/Hindi verse in Devanagari")
    transliteration: Optional[str] = Field(None, description="Romanized transliteration if available")
    translation: str = Field(description="English translation")
    notes: Optional[str] = Field(None, description="Additional notes or commentary")
    topic: Optional[str] = Field(None, description="Topic of this verse (e.g., 'Virgo described', 'Jupiter Mahadasha')")


class ContentBlock(BaseModel):
    """A block of content extracted from the page"""
    content_type: ContentType = Field(description="Type of this content block")
    text: str = Field(description="The actual text content")
    verse_data: Optional[VerseBlock] = Field(None, description="Structured verse data if content_type is shloka/translation")
    table_data: Optional[ExtractedTable] = Field(None, description="Structured table data if content_type is table")
    sequence_order: int = Field(description="Order of this block on the page (1-indexed)")


class PageMetadata(BaseModel):
    """Metadata about the extracted page"""
    page_number: int = Field(description="Page number in the PDF")
    book_title: Optional[str] = Field(None, description="Book title (e.g., 'Brihat Parasara Hora Shastra')")
    chapter_title: Optional[str] = Field(None, description="Current chapter title")
    chapter_number: Optional[int] = Field(None, description="Chapter number if identifiable")
    section_title: Optional[str] = Field(None, description="Current section title")
    page_type: PageType = Field(description="Classification of page content")
    has_tables: bool = Field(default=False, description="Whether page contains tables")
    has_charts: bool = Field(default=False, description="Whether page contains astrological charts")
    languages_present: List[str] = Field(default_factory=lambda: ["english"], description="Languages found on page")
    astrology_system: Literal["vedic", "western", "both", "general"] = Field(
        default="vedic", 
        description="Astrology system this content relates to"
    )


class ConfidenceMetadata(BaseModel):
    """Metadata about LLM confidence in generated output."""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    criteria: Dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown by criteria (e.g., image_quality, text_clarity, layout_detection)"
    )
    reasoning: Optional[str] = Field(None, description="Explanation of confidence score")
    flags: List[str] = Field(
        default_factory=list,
        description="Quality flags (e.g., 'low_ocr_quality', 'partial_page', 'blur')"
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
    """Complete extraction result for a single page"""
    metadata: PageMetadata = Field(description="Page metadata")
    content_blocks: List[ContentBlock] = Field(default_factory=list, description="Ordered list of content blocks")
    raw_text: Optional[str] = Field(None, description="Raw concatenated text for fallback")
    extraction_confidence: float = Field(
        default=0.8, 
        ge=0.0, 
        le=1.0, 
        description="Confidence in extraction quality (0-1)"
    )
    extraction_notes: Optional[str] = Field(None, description="Notes about extraction quality/issues")
    
    # Quality tracking (new fields)
    confidence: Optional[ConfidenceMetadata] = Field(
        None,
        description="Detailed confidence breakdown for extraction quality"
    )
    retry_metadata: Optional[RetryMetadata] = Field(
        None,
        description="Metadata about extraction retries and model upgrades"
    )


class RAGChunk(BaseModel):
    """A chunk ready for embedding and RAG retrieval"""
    chunk_id: str = Field(description="Unique identifier for this chunk")
    text: str = Field(description="The text content to embed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata for filtering")
    
    # Source tracking
    source_book: str = Field(description="Source book title")
    source_chapter: Optional[str] = Field(None, description="Source chapter")
    source_page: int = Field(description="Source page number")
    
    # Content classification
    content_type: str = Field(description="Type of content (verse, table, prose, etc.)")
    topic: Optional[str] = Field(None, description="Topic/subject matter")
    
    # For verses specifically
    verse_numbers: Optional[str] = Field(None, description="Verse numbers if applicable")
    has_sanskrit: bool = Field(default=False, description="Whether chunk contains Sanskrit text")


class ExtractionResult(BaseModel):
    """Complete extraction result for a document or batch"""
    source_file: str = Field(description="Source PDF filename")
    total_pages: int = Field(description="Total pages processed")
    pages: List[ExtractedPage] = Field(default_factory=list, description="Extracted pages")
    extraction_stats: Dict[str, Any] = Field(default_factory=dict, description="Extraction statistics")


# ============================================================================
# Topic Classification Schemas (for metadata enrichment)
# ============================================================================

class AstrologyTopic(str, Enum):
    """Main topics in Vedic/Western astrology"""
    # Signs/Rashis
    ZODIAC_SIGNS = "zodiac_signs"
    SIGN_CHARACTERISTICS = "sign_characteristics"
    
    # Planets/Grahas
    PLANETS = "planets"
    PLANETARY_CHARACTERISTICS = "planetary_characteristics"
    PLANETARY_RELATIONSHIPS = "planetary_relationships"
    PLANETARY_STRENGTHS = "planetary_strengths"
    UPAGRAHAS = "upagrahas"  # Sub-planets
    
    # Houses/Bhavas
    HOUSES = "houses"
    HOUSE_SIGNIFICATIONS = "house_significations"
    
    # Nakshatras
    NAKSHATRAS = "nakshatras"
    NAKSHATRA_CHARACTERISTICS = "nakshatra_characteristics"
    
    # Dashas
    DASHA_SYSTEMS = "dasha_systems"
    VIMSHOTTARI_DASHA = "vimshottari_dasha"
    DASHA_EFFECTS = "dasha_effects"
    
    # Aspects/Yogas
    ASPECTS = "aspects"
    YOGAS = "yogas"
    RAJA_YOGAS = "raja_yogas"
    DHANA_YOGAS = "dhana_yogas"
    ARISHTA_YOGAS = "arishta_yogas"
    
    # Divisional Charts
    DIVISIONAL_CHARTS = "divisional_charts"
    NAVAMSA = "navamsa"
    
    # Karakas
    KARAKAS = "karakas"
    CHARA_KARAKAS = "chara_karakas"
    STHIRA_KARAKAS = "sthira_karakas"
    
    # Time/Muhurta
    MUHURTA = "muhurta"
    TIME_DIVISIONS = "time_divisions"
    PANCHANGA = "panchanga"
    
    # Predictions
    GENERAL_PREDICTIONS = "general_predictions"
    LONGEVITY = "longevity"
    MARRIAGE = "marriage"
    CHILDREN = "children"
    PROFESSION = "profession"
    
    # Calculations
    ASTRONOMICAL_CALCULATIONS = "astronomical_calculations"
    AYANAMSA = "ayanamsa"
    
    # Other
    REMEDIES = "remedies"
    GENERAL = "general"
