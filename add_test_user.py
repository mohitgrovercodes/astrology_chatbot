"""
Utility to Add Custom Test Users to MongoDB.
Run this to add your own user for testing NakshatraAI.
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def add_user_interactive():
    """Interactive utility to add a user to MongoDB."""
    
    print("=" * 70)
    print("ADD TEST USER TO MONGODB")
    print("=" * 70)
    print()
    
    # Check MongoDB connection
    mongodb_uri = os.getenv('MONGODB_URI')
    
    if not mongodb_uri:
        print("⚠️  No MONGODB_URI found in environment!")
        print("\nUsing DUMMY DATA mode for development.")
        print("\nTo use MongoDB:")
        print("  1. Set MONGODB_URI in your .env file")
        print("  2. Run this script again")
        print()
        use_dummy = True
    else:
        print(f"✓ MongoDB URI found")
        print(f"  URI: {mongodb_uri[:20]}...")
        print()
        use_dummy = False
    
    # Collect user information
    print("Enter user details:")
    print("-" * 70)
    
    user_id = input("User ID (e.g., 'user004'): ").strip()
    if not user_id:
        print("❌ User ID is required!")
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
    
    # Build user document
    user_doc = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "date_of_birth": date_of_birth,
        "time_of_birth": time_of_birth,
        "place_of_birth": place_of_birth,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "preferred_system": preferred_system,
        "language": "en",
        "created_at": datetime.now(),
        "last_active": datetime.now()
    }
    
    # Display summary
    print("\n" + "=" * 70)
    print("USER SUMMARY")
    print("=" * 70)
    print(f"User ID: {user_id}")
    print(f"Name: {name}")
    print(f"Email: {email or 'Not provided'}")
    print(f"Birth: {date_of_birth} at {time_of_birth}")
    print(f"Location: {place_of_birth}")
    print(f"Coordinates: {latitude}, {longitude}")
    print(f"Timezone: {timezone}")
    print(f"System: {preferred_system.upper()}")
    print("=" * 70)
    print()
    
    # Confirm
    confirm = input("Add this user? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return
    
    # Add to database
    if use_dummy:
        print("\n⚠️  DUMMY MODE - User not added to MongoDB")
        print("\nTo add to MongoDB:")
        print("  1. Set MONGODB_URI in .env")
        print("  2. Run this script again")
        print()
        print("For now, you can manually add to src/ai/user_manager.py:")
        print()
        print(f"'{user_id}': {{")
        for key, value in user_doc.items():
            if key not in ['created_at', 'last_active']:
                if isinstance(value, str):
                    print(f"    '{key}': '{value}',")
                else:
                    print(f"    '{key}': {value},")
        print("}")
        print()
    else:
        try:
            from pymongo import MongoClient
            
            client = MongoClient(mongodb_uri)
            db = client['astro_app']
            users_collection = db['users']
            
            # Check if user exists
            existing = users_collection.find_one({"user_id": user_id})
            if existing:
                print(f"\n⚠️  User '{user_id}' already exists!")
                overwrite = input("Overwrite? (yes/no): ").strip().lower()
                if overwrite != 'yes':
                    print("❌ Cancelled")
                    return
                
                # Update
                users_collection.replace_one({"user_id": user_id}, user_doc)
                print(f"\n✅ User '{user_id}' updated successfully!")
            else:
                # Insert
                users_collection.insert_one(user_doc)
                print(f"\n✅ User '{user_id}' added successfully!")
            
            print()
            print("You can now use this user ID in the chatbot:")
            print(f"  python chatbot.py")
            print(f"  Enter user_id: {user_id}")
            print()
            
        except Exception as e:
            print(f"\n❌ Error adding user to MongoDB: {e}")
            print()


def list_existing_users():
    """List existing users in MongoDB."""
    
    mongodb_uri = os.getenv('MONGODB_URI')
    
    if not mongodb_uri:
        print("\n⚠️  No MONGODB_URI - showing dummy users only:")
        print()
        print("Dummy test users (from user_manager.py):")
        print("  • user001 - Arjun Kumar (Vedic, Jaipur)")
        print("  • user002 - Priya Sharma (Vedic, Mumbai)")
        print("  • user003 - Sophia Anderson (Western, New York)")
        print()
        return
    
    try:
        from pymongo import MongoClient
        
        client = MongoClient(mongodb_uri)
        db = client['astro_app']
        users_collection = db['users']
        
        users = list(users_collection.find({}, {
            "user_id": 1,
            "name": 1,
            "preferred_system": 1,
            "place_of_birth": 1,
            "_id": 0
        }))
        
        if not users:
            print("\n⚠️  No users found in MongoDB")
            print("\nAdd a user with: python add_test_user.py")
            return
        
        print("\n" + "=" * 70)
        print(f"USERS IN MONGODB ({len(users)} found)")
        print("=" * 70)
        
        for user in users:
            print(f"  • {user['user_id']} - {user['name']} "
                  f"({user['preferred_system']}, {user.get('place_of_birth', 'Unknown')})")
        
        print("=" * 70)
        print()
        
    except Exception as e:
        print(f"\n❌ Error listing users: {e}\n")


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
