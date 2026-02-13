# tests\test_marriage_prediction_fix.py
import sys
from pathlib import Path
from datetime import datetime
import json
from unittest.mock import MagicMock
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
from src.ai.user_manager import UserProfile

def test_chart_calculation_fix():
    print("--- Testing Birth Chart Calculation Fix ---")
    
    # 1. Setup mock Orchestrator dependencies
    mock_user_manager = MagicMock()
    mock_sqlite = MagicMock()
    mock_user_manager.sqlite = mock_sqlite
    mock_user_manager.use_sqlite = True
    
    # Mimic user011 data from User Manager
    user_id = "user011"
    user_profile_dict = {
        'user_id': 'user011',
        'name': 'Mohit Grover',
        'date_of_birth': '1995-10-01',
        'time_of_birth': '07:30:00',
        'latitude': 27.553,
        'longitude': 76.6346,
        'timezone': 'Asia/Kolkata'
    }
    
    # Initialize Orchestrator (mocking heavy components if possible)
    # We'll pass None for most things since we are only testing one helper method
    orchestrator = EnhancedLangGraphOrchestrator(
        intent_classifier=MagicMock(),
        user_manager=mock_user_manager,
        hybrid_retriever=MagicMock(),
        prompt_builder=MagicMock()
    )
    
    # Mock get_user_profile for Orchestrator
    mock_user_manager.get_user_profile.return_value = None # Not used directly in _get_or_calculate_chart
    # The actual code uses user_profile passed as argument
    
    print(f"Calling _get_or_calculate_chart for {user_id}...")
    try:
        # We need to pass the dict that _authenticate_node would produce
        error, full_chart = orchestrator._get_or_calculate_chart(user_id, user_profile_dict)
        
        if error:
            print(f"[FAIL] Error returned: {error}")
            return False
            
        if full_chart:
            print(f"[SUCCESS] Chart calculated successfully!")
            print(f"Lagna: {full_chart.lagna.rashi_name}") # Verify lagna exists
            print(f"Moon Sign: {full_chart.rashi_name}")
            
            # Verify datetime
            expected_dt = datetime(1995, 10, 1, 7, 30, 0)
            print(f"Chart Date: {full_chart.birth_data.date}")
            assert full_chart.birth_data.date == expected_dt
            print("[OK] Birth datetime correctly combined.")
            
            return True
        else:
            print("[FAIL] full_chart is None")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception during calculation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chart_calculation_fix()
    if success:
        print("\nVERIFICATION PASSED")
        sys.exit(0)
    else:
        print("\nVERIFICATION FAILED")
        sys.exit(1)
