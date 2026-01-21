"""
Astrology AI Chatbot - Source Package
======================================

Root package for all astrology calculation engines and utilities.
"""

# Root package marker
__version__ = "1.0.0"
__author__ = "Astrology AI Chatbot"

# Make modules accessible
from src import engines, utils

__all__ = [
    "engines",
    "utils",
]