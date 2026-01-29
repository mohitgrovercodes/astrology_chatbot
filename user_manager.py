"""
User Management System for Astrology Chatbot.

Handles:
- User authentication (subscription verification)
- User profile management
- Birth data retrieval from MongoDB
- Personalization context

Current: Dummy data
Future: Real MongoDB integration
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


# =============================================================================
# USER DATA STRUCTURES
# =============================================================================

@dataclass
class UserProfile:
    """
    User profile loaded from database.
    
    This contains all user information needed for:
    - Authentication
    - Personalization
    - Automatic birth chart calculations
    """
    # Identity
    user_id: str
    name: str
    email: str
    
    # Subscription
    subscription_status: str  # 'active', 'expired', 'trial', 'free'
    subscription_plan: str    # 'premium', 'basic', etc.
    subscription_expires: Optional[datetime]
    
    # Birth Data
    birth_date: str           # 'YYYY-MM-DD'
    birth_time: str           # 'HH:MM:SS'
    birth_location: str       # Human-readable location
    latitude: float
    longitude: float
    timezone: Optional[str]   # 'Asia/Kolkata', etc.
    
    # Preferences
    preferred_system: str     # 'vedic' or 'western'
    language: str             # 'en', 'hi', etc.
    
    # Metadata
    created_at: datetime
    last_login: datetime
    
    @property
    def is_subscriber(self) -> bool:
        """Check if user has active subscription."""
        return self.subscription_status == 'active'
    
    @property
    def is_trial(self) -> bool:
        """Check if user is on trial."""
        return self.subscription_status == 'trial'
    
    @property
    def has_birth_data(self) -> bool:
        """Check if user has complete birth data."""
        return all([
            self.birth_date,
            self.birth_time,
            self.latitude,
            self.longitude
        ])
    
    @property
    def display_name(self) -> str:
        """Get display name for personalization."""
        return self.name.split()[0] if self.name else "Friend"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "subscription_status": self.subscription_status,
            "subscription_plan": self.subscription_plan,
            "subscription_expires": self.subscription_expires.isoformat() if self.subscription_expires else None,
            "birth_date": self.birth_date,
            "birth_time": self.birth_time,
            "birth_location": self.birth_location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "preferred_system": self.preferred_system,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat(),
        }


# =============================================================================
# DUMMY DATABASE (For Testing)
# =============================================================================

# Simulates MongoDB collection
DUMMY_USERS_DB = {
    "user001": {
        "user_id": "user001",
        "name": "Arjun Kumar",
        "email": "arjun@example.com",
        "subscription_status": "active",
        "subscription_plan": "premium",
        "subscription_expires": datetime(2026, 12, 31),
        "birth_date": "1990-03-15",
        "birth_time": "14:30:00",
        "birth_location": "Jaipur, Rajasthan, India",
        "latitude": 26.9124,
        "longitude": 75.7873,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic",
        "language": "en",
        "created_at": datetime(2024, 1, 15),
        "last_login": datetime(2026, 1, 29),
    },
    
    "user002": {
        "user_id": "user002",
        "name": "Priya Sharma",
        "email": "priya@example.com",
        "subscription_status": "active",
        "subscription_plan": "basic",
        "subscription_expires": datetime(2026, 6, 30),
        "birth_date": "1985-07-22",
        "birth_time": "08:15:00",
        "birth_location": "Mumbai, Maharashtra, India",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic",
        "language": "hi",
        "created_at": datetime(2023, 8, 10),
        "last_login": datetime(2026, 1, 28),
    },
    
    "user003": {
        "user_id": "user003",
        "name": "Rahul Verma",
        "email": "rahul@example.com",
        "subscription_status": "expired",
        "subscription_plan": "basic",
        "subscription_expires": datetime(2025, 12, 31),
        "birth_date": "1992-11-05",
        "birth_time": "19:45:00",
        "birth_location": "Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic",
        "language": "en",
        "created_at": datetime(2023, 5, 20),
        "last_login": datetime(2026, 1, 20),
    },
    
    "user004": {
        "user_id": "user004",
        "name": "Sophia Anderson",
        "email": "sophia@example.com",
        "subscription_status": "active",
        "subscription_plan": "premium",
        "subscription_expires": datetime(2027, 3, 15),
        "birth_date": "1988-05-10",
        "birth_time": "15:20:00",
        "birth_location": "New York, NY, USA",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "timezone": "America/New_York",
        "preferred_system": "western",
        "language": "en",
        "created_at": datetime(2024, 3, 1),
        "last_login": datetime(2026, 1, 29),
    },
    
    "user005": {
        "user_id": "user005",
        "name": "Guest User",
        "email": "guest@example.com",
        "subscription_status": "free",
        "subscription_plan": "free",
        "subscription_expires": None,
        "birth_date": None,
        "birth_time": None,
        "birth_location": None,
        "latitude": None,
        "longitude": None,
        "timezone": None,
        "preferred_system": "vedic",
        "language": "en",
        "created_at": datetime(2026, 1, 29),
        "last_login": datetime(2026, 1, 29),
    },
}


# =============================================================================
# USER MANAGER
# =============================================================================

class UserManager:
    """
    User management with authentication and profile loading.
    
    Current: Uses dummy data
    Future: Real MongoDB connection
    """
    
    def __init__(self, use_mongodb: bool = False, mongo_uri: Optional[str] = None):
        """
        Initialize user manager.
        
        Args:
            use_mongodb: If True, connect to real MongoDB (not implemented yet)
            mongo_uri: MongoDB connection URI (for future use)
        """
        self.use_mongodb = use_mongodb
        
        if use_mongodb:
            # Future: Real MongoDB connection
            raise NotImplementedError("MongoDB integration coming in Phase 7")
        else:
            # Use dummy data
            self.users_db = DUMMY_USERS_DB
            print("[USER MANAGER] Using dummy user database")
    
    def authenticate_user(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        Authenticate user and check subscription status.
        
        Args:
            user_id: User identifier
            
        Returns:
            Tuple of (is_authorized, error_message)
            - (True, None) if authorized
            - (False, error_message) if not authorized
        """
        # Check if user exists
        if user_id not in self.users_db:
            return False, "User not found. Please check your login credentials."
        
        # Load user profile
        profile = self.load_user_profile(user_id)
        
        if not profile:
            return False, "Failed to load user profile."
        
        # Check subscription status
        if profile.subscription_status == "active":
            return True, None
        
        elif profile.subscription_status == "trial":
            return True, None  # Allow trial users
        
        elif profile.subscription_status == "expired":
            return False, f"""Your subscription has expired on {profile.subscription_expires.strftime('%B %d, %Y')}.

Please renew your subscription to continue using the Astrology AI Chatbot.

Visit your account settings to renew or upgrade your plan."""
        
        elif profile.subscription_status == "free":
            return False, """This feature is available for premium subscribers only.

Upgrade to a premium plan to access:
• Unlimited birth chart calculations
• AI-powered astrological interpretations
• Personalized dasha predictions
• Priority support

Visit your account settings to upgrade."""
        
        else:
            return False, "Unknown subscription status. Please contact support."
    
    def load_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Load user profile from database.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserProfile object or None if not found
        """
        if user_id not in self.users_db:
            return None
        
        user_data = self.users_db[user_id]
        
        # Convert to UserProfile
        profile = UserProfile(
            user_id=user_data["user_id"],
            name=user_data["name"],
            email=user_data["email"],
            subscription_status=user_data["subscription_status"],
            subscription_plan=user_data["subscription_plan"],
            subscription_expires=user_data["subscription_expires"],
            birth_date=user_data["birth_date"],
            birth_time=user_data["birth_time"],
            birth_location=user_data["birth_location"],
            latitude=user_data["latitude"],
            longitude=user_data["longitude"],
            timezone=user_data["timezone"],
            preferred_system=user_data["preferred_system"],
            language=user_data["language"],
            created_at=user_data["created_at"],
            last_login=user_data["last_login"],
        )
        
        return profile
    
    def update_last_login(self, user_id: str):
        """Update user's last login timestamp."""
        if user_id in self.users_db:
            self.users_db[user_id]["last_login"] = datetime.now()
    
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get user context for personalization.
        
        Returns dictionary with:
        - name, display_name
        - birth_data (if available)
        - preferences
        - subscription info
        """
        profile = self.load_user_profile(user_id)
        
        if not profile:
            return {}
        
        context = {
            "user_id": profile.user_id,
            "name": profile.name,
            "display_name": profile.display_name,
            "has_birth_data": profile.has_birth_data,
            "preferred_system": profile.preferred_system,
            "is_subscriber": profile.is_subscriber,
            "subscription_plan": profile.subscription_plan,
        }
        
        # Add birth data if available
        if profile.has_birth_data:
            context["birth_data"] = {
                "date": profile.birth_date,
                "time": profile.birth_time,
                "location": profile.birth_location,
                "latitude": profile.latitude,
                "longitude": profile.longitude,
                "timezone": profile.timezone,
            }
        
        return context


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_user_manager() -> UserManager:
    """Get default user manager (dummy data for now)."""
    return UserManager(use_mongodb=False)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("USER MANAGEMENT SYSTEM - Test Suite")
    print("=" * 70)
    print()
    
    # Initialize manager
    manager = get_user_manager()
    
    # Test users
    test_users = [
        ("user001", "Arjun Kumar", True, "Active premium"),
        ("user002", "Priya Sharma", True, "Active basic"),
        ("user003", "Rahul Verma", False, "Expired subscription"),
        ("user004", "Sophia Anderson", True, "Active premium (Western)"),
        ("user005", "Guest User", False, "Free account"),
        ("user999", "Unknown", False, "User not found"),
    ]
    
    for user_id, name, should_pass, description in test_users:
        print(f"Testing: {name} ({user_id})")
        print(f"Expected: {description}")
        
        # Authenticate
        is_auth, error_msg = manager.authenticate_user(user_id)
        
        if is_auth:
            print("✅ Authenticated")
            
            # Load profile
            profile = manager.load_user_profile(user_id)
            print(f"   Name: {profile.name}")
            print(f"   Plan: {profile.subscription_plan}")
            print(f"   Birth Data: {'✓ Complete' if profile.has_birth_data else '✗ Missing'}")
            
            if profile.has_birth_data:
                print(f"   Location: {profile.birth_location}")
                print(f"   Date: {profile.birth_date} at {profile.birth_time}")
            
            # Get context
            context = manager.get_user_context(user_id)
            print(f"   Display Name: {context['display_name']}")
            print(f"   Preferred System: {context['preferred_system']}")
        else:
            print("❌ Not Authenticated")
            if error_msg:
                print(f"   Reason: {error_msg.split(chr(10))[0]}...")  # First line only
        
        print()
    
    print("=" * 70)
    print("✅ User management tests complete!")
    print("=" * 70)
    print()
    print("📊 Summary:")
    print(f"  Total Users: {len(DUMMY_USERS_DB)}")
    print(f"  Active Subscribers: {sum(1 for u in DUMMY_USERS_DB.values() if u['subscription_status'] == 'active')}")
    print(f"  With Birth Data: {sum(1 for u in DUMMY_USERS_DB.values() if u['birth_date'])}")
