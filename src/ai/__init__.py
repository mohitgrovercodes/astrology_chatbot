# src/ai/__init__.py
# src\ai\__init__.py
"""
AI components for NakshatraAI V2.
"""

# Import the classifier
from .intent_classifier import SimplifiedIntentClassifier

# Try to import other components
try:
    from .hybrid_retriever import HybridRetriever
except ImportError:
    HybridRetriever = None

try:
    from .prompt_builder import PromptBuilder
except ImportError:
    PromptBuilder = None

__all__ = [
    'SimplifiedIntentClassifier',
    'HybridRetriever',
    'PromptBuilder',
]