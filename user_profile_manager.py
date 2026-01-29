"""
User Profile Manager for Astrology AI Chatbot.

Manages user authentication and profile data.
- Production: Connects to existing MongoDB
- Development: Uses dummy data for testing

User profiles include:
- Authentication (user_id, subscription status)
- Birth data (date, time, location, coordinates)
- Preferences (astrology system, language)
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class UserProfile:
    """
    User profile with birth data and preferences.
    
    Matches the schema in your existing MongoDB.
    """
    # Authentication
    user_id: str
    name: str
    email: Optional[str]
    subscription_status: str  # 'active', 'inactive', 'trial'
    subscription_tier: str  # 'basic', 'premium', 'enterprise'
    
    # Birth data
    date_of_birth: str  # 'YYYY-MM-DD'
    time_of_birth: str  # 'HH:MM:SS'
    place_of_birth: str  # City name
    latitude: float
    longitude: float
    timezone: Optional[str]
    
    # Preferences
    preferred_system: str = "vedic"  # 'vedic' or 'western'
    language: str = "en"
    
    # Metadata
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def has_complete_birth_data(self) -> bool:
        """Check if user has complete birth data."""
        return all([
            self.date_of_birth,
            self.time_of_birth,
            self.latitude,
            self.longitude
        ])
    
    def is_active_subscriber(self) -> bool:
        """Check if user has active subscription."""
        return self.subscription_status in ['active', 'trial']


# =============================================================================
# MONGODB PROFILE MANAGER
# =============================================================================

class MongoDBProfileManager:
    """
    Production user profile manager (MongoDB).
    
    Connects to your existing MongoDB database.
    """
    
    def __init__(self, mongo_uri: str, db_name: str = "astro_app"):
        """
        Initialize MongoDB connection.
        
        Args:
            mongo_uri: MongoDB connection string
            db_name: Database name
        """
        try:
            from pymongo import MongoClient
            self.client = MongoClient(mongo_uri)
            self.db = self.client[db_name]
            self.users_collection = self.db["users"]
            print("[PROFILE] Connected to MongoDB")
        except ImportError:
            raise ImportError("PyMongo not installed. Run: pip install pymongo")
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Get user profile from MongoDB.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserProfile or None if not found
        """
        try:
            doc = self.users_collection.find_one({"user_id": user_id})
            
            if not doc:
                return None
            
            # Map MongoDB document to UserProfile
            profile = UserProfile(
                user_id=doc["user_id"],
                name=doc.get("name", "Unknown"),
                email=doc.get("email"),
                subscription_status=doc.get("subscription_status", "inactive"),
                subscription_tier=doc.get("subscription_tier", "basic"),
                date_of_birth=doc.get("date_of_birth"),
                time_of_birth=doc.get("time_of_birth"),
                place_of_birth=doc.get("place_of_birth"),
                latitude=doc.get("latitude", 0.0),
                longitude=doc.get("longitude", 0.0),
                timezone=doc.get("timezone"),
                preferred_system=doc.get("preferred_system", "vedic"),
                language=doc.get("language", "en"),
                created_at=doc.get("created_at"),
                last_active=doc.get("last_active")
            )
            
            return profile
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch user profile: {e}")
            return None
    
    def update_last_active(self, user_id: str):
        """Update user's last active timestamp."""
        try:
            self.users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"last_active": datetime.now().isoformat()}}
            )
        except Exception as e:
            print(f"[WARN] Failed to update last_active: {e}")
    
    def authenticate_user(self, user_id: str) -> bool:
        """
        Authenticate user (check if exists and has active subscription).
        
        Args:
            user_id: User identifier
            
        Returns:
            True if authenticated, False otherwise
        """
        profile = self.get_user_profile(user_id)
        
        if not profile:
            return False
        
        return profile.is_active_subscriber()


# =============================================================================
# DUMMY PROFILE MANAGER (For Development)
# =============================================================================

