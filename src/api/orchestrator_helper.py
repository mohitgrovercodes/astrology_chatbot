# src/api/orchestrator_helper.py
"""
Orchestrator helper wrapper.

Canonical dependency wiring now lives in src.api.dependencies.
This module remains for backward compatibility with existing imports.
"""

from src.api.dependencies import get_orchestrator as get_orchestrator