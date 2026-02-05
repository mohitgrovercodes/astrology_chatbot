"""
User Manager for NakshatraAI.

Simple authentication: user in DB = authenticated.
No subscription checks (handled by your colleague at app level).
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class UserProfile:
    """User profile from database."""
    user_id: str
    name: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    time_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    preferred_system: str = "vedic"
    language: str = "en"
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    
    def has_birth_data(self) -> bool:
        """Check if user has complete birth data."""
        return all([
            self.date_of_birth,
            self.time_of_birth,
            self.latitude is not None,
            self.longitude is not None
        ])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.last_active:
            data['last_active'] = self.last_active.isoformat()
        return data


class UserManager:
    """
    User manager with simple authentication.
    
    Authentication logic: user_id in DB = authenticated
    """
    
    # Dummy users for development/testing
    DUMMY_USERS = {
        "user001": {
            "user_id": "user001",
            "name": "Arjun Kumar",
            "email": "arjun@example.com",
            "date_of_birth": "1990-03-15",
            "time_of_birth": "14:30:00",
            "place_of_birth": "Jaipur, Rajasthan",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic",
            "language": "en",
            "created_at": datetime(2024, 1, 15),
            "last_active": datetime.now()
        },
        "user002": {
            "user_id": "user002",
            "name": "Priya Sharma",
            "email": "priya@example.com",
            "date_of_birth": "1985-07-22",
            "time_of_birth": "08:15:00",
            "place_of_birth": "Mumbai, Maharashtra",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic",
            "language": "en",
            "created_at": datetime(2023, 8, 10),
            "last_active": datetime.now()
        },
        "user009": {
            "user_id": "user009",
            "name": "Mohit Grover",
            "email": "kickstartpythonai@gmail.com",
            "date_of_birth": "1995-10-01",
            "time_of_birth": "07:30:00",
            "place_of_birth": "Alwar, IN",
            "latitude": 27.5530,
            "longitude": 76.6346,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic",
            "language": "en",
            "created_at": datetime(2026, 1, 30),
            "last_active": datetime.now()
        },
        'user006': {
            'user_id': 'user006',
            'name': 'Kartikey Kichara',
            'email':'kkichara@gmail.com',
            'date_of_birth': '2003-05-04',
            'time_of_birth': '18:50:00',
            'place_of_birth': 'Bhilwara,India',
            'latitude': 25.3407,
            'longitude': 74.6313,
            'timezone': 'Asia/Kolkata',
            'preferred_system': 'vedic',
            'language': 'en',
            "created_at": datetime(2023, 8, 10),
            "last_active": datetime.now()
        },
        'user007': {
            'user_id': 'user007',
            'name': 'Veniram',
            'email': None,
            'date_of_birth': '2003-05-04',
            'time_of_birth': '18:50:00',
            'place_of_birth': 'Bhilwara,India',
            'latitude': 25.3407,
            'longitude': 74.6313,
            'timezone': 'Asia/Kolkata',
            'preferred_system': 'vedic',
            'language': 'en',
        },
        'user008': {
            'user_id': 'user008',
            'name': 'Anshul Kichara',
            'email': None,
            'date_of_birth': '1998-02-10',
            'time_of_birth': '6:00:00',
            'place_of_birth': 'Bhilwara,India',
            'latitude': 25.3407,
            'longitude': 74.6313,
            'timezone': 'Asia/Kolkata',
            'preferred_system': 'vedic',
            'language': 'en',
        },
        'user009': {
            'user_id': 'user009',
            'name': 'Kartikey Kichara',
            'email': None,
            'date_of_birth': '2003-05-04',
            'time_of_birth': '20:45:00',
            'place_of_birth': 'Bhilwara,India',
            'latitude': 25.3407,
            'longitude': 74.6313,
            'timezone': 'Asia/Kolkata',
            'preferred_system': 'vedic',
            'language': 'en',
        },
        "default_user": {
            "user_id": "default_user",
            "name": "Guest User",
            "email": "guest@example.com",
            "date_of_birth": "2000-01-01",
            "time_of_birth": "12:00:00",
            "place_of_birth": "New Delhi, IN",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic",
            "language": "en",
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }
    }
    
    def __init__(self, mongodb_uri: Optional[str] = None):
        """
        Initialize user manager.
        
        Args:
            mongodb_uri: MongoDB connection string (None = use dummy data)
        """
        self.use_mongodb = mongodb_uri is not None
        
        if self.use_mongodb:
            # Production: MongoDB connection
            try:
                from pymongo import MongoClient
                self.client = MongoClient(mongodb_uri)
                self.db = self.client['astro_app']
                self.users_collection = self.db['users']
                print("[USER] Connected to MongoDB")
            except ImportError:
                print("[USER] PyMongo not installed, falling back to dummy data")
                self.use_mongodb = False
                self.users_db = self.DUMMY_USERS
            except Exception as e:
                print(f"[USER] MongoDB connection failed: {e}, using dummy data")
                self.use_mongodb = False
                self.users_db = self.DUMMY_USERS
        else:
            # Development: Dummy data
            self.users_db = self.DUMMY_USERS
            print("[USER] Using dummy user database")
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Load user profile from database. 
        Note: This is used internally by Orchestrator and expects flat data.
        """
        raw_data = None
        if self.use_mongodb:
            try:
                raw_data = self.users_collection.find_one({"user_id": user_id})
            except Exception as e:
                print(f"[USER] Error loading profile: {e}")
                return None
        else:
            raw_data = self.users_db.get(user_id)

        if not raw_data:
            return None
            
        # If it's already nested (new format), we need to flatten for UserProfile dataclass
        if 'birth_data' in raw_data:
            bd = raw_data.get('birth_data', {})
            pref = raw_data.get('preferences', {})
            flat_data = {
                "user_id": raw_data.get("user_id"),
                "name": raw_data.get("name"),
                "email": raw_data.get("email"),
                "date_of_birth": bd.get("date_of_birth"),
                "time_of_birth": bd.get("time_of_birth"),
                "place_of_birth": bd.get("place_of_birth"),
                "latitude": bd.get("latitude"),
                "longitude": bd.get("longitude"),
                "timezone": bd.get("timezone"),
                "preferred_system": pref.get("astrology_system", "vedic"),
                "language": pref.get("language", "en"),
                "created_at": raw_data.get("created_at"),
                "last_active": raw_data.get("last_active")
            }
            return UserProfile(**flat_data)
        
        # It's already flat
        return UserProfile(**raw_data)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user data as a dictionary in nested format for API.
        """
        # We can leverage get_user_profile then convert to dict
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
            
        # Transform flat profile to nested dict for API
        nested_data = {
            "user_id": profile.user_id,
            "name": profile.name,
            "email": profile.email,
            "birth_data": {
                "date_of_birth": profile.date_of_birth,
                "time_of_birth": profile.time_of_birth,
                "place_of_birth": profile.place_of_birth,
                "latitude": profile.latitude,
                "longitude": profile.longitude,
                "timezone": profile.timezone or "UTC"
            },
            "preferences": {
                "astrology_system": profile.preferred_system,
                "language": profile.language
            },
            "created_at": profile.created_at.isoformat() if isinstance(profile.created_at, datetime) else profile.created_at,
            "updated_at": profile.last_active.isoformat() if isinstance(profile.last_active, datetime) else profile.last_active
        }
        return nested_data

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user. 
        """
        # Determine if input is nested or flat
        if 'birth_data' in user_data:
            # Nested input (from API)
            user_id = user_data.get("user_id")
            if not user_id: raise ValueError("user_id is required")
            
            # Store it flat for internal consistency or nested for future-proofing?
            # Let's flatten it for now to match DUMMY_USERS structure
            bd = user_data.get('birth_data', {})
            pref = user_data.get('preferences', {})
            flat_data = {
                "user_id": user_id,
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "date_of_birth": bd.get("date_of_birth"),
                "time_of_birth": bd.get("time_of_birth"),
                "place_of_birth": bd.get("place_of_birth"),
                "latitude": bd.get("latitude"),
                "longitude": bd.get("longitude"),
                "timezone": bd.get("timezone"),
                "preferred_system": pref.get("astrology_system", "vedic"),
                "language": pref.get("language", "en"),
                "created_at": datetime.now(),
                "last_active": datetime.now()
            }
            target_data = flat_data
        else:
            # Flat input
            user_id = user_data.get("user_id")
            if not user_id: raise ValueError("user_id is required")
            user_data['created_at'] = user_data.get('created_at', datetime.now())
            user_data['last_active'] = datetime.now()
            target_data = user_data

        if self.use_mongodb:
            self.users_collection.insert_one(target_data)
        else:
            self.users_db[user_id] = target_data
            
        return self.get_user(user_id) # Returns nested

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing user. Handles nested update_data from API.
        """
        # Support nested update_data by flattening it
        final_update = {}
        if 'birth_data' in update_data:
            bd = update_data.pop('birth_data')
            for k, v in bd.items():
                final_update[k] = v
        if 'preferences' in update_data:
            pref = update_data.pop('preferences')
            if 'astrology_system' in pref:
                final_update['preferred_system'] = pref['astrology_system']
            if 'language' in pref:
                final_update['language'] = pref['language']
        
        final_update.update(update_data)
        final_update['last_active'] = datetime.now()
        
        if self.use_mongodb:
            self.users_collection.update_one({"user_id": user_id}, {"$set": final_update})
        else:
            if user_id not in self.users_db: raise ValueError(f"User {user_id} not found")
            self.users_db[user_id].update(final_update)
            
        return self.get_user(user_id)

    def update_last_active(self, user_id: str):
        """Update user's last active timestamp."""
        if self.use_mongodb:
            self.users_collection.update_one({"user_id": user_id}, {"$set": {"last_active": datetime.now()}})
        else:
            if user_id in self.users_db: self.users_db[user_id]['last_active'] = datetime.now()

    def user_exists(self, user_id: str) -> bool:
        """
        Check if user exists in database.
        """
        if self.use_mongodb:
            try:
                count = self.users_collection.count_documents({"user_id": user_id})
                return count > 0
            except Exception as e:
                print(f"[USER] Error checking user existence: {e}")
                return False
        else:
            return user_id in self.users_db