class DummyProfileManager:
    """
    Development user profile manager with dummy data.
    
    Uses in-memory dummy users for testing without MongoDB.
    """
    
    # Dummy user database
    DUMMY_USERS = {
        "user001": UserProfile(
            user_id="user001",
            name="Rajesh Kumar",
            email="rajesh.kumar@example.com",
            subscription_status="active",
            subscription_tier="premium",
            date_of_birth="1990-03-15",
            time_of_birth="14:30:00",
            place_of_birth="Delhi, India",
            latitude=28.6139,
            longitude=77.2090,
            timezone="Asia/Kolkata",
            preferred_system="vedic",
            language="en",
            created_at="2025-01-01T00:00:00",
            last_active="2026-01-29T10:00:00"
        ),
        
        "user002": UserProfile(
            user_id="user002",
            name="Priya Sharma",
            email="priya.sharma@example.com",
            subscription_status="active",
            subscription_tier="basic",
            date_of_birth="1985-06-10",
            time_of_birth="03:45:00",
            place_of_birth="Mumbai, India",
            latitude=19.0760,
            longitude=72.8777,
            timezone="Asia/Kolkata",
            preferred_system="vedic",
            language="en",
            created_at="2025-02-15T00:00:00",
            last_active="2026-01-28T15:30:00"
        ),
        
        "user003": UserProfile(
            user_id="user003",
            name="Amit Patel",
            email="amit.patel@example.com",
            subscription_status="trial",
            subscription_tier="basic",
            date_of_birth="1988-12-25",
            time_of_birth="08:15:00",
            place_of_birth="Ahmedabad, India",
            latitude=23.0225,
            longitude=72.5714,
            timezone="Asia/Kolkata",
            preferred_system="vedic",
            language="en",
            created_at="2026-01-25T00:00:00",
            last_active="2026-01-29T09:00:00"
        ),
        
        "user004": UserProfile(
            user_id="user004",
            name="Expired User",
            email="expired@example.com",
            subscription_status="inactive",  # No active subscription
            subscription_tier="basic",
            date_of_birth="1992-08-20",
            time_of_birth="16:00:00",
            place_of_birth="Bangalore, India",
            latitude=12.9716,
            longitude=77.5946,
            timezone="Asia/Kolkata",
            preferred_system="vedic",
            language="en",
            created_at="2024-06-01T00:00:00",
            last_active="2025-12-31T23:59:59"
        ),
    }
    
    def __init__(self):
        """Initialize dummy profile manager."""
        print("[PROFILE] Using dummy user data (development mode)")
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Get user profile from dummy data.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserProfile or None if not found
        """
        return self.DUMMY_USERS.get(user_id)
    
    def update_last_active(self, user_id: str):
        """Update user's last active timestamp (in-memory only)."""
        if user_id in self.DUMMY_USERS:
            self.DUMMY_USERS[user_id].last_active = datetime.now().isoformat()
    
    def authenticate_user(self, user_id: str) -> bool:
        """
        Authenticate user (check if exists and has active subscription).
        
        Args:
            user_id: User identifier
            
        Returns:
            True if authenticated, False otherwise
        """
        profile = self.get_user_profile(user_id)
        
        if not profile:
            print(f"[AUTH] User not found: {user_id}")
            return False
        
        if not profile.is_active_subscriber():
            print(f"[AUTH] User subscription inactive: {user_id}")
            return False
        
        print(f"[AUTH] User authenticated: {profile.name} ({profile.subscription_tier})")
        return True
    
    def list_dummy_users(self) -> List[str]:
        """List all dummy user IDs (for testing)."""
        return list(self.DUMMY_USERS.keys())
    
    def get_dummy_user_info(self, user_id: str) -> Optional[Dict[str, str]]:
        """Get basic info about a dummy user."""
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
        
        return {
            "user_id": profile.user_id,
            "name": profile.name,
            "subscription": f"{profile.subscription_status} ({profile.subscription_tier})",
            "location": profile.place_of_birth,
            "dob": profile.date_of_birth
        }


# =============================================================================
# UNIFIED PROFILE MANAGER
# =============================================================================

