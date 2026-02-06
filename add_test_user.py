"""
Utility to Add Custom Test Users to Database (SQLite).
Run this to add your own user for testing NakshatraAI.
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from src.ai.user_manager import get_user_manager

load_dotenv()

def add_user_interactive():
    """Interactive utility to add a user to Database."""
    
    print("=" * 70)
    print("ADD TEST USER TO DATABASE (SQLite)")
    print("=" * 70)
    print()
    
    # Initialize Manager
    user_manager = get_user_manager()
    print("✓ Connected to Database")
    print()
    
    # Collect user information
    print("Enter user details:")
    print("-" * 70)
    
    user_id = input("User ID (e.g., 'user004'): ").strip()
    if not user_id:
        print("❌ User ID is required!")
        return
        
    # Check if exists
    if user_manager.user_exists(user_id):
        print(f"⚠️  User '{user_id}' already exists!")
        overwrite = input("Overwrite? (yes/no): ").strip().lower()
        if overwrite != 'yes':
            print("❌ Cancelled")
            return
    
    name = input("Full Name (e.g., 'John Doe'): ").strip()
    if not name:
        print("❌ Name is required!")
        return
    
    email = input("Email (optional): ").strip() or None
    
    print("\nBirth Details:")
    date_of_birth = input("  Date of Birth (YYYY-MM-DD, e.g., '1990-03-15'): ").strip()
    time_of_birth = input("  Time of Birth (HH:MM:SS, e.g., '14:30:00'): ").strip()
    place_of_birth = input("  Place of Birth (e.g., 'Jaipur, India'): ").strip()
    
    print("\nLocation Coordinates:")
    try:
        latitude = float(input("  Latitude (e.g., 26.9124): ").strip())
        longitude = float(input("  Longitude (e.g., 75.7873): ").strip())
    except ValueError:
        print("❌ Invalid coordinates!")
        return
    
    timezone = input("  Timezone (e.g., 'Asia/Kolkata'): ").strip() or "Asia/Kolkata"
    
    print("\nAstrology System:")
    print("  1. Vedic (Sidereal)")
    print("  2. Western (Tropical)")
    system_choice = input("  Choose (1 or 2): ").strip()
    preferred_system = "vedic" if system_choice == "1" else "western"
    
    # Build user dict (matches structure expected by UserManager.create_user)
    user_data = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "birth_data": {
            "date_of_birth": date_of_birth,
            "time_of_birth": time_of_birth,
            "place_of_birth": place_of_birth,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone
        },
        "preferences": {
            "astrology_system": preferred_system,
            "language": "en" 
        }
    }
    
    # Display summary
    print("\n" + "=" * 70)
    print("USER SUMMARY")
    print("=" * 70)
    print(f"User ID: {user_id}")
    print(f"Name: {name}")
    print(f"Birth: {date_of_birth} at {time_of_birth}")
    print(f"Location: {place_of_birth}")
    print(f"System: {preferred_system.upper()}")
    print("=" * 70)
    print()
    
    # Confirm
    confirm = input("Add this user? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return
    
    # Add via Manager
    try:
        user_manager.create_user(user_data)
        print(f"\n✅ User '{user_id}' added successfully!")
        print()
        print("You can now use this user ID in the chatbot:")
        print(f"  python chatbot.py")
        print(f"  Enter user_id: {user_id}")
        print()
        
    except Exception as e:
        print(f"\n❌ Error adding user: {e}")
        print()


def list_existing_users():
    """List existing users."""
    user_manager = get_user_manager()
    
    # We need to access underlying DB for list queries if not exposed in Manager
    # Currently UserManager doesn't have list_users. 
    # We can access sqlite client directly if needed or add method.
    # For now, let's use the sqlite client if available.
    
    if user_manager.use_sqlite and user_manager.sqlite:
        conn = user_manager.sqlite.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, system, birth_place FROM users")
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            print("\n⚠️  No users found in Database")
            return
            
        print("\n" + "=" * 70)
        print(f"USERS IN DATABASE ({len(users)} found)")
        print("=" * 70)
        
        for user in users:
            print(f"  • {user['user_id']} - {user['name']} "
                  f"({user['system']}, {user['birth_place']})")
        
        print("=" * 70)
        print()
    else:
        print("Using Dummy Data (cannot list all dynamically)")


def main():
    """Main menu."""
    
    print("\n" + "=" * 70)
    print("NAKSHATRAAI - USER MANAGEMENT UTILITY")
    print("=" * 70)
    print()
    print("Options:")
    print("  1. Add new test user")
    print("  2. List existing users")
    print("  3. Exit")
    print()
    
    choice = input("Choose (1-3): ").strip()
    
    if choice == "1":
        add_user_interactive()
    elif choice == "2":
        list_existing_users()
    elif choice == "3":
        print("\n👋 Goodbye!\n")
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    main()
