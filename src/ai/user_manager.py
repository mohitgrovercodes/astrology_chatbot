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
        "user003": {
            "user_id": "user005",
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
        
        Args:
            user_id: User identifier
            
        Returns:
            UserProfile if user exists, None otherwise
        """
        if self.use_mongodb:
            try:
                doc = self.users_collection.find_one({"user_id": user_id})
                if not doc:
                    return None
                
                return UserProfile(
                    user_id=doc.get('user_id'),
                    name=doc.get('name', 'User'),
                    email=doc.get('email'),
                    date_of_birth=doc.get('date_of_birth'),
                    time_of_birth=doc.get('time_of_birth'),
                    place_of_birth=doc.get('place_of_birth'),
                    latitude=doc.get('latitude'),
                    longitude=doc.get('longitude'),
                    timezone=doc.get('timezone'),
                    preferred_system=doc.get('preferred_system', 'vedic'),
                    language=doc.get('language', 'en'),
                    created_at=doc.get('created_at'),
                    last_active=doc.get('last_active')
                )
            except Exception as e:
                print(f"[USER] Error loading profile: {e}")
                return None
        else:
            # Dummy data
            if user_id not in self.users_db:
                return None
            
            data = self.users_db[user_id]
            return UserProfile(**data)
    
    def update_last_active(self, user_id: str):
        """Update user's last active timestamp."""
        if self.use_mongodb:
            try:
                self.users_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"last_active": datetime.now()}}
                )
            except Exception as e:
                print(f"[USER] Error updating last_active: {e}")
        else:
            if user_id in self.users_db:
                self.users_db[user_id]['last_active'] = datetime.now()
    
    def user_exists(self, user_id: str) -> bool:
        """
        Check if user exists in database.
        
        This is the ONLY authentication check:
        - User in DB → authenticated
        - User not in DB → not authenticated
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user exists, False otherwise
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
            print(f"  ✓ Authenticated")
            print(f"  Name: {profile.name}")
            print(f"  System: {profile.preferred_system}")
            print(f"  Birth data: {'✓ Complete' if profile.has_birth_data() else '✗ Incomplete'}")
            
            # Test update
            manager.update_last_active(user_id)
            print(f"  Last active updated")
        else:
            print(f"  ✗ Not found in database")
        
        print()
    
    print("=" * 60)
    print("✅ Tests complete!")
    print("=" * 60)
    print()
    print("Authentication logic:")
    print("  • User in DB → authenticated")
    print("  • User not in DB → not authenticated")
    print("  • No subscription checks (handled externally)")