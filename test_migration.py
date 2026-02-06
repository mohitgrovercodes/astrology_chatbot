
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.ai.user_manager import get_user_manager

def test_migration():
    print("Initializing User Manager (SQLite Mode)...")
    try:
        user_manager = get_user_manager()
        print("User Manager initialized.")
        
        # Check if DB file exists
        if os.path.exists("data/astro.db"):
            print("✅ data/astro.db created.")
        else:
            print("❌ data/astro.db NOT found.")
            
        # Check specific user
        print("Checking for user011...")
        if user_manager.user_exists("user011"):
            profile = user_manager.get_user_profile("user011")
            print(f"✅ User011 found: {profile.name}")
        else:
            print("❌ User011 NOT found.")
            
        # Check conversation history
        print("Adding message to history...")
        user_manager.add_message("user011", "user", "Hello from test script")
        history = user_manager.get_history("user011")
        print(f"History retrieved: {len(history)} messages")
        if len(history) > 0 and history[-1]['content'] == "Hello from test script":
             print("✅ History storage working.")
        else:
             print("❌ History storage failed.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_migration()
