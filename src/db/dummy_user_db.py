# src\db\dummy_user_db.py
"""
Dummy User Database for NakshatraAI
====================================

In-memory user database for development and testing.
Provides the same interface as SQLiteClient without requiring a database file.

This is used when USE_DUMMY_USER_DB=true in configuration.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json


class DummyUserDB:
    """In-memory user database for development/testing."""
    
    def __init__(self):
        """Initialize in-memory storage."""
        self.users: Dict[str, Dict[str, Any]] = {}
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        
        # Pre-populate with sample users
        self._init_sample_users()
        print("[DB] Dummy user database initialized (in-memory)")
    
    def _init_sample_users(self):
        """Create sample users for testing."""
        sample_users = [
            {
                "user_id": "user001",
                "name": "Arjun Kumar",
                "email": "arjun@example.com",
                "birth_date": "1990-05-15",
                "birth_time": "14:30:00",
                "birth_place": "New Delhi, India",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "timezone": "Asia/Kolkata",
                "system": "vedic",
                "language": "hi-lat",
                "birth_chart_cache": None,
                "created_at": "2026-01-01T00:00:00",
                "last_active": datetime.now().isoformat()
            },
            {
                "user_id": "user002",
                "name": "Priya Sharma",
                "email": "priya@example.com",
                "birth_date": "1995-08-22",
                "birth_time": "09:15:00",
                "birth_place": "Mumbai, India",
                "latitude": 19.0760,
                "longitude": 72.8777,
                "timezone": "Asia/Kolkata",
                "system": "vedic",
                "language": "en",
                "birth_chart_cache": None,
                "created_at": "2026-01-15T00:00:00",
                "last_active": datetime.now().isoformat()
            },
            {
                "user_id": "user003",
                "name": "Sophia Anderson",
                "email": "sophia@example.com",
                "birth_date": "1988-12-10",
                "birth_time": "18:45:00",
                "birth_place": "New York, USA",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "America/New_York",
                "system": "western",
                "language": "en",
                "birth_chart_cache": None,
                "created_at": "2026-02-01T00:00:00",
                "last_active": datetime.now().isoformat()
            },
            {
                "user_id": "user011",
                "name": "Test User",
                "email": "test@example.com",
                "birth_date": "1992-03-25",
                "birth_time": "10:30:00",
                "birth_place": "Bangalore, India",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "timezone": "Asia/Kolkata",
                "system": "vedic",
                "language": "hi-lat",
                "birth_chart_cache": None,
                "created_at": "2026-02-01T00:00:00",
                "last_active": datetime.now().isoformat()
            }
        ]
        
        for user in sample_users:
            self.users[user["user_id"]] = user
            self.conversations[user["user_id"]] = []
    
    # =========================================================================
    # USER OPERATIONS
    # =========================================================================
    
    def upsert_user(self, user_data: Dict[str, Any]):
        """
        Insert or Update a user profile.
        
        Args:
            user_data: Dictionary containing user fields
        """
        user_id = user_data.get('user_id')
        if not user_id:
            raise ValueError("user_id is required")
        
        # Convert datetime objects to ISO strings
        processed_data = {}
        for key, value in user_data.items():
            if isinstance(value, datetime):
                processed_data[key] = value.isoformat()
            else:
                processed_data[key] = value
        
        # Update or insert
        if user_id in self.users:
            self.users[user_id].update(processed_data)
        else:
            self.users[user_id] = processed_data
            self.conversations[user_id] = []
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user profile by ID."""
        return self.users.get(user_id)
    
    def user_exists(self, user_id: str) -> bool:
        """Check if user exists."""
        return user_id in self.users
    
    def update_last_active(self, user_id: str):
        """Update last_active timestamp."""
        if user_id in self.users:
            self.users[user_id]['last_active'] = datetime.now().isoformat()
    
    def update_user_chart(self, user_id: str, chart_json: str):
        """Update the cached birth chart for a user."""
        if user_id in self.users:
            self.users[user_id]['birth_chart_cache'] = chart_json
    
    # =========================================================================
    # CONVERSATION OPERATIONS
    # =========================================================================
    
    def add_message(self, user_id: str, role: str, content: str, intent: str = None):
        """Log a message in the conversation history."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        message = {
            "role": role,
            "content": content,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        }
        
        self.conversations[user_id].append(message)
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get recent conversation history for context.
        
        Returns list of dicts: {'role': 'user', 'content': '...'}
        """
        if user_id not in self.conversations:
            return []
        
        # Get last N messages
        messages = self.conversations[user_id][-limit:]
        
        # Return in format expected by orchestrator
        return [{"role": msg["role"], "content": msg["content"]} for msg in messages]
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users (for admin/debugging)."""
        return list(self.users.values())
    
    def clear_conversations(self, user_id: str):
        """Clear conversation history for a user."""
        if user_id in self.conversations:
            self.conversations[user_id] = []
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        total_messages = sum(len(convs) for convs in self.conversations.values())
        return {
            "total_users": len(self.users),
            "total_messages": total_messages
        }