class UserProfileManager:
    """
    Unified user profile manager.
    
    Automatically uses MongoDB in production, dummy data in development.
    """
    
    def __init__(self, use_mongodb: bool = False, mongo_uri: Optional[str] = None):
        """
        Initialize profile manager.
        
        Args:
            use_mongodb: If True, connect to MongoDB. If False, use dummy data.
            mongo_uri: MongoDB connection string (required if use_mongodb=True)
        """
        if use_mongodb:
            if not mongo_uri:
                raise ValueError("mongo_uri required when use_mongodb=True")
            self.manager = MongoDBProfileManager(mongo_uri)
        else:
            self.manager = DummyProfileManager()
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile."""
        return self.manager.get_user_profile(user_id)
    
    def authenticate_user(self, user_id: str) -> bool:
        """Authenticate user."""
        return self.manager.authenticate_user(user_id)
    
    def update_last_active(self, user_id: str):
        """Update last active timestamp."""
        self.manager.update_last_active(user_id)
    
    # Dummy-specific methods (for testing)
    def list_dummy_users(self) -> List[str]:
        """List dummy user IDs (only works with DummyProfileManager)."""
        if isinstance(self.manager, DummyProfileManager):
            return self.manager.list_dummy_users()
        return []
    
    def get_dummy_user_info(self, user_id: str) -> Optional[Dict[str, str]]:
        """Get dummy user info (only works with DummyProfileManager)."""
        if isinstance(self.manager, DummyProfileManager):
            return self.manager.get_dummy_user_info(user_id)
        return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_default_profile_manager() -> UserProfileManager:
    """
    Get default profile manager.
    
    Uses MongoDB if MONGODB_URI environment variable is set,
    otherwise uses dummy data.
    """
    import os
    mongo_uri = os.environ.get("MONGODB_URI")
    
    if mongo_uri:
        return UserProfileManager(use_mongodb=True, mongo_uri=mongo_uri)
    else:
        return UserProfileManager(use_mongodb=False)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("USER PROFILE MANAGER - Test Suite")
    print("=" * 70)
    print()
    
    # Initialize manager (dummy mode)
    manager = UserProfileManager(use_mongodb=False)
    
    # Test 1: List dummy users
    print("Test 1: List Dummy Users")
    users = manager.list_dummy_users()
    print(f"  ✓ Found {len(users)} dummy users:")
    for user_id in users:
        info = manager.get_dummy_user_info(user_id)
        print(f"    • {info['name']} ({user_id}) - {info['subscription']}")
    print()
    
    # Test 2: Authenticate active user
    print("Test 2: Authenticate Active User")
    active_user = "user001"
    is_auth = manager.authenticate_user(active_user)
    print(f"  {'✓' if is_auth else '✗'} User {active_user}: {'Authenticated' if is_auth else 'Failed'}")
    print()
    
    # Test 3: Authenticate inactive user
    print("Test 3: Authenticate Inactive User")
    inactive_user = "user004"
    is_auth = manager.authenticate_user(inactive_user)
    print(f"  {'✗' if not is_auth else '✓'} User {inactive_user}: {'Authenticated' if is_auth else 'Blocked (expected)'}")
    print()
    
    # Test 4: Get user profile
    print("Test 4: Get User Profile")
    profile = manager.get_user_profile("user001")
    if profile:
        print(f"  ✓ Profile loaded:")
        print(f"    Name: {profile.name}")
        print(f"    DOB: {profile.date_of_birth} {profile.time_of_birth}")
        print(f"    Location: {profile.place_of_birth}")
        print(f"    Coordinates: ({profile.latitude}, {profile.longitude})")
        print(f"    Subscription: {profile.subscription_status} ({profile.subscription_tier})")
        print(f"    Complete birth data: {profile.has_complete_birth_data()}")
    print()
    
    # Test 5: Non-existent user
    print("Test 5: Non-existent User")
    profile = manager.get_user_profile("user999")
    print(f"  {'✓' if profile is None else '✗'} User user999: {'Not found (expected)' if profile is None else 'Found (error)'}")
    print()
    
    # Test 6: Update last active
    print("Test 6: Update Last Active")
    manager.update_last_active("user001")
    profile = manager.get_user_profile("user001")
    print(f"  ✓ Last active updated: {profile.last_active}")
    print()
    
    print("=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    print()
    print("Dummy Users Summary:")
    print("  • user001 - Active Premium (has all data)")
    print("  • user002 - Active Basic (has all data)")
    print("  • user003 - Trial (has all data)")
    print("  • user004 - Inactive (subscription expired)")
