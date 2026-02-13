# src\safety\__init__.py
"""
Safety Module for Astrology Chatbot

Handles safety classification, response templates, and guardrails.
"""

from .models import (
    SafetyDecision,
    SafetyCheckResult,
    BlockReasons,
    DisclaimerTypes,
)

from .classifier import (
    SafetyClassifier,
    create_safety_classifier,
)

from .templates import (
    RESPONSE_TEMPLATES,
    get_template,
    get_disclaimer,
    format_reframe_response,
    DEFAULT_BLOCK_MESSAGE,
    DEFAULT_ERROR_MESSAGE,
)

__all__ = [
    # Models
    "SafetyDecision",
    "SafetyCheckResult",
    "BlockReasons",
    "DisclaimerTypes",
    
    # Classifier
    "SafetyClassifier",
    "create_safety_classifier",
    
    # Templates
    "RESPONSE_TEMPLATES",
    "get_template",
    "get_disclaimer",
    "format_reframe_response",
    "DEFAULT_BLOCK_MESSAGE",
    "DEFAULT_ERROR_MESSAGE",
]
