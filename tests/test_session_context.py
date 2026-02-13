# tests\test_session_context.py
"""
Verification test for Session-Based User Context Integration.

This script verifies that session-provided data (like name) correctly 
overrides database-provided data in the orchestrator flow.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from src.orchestration.orchestrator import NakshatraState, EnhancedLangGraphOrchestrator
from src.ai.user_manager import get_user_manager

def test_session_override():
    print("="*70)
    print("Testing Session Context Integration (Redis Simulation)")
    print("="*70)
    print()

    # 1. Setup Mock Components
    user_manager = get_user_manager()
    user_id = "user011"
    
    # Get original DB profile
    db_profile = user_manager.get_user_profile(user_id)
    print(f"DB Profile Name: {db_profile.name}")
    
    # 2. Mock Orchestrator State
    # We'll test the _authenticate_node logic directly
    orchestrator = EnhancedLangGraphOrchestrator(
        intent_classifier=None,
        user_manager=user_manager,
        hybrid_retriever=None,
        prompt_builder=None
    )
    
    # Session data to override DB
    session_data = {
        "name": "Super Saiyan Astrologer",
        "custom_note": "Premium VIP"
    }
    
    state: NakshatraState = {
        "query": "Who am I?",
        "user_id": user_id,
        "conversation_history": [],
        "session_data": session_data,
        "user_profile": None,
        "authenticated": False,
        "intent": None,
        "confidence": 0.0,
        "intent_reasoning": "",
        "cached": False,
        "detected_language": "en",
        "original_query": "Who am I?",
        "chart_data": None,
        "dasha_data": None,
        "transit_data": None,
        "knowledge_chunks": None,
        "answer": "",
        "error": None,
        "processing_time": 0.0,
        "messages": [],
        "persona_type": "vedic",
        "validation_attempts": 0,
        "validation_feedback": None,
        "is_safe": True
    }
    
    # 3. Execute Authentication Node
    print(f"\nRunning _authenticate_node with session_data: {session_data}")
    updated_state = orchestrator._authenticate_node(state)
    
    # 4. Verify Results
    final_profile = updated_state.get('user_profile', {})
    final_name = final_profile.get('name')
    
    print(f"\nFinal Profile Name in State: {final_name}")
    print(f"Final Profile Custom Note: {final_profile.get('custom_note')}")
    
    if final_name == session_data['name']:
        print("\n[OK] PASS: Session name correctly overrode DB name!")
    else:
        print(f"\n[FAIL] FAIL: Name mismatch. Expected {session_data['name']}, Got {final_name}")
        
    if final_profile.get('custom_note') == session_data['custom_note']:
        print("[OK] PASS: Session custom note correctly merged into profile!")
    else:
        print("[FAIL] FAIL: Custom note missing from merged profile.")

    print("\n" + "="*70)
    print("Test Complete!")
    print("="*70)

if __name__ == "__main__":
    test_session_override()
