# src/safety/models.py
# src\safety\models.py
"""
Safety Classification Models

Pydantic models for safety decision-making in the astrology chatbot.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class SafetyDecision(BaseModel):
    """
    Structured output from safety classifier.
    
    This model defines the decision-making output for query safety checks.
    """
    
    category: Literal[
        "HARD_BLOCK",      # Never answer - harmful/dangerous
        "SOFT_BLOCK",      # Decline politely - out of scope/inappropriate
        "CONDITIONAL",     # Answer with disclaimer
        "REFRAME",         # Transform the question
        "SAFE"            # Normal query - answer directly
    ] = Field(
        description="Primary classification category for the query"
    )
    
    reason: str = Field(
        description=(
            "Specific reason code for classification. Examples: "
            "'death_prediction', 'medical_diagnosis', 'health_tendency', "
            "'financial_trend', 'poorly_framed', 'educational'"
        )
    )
    
    should_answer: bool = Field(
        description=(
            "Whether the chatbot should proceed with generating a response. "
            "False for HARD_BLOCK and SOFT_BLOCK, True for others."
        )
    )
    
    disclaimer_type: Optional[str] = Field(
        default=None,
        description=(
            "Type of disclaimer to add if category is CONDITIONAL. "
            "Options: 'HEALTH', 'FINANCIAL', 'RELATIONSHIP', 'GENERAL'"
        )
    )
    
    reframed_query: Optional[str] = Field(
        default=None,
        description=(
            "Reframed version of the query if category is REFRAME. "
            "Should transform fortune-telling style questions into "
            "astrologically appropriate inquiries."
        )
    )
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    
    @field_validator('confidence')
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        """Clamp confidence to [0.0, 1.0] range to handle floating-point precision."""
        return max(0.0, min(1.0, v))
    
    explanation: Optional[str] = Field(
        default=None,
        description="Brief explanation of why this classification was made (for logging/debugging)"
    )
    
    keywords_matched: Optional[list[str]] = Field(
        default=None,
        description="Keywords or patterns that triggered this classification"
    )
    
    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "examples": [
                {
                    "category": "HARD_BLOCK",
                    "reason": "death_prediction",
                    "should_answer": False,
                    "disclaimer_type": None,
                    "reframed_query": None,
                    "confidence": 0.95,
                    "explanation": "Query asks for specific death timing",
                    "keywords_matched": ["when", "die", "death"]
                },
                {
                    "category": "CONDITIONAL",
                    "reason": "health_tendency",
                    "should_answer": True,
                    "disclaimer_type": "HEALTH",
                    "reframed_query": None,
                    "confidence": 0.88,
                    "explanation": "Query about health tendencies, not diagnosis",
                    "keywords_matched": ["health", "6th house"]
                },
                {
                    "category": "REFRAME",
                    "reason": "poorly_framed",
                    "should_answer": True,
                    "disclaimer_type": None,
                    "reframed_query": "What periods in my chart support wealth accumulation?",
                    "confidence": 0.82,
                    "explanation": "Fortune-telling style question needs reframing",
                    "keywords_matched": ["will I become", "rich"]
                }
            ]
        }


class SafetyCheckResult(BaseModel):
    """
    Complete result from safety check process.
    
    Includes the decision plus metadata for logging and routing.
    """
    
    decision: SafetyDecision = Field(description="The safety classification decision")
    
    original_query: str = Field(description="The original user query")
    
    processed_query: Optional[str] = Field(
        default=None,
        description="The query to use for processing (original or reframed)"
    )
    
    requires_human_review: bool = Field(
        default=False,
        description="Whether this query should be flagged for human review"
    )
    
    block_template_key: Optional[str] = Field(
        default=None,
        description="Template key for blocked response (if applicable)"
    )
    
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata for logging and analytics"
    )
    
    @property
    def should_proceed(self) -> bool:
        """Whether to proceed with query processing"""
        return self.decision.should_answer
    
    @property
    def needs_disclaimer(self) -> bool:
        """Whether response needs a disclaimer"""
        return self.decision.disclaimer_type is not None
    
    @property
    def is_blocked(self) -> bool:
        """Whether query is blocked"""
        return self.decision.category in ["HARD_BLOCK", "SOFT_BLOCK"]
    
    def get_template_key(self) -> Optional[str]:
        """
        Get the response template key based on decision.
        
        Returns:
            Template key string or None if no template needed
        """
        if self.decision.category == "HARD_BLOCK":
            return f"HARD_BLOCK_{self.decision.reason.upper()}"
        elif self.decision.category == "SOFT_BLOCK":
            return f"SOFT_BLOCK_{self.decision.reason.upper()}"
        elif self.decision.disclaimer_type:
            return f"DISCLAIMER_{self.decision.disclaimer_type.upper()}"
        return None


# Reason code constants for easy reference
class BlockReasons:
    """Constants for block reason codes"""
    
    # Hard Block Reasons
    DEATH_PREDICTION = "death_prediction"
    MEDICAL_DIAGNOSIS = "medical_diagnosis"
    GAMBLING_SPECIFIC = "gambling_specific"
    LEGAL_ADVICE = "legal_advice"
    HARMFUL_INTENT = "harmful_intent"
    
    # Soft Block Reasons
    FORTUNE_TELLING = "fortune_telling"
    PRIVACY_VIOLATION = "privacy_violation"
    OUT_OF_SCOPE = "out_of_scope"
    CONSPIRACY_THEORY = "conspiracy_theory"
    THIRD_PARTY_PREDICTION = "third_party_prediction"
    SABOTAGE_CRITICISM = "sabotage_criticism"
    
    # Conditional Reasons
    HEALTH_TENDENCY = "health_tendency"
    FINANCIAL_TREND = "financial_trend"
    RELATIONSHIP_COMPATIBILITY = "relationship_compatibility"
    CHILDREN_TIMING = "children_timing"
    CAREER_CHANGE = "career_change"
    
    # Reframe Reasons
    POORLY_FRAMED = "poorly_framed"
    MISUNDERSTOOD = "misunderstood"
    
    # Safe Reasons
    EDUCATIONAL = "educational"
    CALCULATION_QUERY = "calculation_query"
    CHART_INTERPRETATION = "chart_interpretation"


class DisclaimerTypes:
    """Constants for disclaimer types"""
    
    HEALTH = "HEALTH"
    FINANCIAL = "FINANCIAL"
    RELATIONSHIP = "RELATIONSHIP"
    GENERAL = "GENERAL"
