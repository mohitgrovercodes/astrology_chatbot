# tests\test_hybrid_priority.py
"""
Verification test for Hybrid Data Priority.

Verifies:
1. [PRIORITY] Injected data is used (Bypassing calculations/DB)
2. [FALLBACK] Missing data triggers internal tools
3. [HYBRID] Partial injection (Name via API, Chart via Engine)
"""

import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
from src.ai.intent_classifier import LLMIntentClassifier
from src.ai.prompt_builder import PromptBuilder
from src.ai.user_manager import get_user_manager

def test_hybrid_priority():
    print("="*70)
    print("Testing Hybrid Data Priority (Redis First, Engine Fallback)")
    print("="*70)
    print()

    # Setup orchestrator with full dependencies
    mongodb_uri = os.getenv('MONGODB_URI')
    user_manager = get_user_manager(mongodb_uri)
    
    # Ensure a test user exists in the dummy/real DB for fallback tests
    test_user_id = "hybrid_test_user"
    if not user_manager.user_exists(test_user_id):
        print(f"Creating test user: {test_user_id}")
        user_manager.create_user({
            "user_id": test_user_id,
            "name": "Original Database Arjun",
            "date_of_birth": "1990-05-15",
            "time_of_birth": "10:30:00",
            "place_of_birth": "Delhi, India",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic"
        })

    orchestrator = EnhancedLangGraphOrchestrator(
        intent_classifier=LLMIntentClassifier(),
        user_manager=user_manager,
        hybrid_retriever=None, # RAG bypassed for simplicity
        prompt_builder=PromptBuilder(),
        calculation_tools=None, # Auto-load
        llm=None, # Auto-load
        fast_llm=None
    )

    print("--- CASE 1: Partial Injection (Name from API, Chart from Fallback) ---")
    # Provide name but NO chart_data
    # LOGS should show: [AUTH] [PRIORITY] (for name) and [CALC] [FALLBACK] (for chart)
    result = orchestrator.process_query(
        query="What is my moon sign?",
        user_id=test_user_id,
        session_data={"name": "Hybrid Priority Arjun"}
    )
    print(f"Response: {result['answer']}")
    if "Dhanu" in result['answer'] or "Sagittarius" in result['answer']: 
        print("[OK] Partial injection: Chart calculated from Fallback (Dhanu).")
    else:
        print("[FAIL] Partial injection check failed (Chart mismatch).")
    
    # Check if name was promoted to state (internal check)
    if result.get('user_profile', {}).get('name') == "Hybrid Priority Arjun":
        print("[OK] Partial injection: Name successfully promoted from Priority.")
    else:
        print("[FAIL] Name promotion failed.")

    print("\n--- CASE 2: Full Injection Override (Leo instead of Database Rashi) ---")
    # Original Arjun is likely Vrishabha or Mithuna. We inject Leo.
    fake_chart = {
        "lagna": "Aries",
        "moon_sign": "Leo",
        "sun_sign": "Scorpio",
        "planets": {
            "Moon": {"rashi": "Leo", "house": 5},
            "Sun": {"rashi": "Scorpio", "house": 8}
        }
    }
    result = orchestrator.process_query(
        query="Tell me my moon sign from this specific session.",
        user_id=test_user_id,
        session_data={
            "name": "Overridden Arjun",
            "chart_data": fake_chart
        }
    )
    print(f"Response: {result['answer']}")
    if "Leo" in result['answer']:
        print("[OK] Full override: Injected chart (Leo) took precedence over DB.")
    else:
        print("[FAIL] Full override failed.")

    print("\n--- CASE 3: History Injection (API Priority vs DB Fallback) ---")
    # Test Fallback: NO history provided. Bot should load from DB.
    print("Testing History Fallback (Loading from DB)...")
    result_fallback = orchestrator.process_query(
        query="What did we just talk about?",
        user_id=test_user_id,
        conversation_history=None # Force fallback
    )
    # Since it's a new test user, history might be empty, but logs should show fallback attempt
    
    # Test Priority: Provide injected history
    print("Testing History Priority (Injected Context)...")
    injected_history = [
        {"role": "user", "content": "I am traveling to Paris."},
        {"role": "assistant", "content": "Paris is lovely for your Moon sign."}
    ]
    result_priority = orchestrator.process_query(
        query="Where did I say I am going?",
        user_id=test_user_id,
        conversation_history=injected_history
    )
    print(f"Response: {result_priority['answer']}")
    if "Paris" in result_priority['answer']:
        print("[OK] History priority: Injected history was honored.")
    else:
        print("[FAIL] History priority failed.")

    print("\n" + "="*70)
    print("Hybrid Priority Test Complete!")
    print("="*70)

if __name__ == "__main__":
    test_hybrid_priority()
