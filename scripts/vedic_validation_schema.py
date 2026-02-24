# vedic_validation_schema.py
"""
Pydantic schemas for Vedic Astrology Validation Rules

This module defines the structure for validation rules extracted from classical texts.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from enum import Enum


class ValidationSeverity(str, Enum):
    """Severity levels for validation rules - Common levels listed, but any string is accepted"""
    CRITICAL = "critical"  # Must check, blocks prediction if violated
    HIGH = "high"          # Significantly impacts prediction
    MEDIUM = "medium"      # Moderate impact
    LOW = "low"           # Minor consideration
    
    @classmethod
    def _missing_(cls, value):
        """Allow any string value not in enum - makes it flexible"""
        pseudo_member = str.__new__(cls, value)
        pseudo_member._name_ = value
        pseudo_member._value_ = value
        return pseudo_member


class ValidationCategory(str, Enum):
    """Categories of validation rules - Common categories listed, but any string is accepted"""
    PLANETARY_STATE = "planetary_state"           # Combustion, retrogression, etc.
    DIVISIONAL_CONFIRMATION = "divisional_confirmation"  # D9 confirmation, etc.
    LAGNA_SPECIFIC = "lagna_specific"            # Functional nature by ascendant
    HIERARCHICAL_LOGIC = "hierarchical_logic"    # Promise->Timing->Trigger
    STRENGTH_ASSESSMENT = "strength_assessment"  # Shadbala, dignity
    LUNAR_CONSIDERATION = "lunar_consideration"  # Moon's paksha, state
    KARMIC_AXIS = "karmic_axis"                 # Rahu/Ketu effects
    ASPECT_ANALYSIS = "aspect_analysis"          # Drishti effects
    YOGA_DETECTION = "yoga_detection"            # Planetary combinations
    HOUSE_ANALYSIS = "house_analysis"            # Bhava strength, significations
    TABLE_BASED_RULES = "table_based_rules"      # Rules from tables (plural)
    TABLE_BASED_RULE = "table_based_rule"        # Rules from tables (singular)
    GENERAL = "general"                          # General principles
    PLANETARY_COMBINATION = "planetary_combination"  # Planet combinations
    HOUSE_LORDSHIP = "house_lordship"           # House lord rules
    
    @classmethod
    def _missing_(cls, value):
        """Allow any string value not in enum - makes it flexible"""
        pseudo_member = str.__new__(cls, value)
        pseudo_member._name_ = value
        pseudo_member._value_ = value
        return pseudo_member


class QueryType(str, Enum):
    """Types of astrological queries - Common types listed, but any string is accepted"""
    # Core query types
    MARRIAGE = "marriage"
    CAREER = "career"
    FINANCE = "finance"
    HEALTH = "health"
    EDUCATION = "education"
    CHILDREN = "children"
    SPIRITUAL = "spiritual"
    PROPERTY = "property"
    GENERAL = "general"
    ALL = "all"
    
    # Additional common types
    TRAVEL = "travel"
    HAPPINESS = "happiness"
    PARTNERSHIPS = "partnerships"
    REPUTATION = "reputation"
    PARENTS = "parents"
    FAMILY = "family"
    MOTHER = "mother"
    SIBLINGS = "siblings"
    ENEMIES = "enemies"
    PARTNERSHIP = "partnership"
    LONGEVITY = "longevity"
    FATHER = "father"
    GAINS = "gains"
    EXPENDITURE = "expenditure"
    MENTAL_WELLBEING = "mental_wellbeing"
    APPEARANCE = "appearance"
    CHARACTER = "character"
    SEX = "sex"
    LOST_THINGS = "lost things"
    MISSING_PERSONS = "missing persons"
    
    @classmethod
    def _missing_(cls, value):
        """Allow any string value not in enum - makes it flexible"""
        # Create a pseudo-member for unknown values
        pseudo_member = str.__new__(cls, value)
        pseudo_member._name_ = value
        pseudo_member._value_ = value
        return pseudo_member


class PredictionStage(str, Enum):
    """Stages in prediction workflow - Common stages listed, but any string is accepted"""
    PROMISE = "promise"      # D1 + Divisional charts
    TIMING = "timing"        # Dasha analysis
    TRIGGER = "trigger"      # Transit analysis
    SYNTHESIS = "synthesis"  # Final combination
    ALL = "all"              # Applies to all stages
    
    @classmethod
    def _missing_(cls, value):
        """Allow any string value not in enum - makes it flexible"""
        pseudo_member = str.__new__(cls, value)
        pseudo_member._name_ = value
        pseudo_member._value_ = value
        return pseudo_member


class CheckLogic(BaseModel):
    """Logic for executing a validation check"""
    condition: str = Field(description="When this check applies (e.g., 'planet_distance_from_sun < 8')")
    calculation: str = Field(description="How to calculate/check (e.g., 'abs(planet_long - sun_long)')")
    threshold: Optional[float] = Field(None, description="Numerical threshold if applicable (use None for non-numeric rules)")
    comparison: Optional[Literal["<", ">", "<=", ">=", "==", "!=", "=", "equals"]] = Field(None, description="Comparison operator: <, >, ==, !=, <=, >= (or = or equals for equality)")


class RuleCancellation(BaseModel):
    """Conditions that cancel or modify a rule"""
    condition: str = Field(description="Condition that cancels the rule")
    impact: str = Field(description="How it modifies the result")
    percentage_reduction: Optional[int] = Field(None, description="% reduction in impact (0-100)")
    
    class Config:
        # Allow extra fields and coercion
        extra = "ignore"
        
    @classmethod
    def __get_validators__(cls):
        yield cls.validate_to_json
        
    @classmethod
    def validate_to_json(cls, value):
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            # Convert float to int for percentage_reduction
            if 'percentage_reduction' in value and isinstance(value['percentage_reduction'], float):
                value['percentage_reduction'] = int(value['percentage_reduction'])
            return cls(**value)
        raise ValueError("Invalid RuleCancellation")


class LagnaSpecificRule(BaseModel):
    """Lagna-specific functional nature"""
    lagna: str = Field(description="Ascendant sign (e.g., 'Aries', 'Taurus')")
    yogakarakas: List[str] = Field(default_factory=list, description="Benefic planets for this lagna")
    functional_malefics: List[str] = Field(default_factory=list, description="Malefic planets for this lagna")
    neutral: List[str] = Field(default_factory=list)


class VedicValidationRule(BaseModel):
    """
    Complete validation rule extracted from classical texts
    
    This represents a single non-negotiable check that must be performed
    during astrological analysis.
    """
    
    # Identification
    rule_id: str = Field(description="Unique identifier (e.g., 'VR001')")
    rule_name: str = Field(description="Human-readable name")
    
    # Classification
    category: ValidationCategory
    severity: ValidationSeverity
    check_order: int = Field(description="Order in which to check (1=first, 2=second, etc.)")
    
    # Applicability
    applies_to_queries: List[QueryType] = Field(description="Which query types need this check")
    prediction_stage: PredictionStage = Field(description="When in workflow to check")
    
    # Logic
    check_logic: CheckLogic = Field(description="How to perform the validation")
    
    # Impact
    halt_on_failure: bool = Field(default=False, description="Stop prediction if this check fails")
    impact_if_violated: str = Field(description="What happens if rule is violated")
    impact_percentage: Optional[int] = Field(None, description="% reduction in result strength (0-100)")
    
    # Exceptions and Cancellations
    cancellation_conditions: List[RuleCancellation] = Field(default_factory=list)
    
    # Lagna-specific rules (if applicable)
    lagna_specific_rules: Optional[List[LagnaSpecificRule]] = None
    
    # Classical References
    classical_reference: str = Field(description="Source text (e.g., 'BPHS 27.10-12')")
    chapter: Optional[str] = None
    verse_range: Optional[str] = None
    
    # Dependencies
    depends_on_rules: List[str] = Field(default_factory=list, description="Rule IDs this depends on")
    conflicts_with_rules: List[str] = Field(default_factory=list)
    
    # Extraction metadata
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    expert_verified: bool = Field(default=False)
    extraction_notes: Optional[str] = None
    
    class Config:
        use_enum_values = True


class VedicValidationRuleSet(BaseModel):
    """Collection of validation rules"""
    version: str = Field(default="1.0.0")
    last_updated: str
    total_rules: int
    rules: List[VedicValidationRule]
    
    # Statistics
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_stage: Dict[str, int] = Field(default_factory=dict)


# Enhanced Metadata for RAG (building on existing structure)
class EnhancedRAGMetadata(BaseModel):
    """
    Enhanced metadata for RAG chunks - extends current structure
    Based on existing implementation in src/rag/preprocessing/
    """
    
    # === EXISTING FIELDS (from current implementation) ===
    source: str
    chapter: Optional[str] = None
    page: Optional[int] = None
    verse: Optional[str] = None
    language: str = "en"
    
    # Entities (already extracted)
    planets: List[str] = Field(default_factory=list)
    houses: List[int] = Field(default_factory=list)
    signs: List[str] = Field(default_factory=list)
    nakshatras: List[str] = Field(default_factory=list)
    
    # Topics (already classified)
    topics: List[str] = Field(default_factory=list)
    
    # === NEW FIELDS (for validation enhancement) ===
    
    # Content type classification
    content_type: Literal[
        "validation_rule",
        "interpretation",
        "combination_rule",
        "timing_technique",
        "general_principle",
        "remedial_measure"
    ] = "interpretation"
    
    # Validation-specific metadata
    is_validation_rule: bool = False
    validation_category: Optional[ValidationCategory] = None
    severity: Optional[ValidationSeverity] = None
    check_order: Optional[int] = None
    halt_on_failure: bool = False
    
    # Prediction workflow
    prediction_stage: Optional[PredictionStage] = None
    applies_to_queries: List[QueryType] = Field(default_factory=list)
    
    # Text authority
    tier: Literal["tier1_classical", "tier2_specialized", "tier3_modern"] = "tier1_classical"
    
    # Additional context
    divisional_charts: List[str] = Field(default_factory=list)  # ["D9", "D10"]
    yogas_mentioned: List[str] = Field(default_factory=list)
    
    # Functional classification
    is_beneficial: Optional[bool] = None
    is_malefic: Optional[bool] = None
    
    # Relationships
    depends_on: List[str] = Field(default_factory=list, description="Chunk IDs this depends on")
    related_rules: List[str] = Field(default_factory=list, description="Related rule IDs")


# Example instances for documentation
EXAMPLE_COMBUSTION_RULE = VedicValidationRule(
    rule_id="VR001",
    rule_name="Combustion Check",
    category=ValidationCategory.PLANETARY_STATE,
    severity=ValidationSeverity.HIGH,
    check_order=2,
    applies_to_queries=[QueryType.ALL],
    prediction_stage=PredictionStage.PROMISE,
    check_logic=CheckLogic(
        condition="planet_distance_from_sun < 8_degrees",
        calculation="abs(planet_longitude - sun_longitude)",
        threshold=8.0,
        comparison="<"
    ),
    halt_on_failure=False,
    impact_if_violated="Planet loses 60-80% of its power to deliver results",
    impact_percentage=70,
    cancellation_conditions=[
        RuleCancellation(
            condition="planet_is_retrograde",
            impact="Combustion effect reduced by 50%",
            percentage_reduction=50
        )
    ],
    classical_reference="BPHS 27.10-12",
    chapter="27",
    verse_range="10-12",
    extraction_confidence=0.95,
    expert_verified=True
)

EXAMPLE_FUNCTIONAL_NATURE_RULE = VedicValidationRule(
    rule_id="VR003",
    rule_name="Functional Nature Check",
    category=ValidationCategory.LAGNA_SPECIFIC,
    severity=ValidationSeverity.CRITICAL,
    check_order=1,
    applies_to_queries=[QueryType.ALL],
    prediction_stage=PredictionStage.PROMISE,
    check_logic=CheckLogic(
        condition="before_interpreting_any_planet",
        calculation="determine_functional_nature(planet, lagna)",
        threshold=None,
        comparison=None
    ),
    halt_on_failure=False,
    impact_if_violated="Benefic planet may actually harm, malefic may help",
    impact_percentage=100,
    lagna_specific_rules=[
        LagnaSpecificRule(
            lagna="Aries",
            yogakarakas=["Sun", "Mars"],
            functional_malefics=["Saturn", "Mercury", "Venus"],
            neutral=["Moon", "Jupiter"]
        ),
        LagnaSpecificRule(
            lagna="Taurus",
            yogakarakas=["Saturn"],
            functional_malefics=["Jupiter", "Venus", "Mars"],
            neutral=["Sun", "Moon", "Mercury"]
        ),
        # ... other lagnas would be added
    ],
    classical_reference="BPHS Chapter 25",
    chapter="25",
    extraction_confidence=1.0,
    expert_verified=True
)