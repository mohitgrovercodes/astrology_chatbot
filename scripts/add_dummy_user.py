# scripts/add_dummy_user.py
# scripts\add_dummy_user.py
#!/usr/bin/env python3
"""
Add Dummy User Script
=====================

Interactive script to add custom test users to the DummyUserDB.
Useful for testing the chatbot with different birth profiles.

Usage:
    python add_dummy_user.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent  # Go up from scripts/ to project root
sys.path.insert(0, str(project_root))

from src.db.dummy_user_db import DummyUserDB


def get_input(prompt: str, default: str = None, required: bool = True) -> str:
    """Get user input with optional default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        
        if value:
            return value
        elif default:
            return default
        elif not required:
            return ""
        else:
            print("❌ This field is required. Please enter a value.")


def get_coordinates():
    """Get latitude and longitude with validation."""
    print("\n📍 Birth Location Coordinates")
    print("   (You can find these on Google Maps)")
    
    while True:
        try:
            lat_str = input("   Latitude (-90 to 90): ").strip()
            lat = float(lat_str)
            if -90 <= lat <= 90:
                break
            print("   ❌ Latitude must be between -90 and 90")
        except ValueError:
            print("   ❌ Please enter a valid number")
    
    while True:
        try:
            lon_str = input("   Longitude (-180 to 180): ").strip()
            lon = float(lon_str)
            if -180 <= lon <= 180:
                break
            print("   ❌ Longitude must be between -180 and 180")
        except ValueError:
            print("   ❌ Please enter a valid number")
    
    return lat, lon


def validate_date(date_str: str) -> bool:
    """Validate date format YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time(time_str: str) -> bool:
    """Validate time format HH:MM:SS."""
    try:
        datetime.strptime(time_str, "%H:%M:%S")
        return True
    except ValueError:
        return False


def main():
    print("\n" + "="*70)
    print("🌟 Add Dummy User to NakshatraAI")
    print("="*70)
    print()
    print("This script will add a new test user to the in-memory database.")
    print("The user will be available when you run chatbot.py")
    print()
    
    # Initialize DummyUserDB
    db = DummyUserDB()
    
    print("📋 Current Users:")
    for user_id, user_data in db.users.items():
        print(f"   • {user_id}: {user_data['name']}")
    print()
    
    # Get user details
    print("="*70)
    print("Enter New User Details")
    print("="*70)
    print()
    
    # User ID
    while True:
        user_id = get_input("User ID (e.g., user004, test_user_2)")
        if user_id in db.users:
            print(f"❌ User ID '{user_id}' already exists. Please choose a different ID.")
        else:
            break
    
    # Basic Info
    name = get_input("Full Name (e.g., John Doe)")
    email = get_input("Email", required=False)
    
    # Birth Date
    while True:
        birth_date = get_input("Birth Date (YYYY-MM-DD, e.g., 1990-05-15)")
        if validate_date(birth_date):
            break
        print("❌ Invalid date format. Please use YYYY-MM-DD")
    
    # Birth Time
    while True:
        birth_time = get_input("Birth Time (HH:MM:SS, e.g., 14:30:00)")
        if validate_time(birth_time):
            break
        print("❌ Invalid time format. Please use HH:MM:SS")
    
    # Birth Place
    birth_place = get_input("Birth Place (e.g., New Delhi, India)")
    
    # Coordinates
    print()
    print("💡 Tip: You can find coordinates by searching the place on Google Maps")
    print("   Right-click on the location and select 'What's here?'")
    latitude, longitude = get_coordinates()
    
    # Timezone
    print()
    print("🕐 Timezone")
    print("   Examples: Asia/Kolkata, America/New_York, Europe/London")
    timezone = get_input("Timezone", default="Asia/Kolkata")
    
    # Astrology System
    print()
    print("🔮 Astrology System")
    print("   1. Vedic (Default)")
    print("   2. Western")
    system_choice = input("   Choice [1]: ").strip()
    system = "western" if system_choice == "2" else "vedic"
    
    # Language
    print()
    print("🗣️  Preferred Language")
    print("   1. Hindi (Romanized) - hi-lat (Default)")
    print("   2. English - en")
    print("   3. Tamil - ta")
    lang_choice = input("   Choice [1]: ").strip()
    
    lang_map = {"1": "hi-lat", "2": "en", "3": "ta"}
    language = lang_map.get(lang_choice, "hi-lat")
    
    # Create user data
    user_data = {
        "user_id": user_id,
        "name": name,
        "email": email or f"{user_id}@example.com",
        "birth_date": birth_date,
        "birth_time": birth_time,
        "birth_place": birth_place,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "system": system,
        "language": language,
        "birth_chart_cache": None,
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat()
    }
    
    # Confirm
    print()
    print("="*70)
    print("📝 User Summary")
    print("="*70)
    print(f"User ID:      {user_id}")
    print(f"Name:         {name}")
    print(f"Email:        {user_data['email']}")
    print(f"Birth Date:   {birth_date}")
    print(f"Birth Time:   {birth_time}")
    print(f"Birth Place:  {birth_place}")
    print(f"Coordinates:  {latitude}, {longitude}")
    print(f"Timezone:     {timezone}")
    print(f"System:       {system.title()}")
    print(f"Language:     {language}")
    print("="*70)
    print()
    
    confirm = input("Add this user? (y/n) [y]: ").strip().lower()
    if confirm and confirm != 'y':
        print("\n❌ User creation cancelled.")
        return
    
    # Add user to database
    db.upsert_user(user_data)
    
    print()
    print("="*70)
    print("✅ User Added Successfully!")
    print("="*70)
    print()
    print(f"You can now use '{user_id}' when running chatbot.py")
    print()
    print("⚠️  NOTE: This user is only in memory and will be lost when you restart.")
    print("   To make it permanent, add it to src/db/dummy_user_db.py")
    print()
    print("To add it permanently, add this to the sample_users list:")
    print()
    print("```python")
    print("{")
    for key, value in user_data.items():
        if isinstance(value, str):
            print(f'    "{key}": "{value}",')
        else:
            print(f'    "{key}": {value},')
    print("},")
    print("```")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
