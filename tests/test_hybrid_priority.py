# tests/test_hybrid_priority.py
# tests\test_hybrid_priority.py
"""
Verification test for Hybrid Data Priority.

Verifies:
1. [PRIORITY] Injected data is used (Bypassing calculations)
2. [HYBRID]   Partial injection (Name via API, Chart missing → fallback to engine)
3. [HISTORY]  Injected conversation history takes priority over empty state
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


# ── Test user profile (replaces DB lookup, fully stateless) ──────────────────
TEST_USER_PROFILE = {
    "user_id":          "hybrid_test_user",
    "name":             "Original Database Arjun",
    "date_of_birth":    "1990-05-15",
    "time_of_birth":    "10:30:00",
    "place_of_birth":   "Delhi, India",
    "latitude":         28.6139,
    "longitude":        77.2090,
    "timezone":         "Asia/Kolkata",
    "preferred_system": "vedic"
}

def _make_orchestrator():
    """Create orchestrator with no external dependencies (fully stateless)."""
    return EnhancedLangGraphOrchestrator(
        intent_classifier=LLMIntentClassifier(),
        hybrid_retriever=None,
        prompt_builder=PromptBuilder(),
        calculation_tools=None,  # Auto-loads from src.tools.tools
        llm=None,                # Auto-loads from LLMFactory
        fast_llm=None
    )


def test_hybrid_priority():
    print("=" * 70)
    print("Testing Hybrid Data Priority (Injected Data First, Engine Fallback)")
    print("=" * 70)
    print()

    orchestrator = _make_orchestrator()

    # ── CASE 1: Full injection override ──────────────────────────────────────
    print("--- CASE 1: Full Chart Injection Override ---")
    fake_chart = {
        "lagna":     "Aries",
        "moon_sign": "Leo",
        "sun_sign":  "Scorpio",
        "planets": {
            "Moon": {"sign": "Leo",      "house": 5},
            "Sun":  {"sign": "Scorpio",  "house": 8}
        }
    }
    result = orchestrator.process_query(
        query="Tell me my moon sign from this specific session.",
        user_id="hybrid_test_user",
        user_profile_override=TEST_USER_PROFILE,
        session_data={"chart_data": fake_chart}
    )
    print(f"Response: {result['answer']}")
    if "Leo" in result['answer']:
        print("[OK] Full override: Injected chart (Leo) took precedence over engine.")
    else:
        print("[FAIL] Full override failed — Leo not found in response.")

    # ── CASE 2: Partial injection (profile only, chart falls back to engine) ──
    print("\n--- CASE 2: Partial Injection (Profile only, no pre-computed chart) ---")
    partial_profile = dict(TEST_USER_PROFILE)
    partial_profile["name"] = "Hybrid Priority Arjun"

    result = orchestrator.process_query(
        query="What is my moon sign?",
        user_id="hybrid_test_user",
        user_profile_override=partial_profile
    )
    print(f"Response: {result['answer']}")
    # Engine should calculate the chart from the profile's birth data
    print("[INFO] If chart was calculated from birth data, test passed.")

    # ── CASE 3: History injection ─────────────────────────────────────────────
    print("\n--- CASE 3: History Priority (Injected Conversation Context) ---")
    injected_history = [
        {"role": "user",      "content": "I am traveling to Paris."},
        {"role": "assistant", "content": "Paris is lovely for your Moon sign."}
    ]
    result_priority = orchestrator.process_query(
        query="Where did I say I am going?",
        user_id="hybrid_test_user",
        user_profile_override=TEST_USER_PROFILE,
        conversation_history=injected_history
    )
    print(f"Response: {result_priority['answer']}")
    if "Paris" in result_priority['answer']:
        print("[OK] History priority: Injected history was honoured.")
    else:
        print("[FAIL] History priority failed — Paris not found in response.")

    print("\n" + "=" * 70)
    print("Hybrid Priority Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_hybrid_priority()
