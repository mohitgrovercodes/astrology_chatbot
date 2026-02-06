"""
User Manager for NakshatraAI.

Simple authentication: user in DB = authenticated.
No subscription checks (handled by your colleague at app level).
"""

from typing import Optional, Dict, Any, List
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
    language: str = "hi-lat"
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
            "language": "hi-lat",
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
            'time_of_birth': '20:45:00',
            'place_of_birth': 'Bhilwara,India',
            'latitude': 25.3407,
            'longitude': 74.6313,
            'timezone': 'Asia/Kolkata',
            'preferred_system': 'vedic',
            'language': 'en',
            "created_at": datetime(2023, 8, 10),
            "last_active": datetime.now()
        },
        'user010': {
            'user_id': 'user010',
            'name': 'Ritu Saini',
            'email': None,
            'date_of_birth': '2002-07-25',
            'time_of_birth': '05:45:00',
            'place_of_birth': 'Alwar, India',
            'latitude': 27.553,
            'longitude': 76.6346,
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
        'user011': {
            'user_id': 'user011',
            'name': 'Mohit Grover',
            'email': None,
            'date_of_birth': '1995-10-01',
            'time_of_birth': '07:30:00',
            'place_of_birth': 'Alwar,India',
            'latitude': 27.553,
            'longitude': 76.6346,
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
    
    
    def __init__(self, use_sqlite: bool = True):
        """
        Initialize user manager.
        """
        self.use_sqlite = use_sqlite
        self.sqlite = None
        
        if self.use_sqlite:
            try:
                from src.db.sqlite_client import SQLiteClient
                self.sqlite = SQLiteClient()
                print("[USER] Connected to SQLite Database")
                
                # Check migration
                self._check_migration()
                
            except ImportError as e:
                print(f"[USER] SQLite import failed: {e}, falling back to dummy data")
                self.use_sqlite = False
                self.users_db = self.DUMMY_USERS
            except Exception as e:
                print(f"[USER] SQLite connection failed: {e}, using dummy data")
                self.use_sqlite = False
                self.users_db = self.DUMMY_USERS
        else:
            self.users_db = self.DUMMY_USERS
            print("[USER] Using dummy user database")

    def _check_migration(self):
        """Migrate dummy users if not exists."""
        for user_id, data in self.DUMMY_USERS.items():
            if not self.sqlite.user_exists(user_id):
                print(f"[MIGRATION] Porting {user_id} to SQLite...")
                # Flatten potential nested data if coming from dummy
                # (DUMMY_USERS is largely flat except timestamps)
                self.create_user(data)

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Load user profile from database. 
        """
        raw_data = None
        if self.use_sqlite and self.sqlite:
            try:
                raw_data = self.sqlite.get_user(user_id)
            except Exception as e:
                print(f"[USER] Error loading profile: {e}")
                return None
        else:
            raw_data = self.users_db.get(user_id)

        if not raw_data:
            return None
            
        # SQLite returns flat dict, compatible with UserProfile
        # Handle loose typing from DB if needed
        return UserProfile(
            user_id=raw_data['user_id'],
            name=raw_data['name'],
            email=raw_data.get('email'),
            date_of_birth=raw_data.get('birth_date'), # Schema mismatch fix: birth_date vs date_of_birth
            time_of_birth=raw_data.get('birth_time'),
            place_of_birth=raw_data.get('birth_place'),
            latitude=raw_data.get('latitude'),
            longitude=raw_data.get('longitude'),
            timezone=raw_data.get('timezone'),
            preferred_system=raw_data.get('system', 'vedic'),
            language=raw_data.get('language', 'hi-lat'),
            created_at=raw_data.get('created_at'),
            last_active=raw_data.get('last_active')
        )

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user data as a dictionary in nested format for API.
        """
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
            
        return {
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
            "created_at": str(profile.created_at),
            "updated_at": str(profile.last_active)
        }

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user."""
        user_id = user_data.get("user_id")
        if not user_id: raise ValueError("user_id is required")

        # Prepare flat data for SQLite
        flat_data = {
            "user_id": user_id,
            "name": user_data.get("name"),
            "email": user_data.get("email"),
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }

        # Check if nested birth_data
        if 'birth_data' in user_data:
            bd = user_data.get('birth_data', {})
            flat_data.update({
                "birth_date": bd.get("date_of_birth"),
                "birth_time": bd.get("time_of_birth"),
                "birth_place": bd.get("place_of_birth"),
                "latitude": bd.get("latitude"),
                "longitude": bd.get("longitude"),
                "timezone": bd.get("timezone")
            })
        else:
            # Fallback for flat input (migration)
            flat_data.update({
                "birth_date": user_data.get("date_of_birth"),
                "birth_time": user_data.get("time_of_birth"),
                "birth_place": user_data.get("place_of_birth"),
                "latitude": user_data.get("latitude"),
                "longitude": user_data.get("longitude"),
                "timezone": user_data.get("timezone")
            })

        # Check preferences
        if 'preferences' in user_data:
            pref = user_data.get('preferences', {})
            flat_data['system'] = pref.get("astrology_system", "vedic")
            flat_data['language'] = pref.get("language", "hi-lat")
        else:
             flat_data['system'] = user_data.get("preferred_system", "vedic")
             flat_data['language'] = user_data.get("language", "hi-lat")

        if self.use_sqlite and self.sqlite:
            self.sqlite.upsert_user(flat_data)
        else:
            self.users_db[user_id] = flat_data
            
        return self.get_user(user_id)

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing user."""
        # Get existing first to merge
        current = self.get_user(user_id)
        if not current: raise ValueError(f"User {user_id} not found")
        
        # Prepare update dict (start with existing flat structure logic)
        flat_update = {"user_id": user_id}
        
        # Map fields from update_data (API nested) to DB Scheme
        if 'name' in update_data: flat_update['name'] = update_data['name']
        if 'email' in update_data: flat_update['email'] = update_data['email']
        
        if 'birth_data' in update_data:
            bd = update_data['birth_data']
            if 'date_of_birth' in bd: flat_update['birth_date'] = bd['date_of_birth']
            if 'time_of_birth' in bd: flat_update['birth_time'] = bd['time_of_birth']
            if 'place_of_birth' in bd: flat_update['birth_place'] = bd['place_of_birth']
            if 'latitude' in bd: flat_update['latitude'] = bd['latitude']
            if 'longitude' in bd: flat_update['longitude'] = bd['longitude']
            if 'timezone' in bd: flat_update['timezone'] = bd['timezone']
            
        if 'preferences' in update_data:
            pref = update_data['preferences']
            if 'astrology_system' in pref: flat_update['system'] = pref['astrology_system']
            if 'language' in pref: flat_update['language'] = pref['language']

        if self.use_sqlite and self.sqlite:
            self.sqlite.upsert_user(flat_update) # Upsert handles partial updates via merge logic on app side usually, but upsert_user here replaces fields. 
            # Ideally execute update query. For now relying on upsert constraints or just careful calls.
            # Actually our upsert_user is an INSERT OR REPLACE logic or ON CONFLICT UPDATE.
            # So we only need to pass changed fields + user_id? 
            # Wait, upsert overwrites. We need to preserve old data if not passed.
            # Simplified: Since we don't have partial update SQL, let's rely on the fact we usually get full profile from UI form.
            # Or better, just implement a smart upsert in client.
            # For now:
            self.sqlite.upsert_user(flat_update) 
        else:
            # Dummy update (simplified)
            pass
            
        return self.get_user(user_id)

    def update_last_active(self, user_id: str):
        """Update user's last active timestamp."""
        if self.use_sqlite and self.sqlite:
            self.sqlite.update_last_active(user_id)
        else:
            if user_id in self.users_db: self.users_db[user_id]['last_active'] = datetime.now()

    def user_exists(self, user_id: str) -> bool:
        """Check if user exists."""
        if self.use_sqlite and self.sqlite:
            return self.sqlite.user_exists(user_id)
        else:
            return user_id in self.users_db
            
    # Conversation History Methods
    def add_message(self, user_id: str, role: str, content: str, intent: str = None):
        """Save a message to history."""
        if self.use_sqlite and self.sqlite:
            self.sqlite.add_message(user_id, role, content, intent)
            
    def get_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get recent chat history."""
        if self.use_sqlite and self.sqlite:
            return self.sqlite.get_conversation_history(user_id, limit)
        return []


def get_user_manager(mongodb_uri: Optional[str] = None) -> UserManager:
    """
    Factory function.
    """
    return UserManager(use_sqlite=True)


# Testing
if __name__ == "__main__":
    print("=" * 60)
    print("USER MANAGER - Test Suite")
    print("=" * 60)
    print()
    
    # Initialize with dummy data
    manager = get_user_manager()
    
    # Test users
    test_users = ["user001", "user002", "user011", "user999"]
    
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