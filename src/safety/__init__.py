"""
Safety & Guardrails Module - Phase 6
====================================

Core Philosophy: Behave like a HUMAN ASTROLOGER
- Never block queries
- Clarify first (C), redirect to positive (B), then provide with empathy (A)
- Natural disclaimers, not legal boilerplate
- Guide, don't refuse

Components:
- QueryAnalyzer: Identifies sensitive topics and appropriate handling
- ResponseEnhancer: Adds natural disclaimers and empathetic framing
- InputValidator: Flexible birth data validation
- DISCLAIMERS: Contextual disclaimer templates
"""

from src.safety.guardrails import (
    QueryAnalyzer,
    ResponseEnhancer,
    SensitivityCategory,
    QueryAnalysis
)

from src.safety.disclaimers import (
    DISCLAIMERS,
    get_disclaimer,
    get_clarifying_question,
    get_positive_redirect
)

from src.safety.input_validator import (
    InputValidator,
    ValidationResult,
    validate_birth_data
)

__all__ = [
    # Core classes
    "QueryAnalyzer",
    "ResponseEnhancer",
    "InputValidator",
    
    # Data types
    "SensitivityCategory",
    "QueryAnalysis",
    "ValidationResult",
    
    # Utilities
    "DISCLAIMERS",
    "get_disclaimer",
    "get_clarifying_question",
    "get_positive_redirect",
    "validate_birth_data",
]
