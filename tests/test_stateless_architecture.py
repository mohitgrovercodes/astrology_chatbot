# tests/test_stateless_architecture.py
# tests\test_stateless_architecture.py
"""
Verification test for Stateless Production Architecture.

This script verifies that the orchestrator can operate without a database
or calculation engine if all necessary context is provided in the state.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
from src.ai.intent_classifier import LLMIntentClassifier
from src.ai.prompt_builder import PromptBuilder

def test_stateless_flow():
    print("="*70)
    print("Testing Stateless Production Architecture (No DB, No Engine)")
    print("="*70)
    print()

    # 1. Setup Orchestrator with ZERO dependencies (except LLM and PromptBuilder)
    # We pass None for user_manager to simulate production
    # Calculation tools and retriever will be bypassed
    orchestrator = EnhancedLangGraphOrchestrator(
        intent_classifier=LLMIntentClassifier(),
        user_manager=None, # NO DATABASE
        hybrid_retriever=None, # NO RETRIEVER
        prompt_builder=PromptBuilder(),
        calculation_tools={}, # NO CALCULATION ENGINE
        llm=None, # Let it load from default factory (correct way)
        fast_llm=None
    )

    # 2. Mock full context injection
    user_id = "external_user_123"
    user_profile = {
        "name": "Stateless Guru",
        "date_of_birth": "1990-01-01",
        "preferred_system": "vedic",
        "language": "en"
    }
    
    # Injected calculation results
    chart_data = {
        "lagna": "Sagittarius",
        "moon_sign": "Pisces",
        "sun_sign": "Capricorn",
        "planets": {
            "Sun": {"rashi": "Capricorn", "house": 2},
            "Moon": {"rashi": "Pisces", "house": 4}
        }
    }
    
    dasha_data = {
        "mahadasha": {"planet": "Jupiter", "start_date": "2020-01-01", "end_date": "2036-01-01"},
        "antardasha": {"planet": "Saturn", "start_date": "2023-01-01", "end_date": "2025-01-01"},
        "dasha_sequence": "Jupiter/Saturn"
    }
    
    transit_data = {
        "date": str(datetime.now().date()),
        "transits": {"Jupiter": "Aries", "Saturn": "Aquarius"}
    }

    print("--- Running CHITCHAT Test ---")
    # Chitchat doesn't need much, but let's see if it works without DB
    result = orchestrator.process_query(
        query="Hello Nakshatra!",
        user_id=user_id,
        user_profile_override=user_profile
    )
    print(f"Response: {result['answer']}")
    if "Stateless Guru" in result['answer'] or "Namaste" in result['answer']:
        print("[OK] Chitchat passed in stateless mode.")
    else:
        print("[FAIL] Chitchat failed.")

    print("\n--- Running PREDICTION Test (Full Injection) ---")
    # This should return the info from our injected data
    result = orchestrator.process_query(
        query="Tell me about my Jupiter dasha.",
        user_id=user_id,
        user_profile_override=user_profile,
        session_data={
            "chart_data": chart_data,
            "dasha_data": dasha_data,
            "transit_data": transit_data
        }
    )
    
    print(f"Response: {result['answer']}")
    if "Jupiter" in result['answer'] and "Saturn" in result['answer']:
        print("[OK] Prediction bypass passed. Used injected dasha/chart data!")
    else:
        print("[FAIL] Prediction bypass failed.")

    print("\n" + "="*70)
    print("Stateless Architecture Test Complete!")
    print("="*70)

if __name__ == "__main__":
    test_stateless_flow()
