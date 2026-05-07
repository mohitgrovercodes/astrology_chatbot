# src/ai/__init__.py
"""
AI components for NakshatraAI V2.
"""

# Import the classifier
from .intent_classifier import LLMIntentClassifier

# Backward-compatible alias
SimplifiedIntentClassifier = LLMIntentClassifier

# Try to import other components
try:
    from .hybrid_retriever import HybridRetriever
except ImportError:
    HybridRetriever = None

try:
    from .prompt_builder import PromptBuilder
except ImportError:
    PromptBuilder = None

try:
    from .semantic_frame import SemanticFrame, SemanticFrameBuilder, get_semantic_frame_builder
except ImportError:
    SemanticFrame = None
    SemanticFrameBuilder = None
    get_semantic_frame_builder = None

__all__ = [
    'SimplifiedIntentClassifier',
    'HybridRetriever',
    'PromptBuilder',
    'SemanticFrame',
    'SemanticFrameBuilder',
    'get_semantic_frame_builder',
]