def get_user_manager(mongodb_uri: Optional[str] = None) -> UserManager:
    """
    Factory function to create user manager.
    
    Args:
        mongodb_uri: MongoDB connection string (None = dummy data)
        
    Returns:
        UserManager instance
    """
    import os
    
    # Try to get MongoDB URI from environment if not provided
    if mongodb_uri is None:
        mongodb_uri = os.environ.get('MONGODB_URI')
    
    return UserManager(mongodb_uri=mongodb_uri)


# Testing
if __name__ == "__main__":
    print("=" * 60)
    print("USER MANAGER - Test Suite")
    print("=" * 60)
    print()
    
    # Initialize with dummy data
    manager = get_user_manager()
    
    # Test users
    test_users = ["user001", "user002", "user003", "user999"]
    
    for user_id in test_users:
        print(f"Testing: {user_id}")
        
        if manager.user_exists(user_id):
            profile = manager.get_user_profile(user_id)
            print(f"  [OK] Authenticated")
            print(f"  Name: {profile.name}")
            print(f"  System: {profile.preferred_system}")
            print(f"  Birth data: {'[OK] Complete' if profile.has_birth_data() else '[FAIL] Incomplete'}")
            
            # Test update
            manager.update_last_active(user_id)
            print(f"  Last active updated")
        else:
            print(f"  [FAIL] Not found in database")
        
        print()
    
    print("=" * 60)
    print("[DONE] Tests complete!")
    print("=" * 60)
    print()
    print("Authentication logic:")
    print("  • User in DB -> authenticated")
    print("  • User not in DB -> not authenticated")
    print("  • No subscription checks (handled externally)")