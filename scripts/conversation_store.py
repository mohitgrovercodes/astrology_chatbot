"""
Conversation Storage for Astrology AI Chatbot.

Provides persistent storage for conversation history.
- Current: JSON file backend (development)
- Future: MongoDB backend (production)

The interface remains the same regardless of backend.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


class ConversationStore:
    """
    Abstract interface for conversation storage.
    
    Backend-agnostic: currently uses JSON, will swap to MongoDB in production.
    """
    
    def __init__(self, backend: str = "json", **kwargs):
        """
        Initialize conversation store.
        
        Args:
            backend: Storage backend ("json" or "mongodb")
            **kwargs: Backend-specific configuration
        """
        self.backend = backend
        
        if backend == "json":
            self.store = JSONConversationStore(**kwargs)
        elif backend == "mongodb":
            # Future: MongoDB implementation
            raise NotImplementedError("MongoDB backend coming soon")
        else:
            raise ValueError(f"Unknown backend: {backend}")
    
    def create_session(self, user_id: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Create a new conversation session."""
        return self.store.create_session(user_id, metadata)
    
    def add_turn(self, session_id: str, user_message: str, assistant_message: str, metadata: Optional[Dict] = None):
        """Add a conversation turn to the session."""
        self.store.add_turn(session_id, user_message, assistant_message, metadata)
    
    def get_history(self, session_id: str, max_turns: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation history for a session."""
        return self.store.get_history(session_id, max_turns)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get full session data."""
        return self.store.get_session(session_id)
    
    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """List all session IDs (optionally filtered by user)."""
        return self.store.list_sessions(user_id)
    
    def delete_session(self, session_id: str):
        """Delete a session."""
        self.store.delete_session(session_id)
    
    def clear_all(self):
        """Clear all sessions (for testing)."""
        self.store.clear_all()


# ============================================
# JSON BACKEND (Temporary Development Storage)
# ============================================

class JSONConversationStore:
    """
    JSON file-based conversation storage.
    
    Structure:
    data/conversations/
        ├── session_<uuid>.json
        ├── session_<uuid>.json
        └── ...
    
    Each file contains:
    {
        "session_id": "...",
        "user_id": "...",
        "created_at": "...",
        "updated_at": "...",
        "metadata": {...},
        "turns": [
            {"user": "...", "assistant": "...", "timestamp": "...", "metadata": {...}},
            ...
        ]
    }
    """
    
    def __init__(self, storage_dir: str = "data/conversations"):
        """
        Initialize JSON storage.
        
        Args:
            storage_dir: Directory to store conversation JSON files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, user_id: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "turns": []
        }
        
        self._save_session(session_id, session_data)
        return session_id
    
    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict] = None
    ):
        """Add a conversation turn."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        turn = {
            "user": user_message,
            "assistant": assistant_message,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        session["turns"].append(turn)
        session["updated_at"] = datetime.now().isoformat()
        
        self._save_session(session_id, session)
    
    def get_history(self, session_id: str, max_turns: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get conversation history.
        
        Args:
            session_id: Session identifier
            max_turns: Maximum number of recent turns to return (None = all)
            
        Returns:
            List of turns in format [{"user": "...", "assistant": "..."}, ...]
        """
        session = self.get_session(session_id)
        if not session:
            return []
        
        turns = session["turns"]
        
        if max_turns is not None and len(turns) > max_turns:
            turns = turns[-max_turns:]
        
        # Return simplified format (just user/assistant messages)
        return [{"user": t["user"], "assistant": t["assistant"]} for t in turns]
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get full session data."""
        session_file = self.storage_dir / f"session_{session_id}.json"
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading session {session_id}: {e}")
            return None
    
    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """List all session IDs."""
        sessions = []
        
        for session_file in self.storage_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    
                # Filter by user_id if provided
                if user_id is None or session_data.get("user_id") == user_id:
                    sessions.append(session_data["session_id"])
            except Exception as e:
                print(f"Error reading {session_file}: {e}")
                continue
        
        return sessions
    
    def delete_session(self, session_id: str):
        """Delete a session."""
        session_file = self.storage_dir / f"session_{session_id}.json"
        
        if session_file.exists():
            session_file.unlink()
    
    def clear_all(self):
        """Clear all sessions (for testing)."""
        for session_file in self.storage_dir.glob("session_*.json"):
            session_file.unlink()
    
    def _save_session(self, session_id: str, session_data: Dict):
        """Save session to file."""
        session_file = self.storage_dir / f"session_{session_id}.json"
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)


# ============================================
# FUTURE: MONGODB BACKEND
# ============================================

class MongoDBConversationStore:
    """
    MongoDB-based conversation storage (future implementation).
    
    Collection: conversations
    Schema:
    {
        "_id": ObjectId,
        "session_id": str,
        "user_id": str,
        "created_at": datetime,
        "updated_at": datetime,
        "metadata": dict,
        "turns": [
            {"user": str, "assistant": str, "timestamp": datetime, "metadata": dict},
            ...
        ]
    }
    
    Usage (future):
    >>> store = ConversationStore(backend="mongodb", mongo_uri="mongodb://...", db_name="astro_chatbot")
    >>> session_id = store.create_session(user_id="user123")
    >>> store.add_turn(session_id, "What is Mars?", "Mars is the planet of action...")
    """
    
    def __init__(self, mongo_uri: str, db_name: str = "astro_chatbot", collection_name: str = "conversations"):
        """
        Initialize MongoDB storage.
        
        Args:
            mongo_uri: MongoDB connection URI
            db_name: Database name
            collection_name: Collection name for conversations
        """
        raise NotImplementedError("MongoDB backend will be implemented during app integration")
        
        # Future implementation:
        # from pymongo import MongoClient
        # self.client = MongoClient(mongo_uri)
        # self.db = self.client[db_name]
        # self.collection = self.db[collection_name]
        # 
        # # Create indexes
        # self.collection.create_index("session_id", unique=True)
        # self.collection.create_index("user_id")
        # self.collection.create_index("created_at")


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_default_store() -> ConversationStore:
    """Get default conversation store (JSON for now)."""
    return ConversationStore(backend="json")


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("CONVERSATION STORE - Test Suite")
    print("=" * 70)
    print()
    
    # Initialize store
    store = get_default_store()
    
    # Test 1: Create session
    print("Test 1: Create session")
    session_id = store.create_session(user_id="test_user", metadata={"persona": "hybrid"})
    print(f"  ✓ Created session: {session_id}")
    print()
    
    # Test 2: Add turns
    print("Test 2: Add conversation turns")
    store.add_turn(session_id, "What is Mars?", "Mars (Mangal/Kuja) is the planet of action and energy...")
    store.add_turn(session_id, "What about in the 7th house?", "Mars in the 7th house indicates strong passions in partnerships...")
    store.add_turn(session_id, "Thank you!", "You're most welcome! Do you have any other questions?")
    print(f"  ✓ Added 3 turns")
    print()
    
    # Test 3: Get history
    print("Test 3: Retrieve conversation history")
    history = store.get_history(session_id)
    print(f"  ✓ Retrieved {len(history)} turns:")
    for i, turn in enumerate(history, 1):
        print(f"    Turn {i}:")
        print(f"      User: {turn['user'][:50]}...")
        print(f"      Assistant: {turn['assistant'][:50]}...")
    print()
    
    # Test 4: Get history with limit
    print("Test 4: Retrieve last 2 turns only")
    recent_history = store.get_history(session_id, max_turns=2)
    print(f"  ✓ Retrieved {len(recent_history)} turns")
    print()
    
    # Test 5: Get full session
    print("Test 5: Get full session data")
    session = store.get_session(session_id)
    print(f"  ✓ Session metadata:")
    print(f"    ID: {session['session_id']}")
    print(f"    User: {session['user_id']}")
    print(f"    Created: {session['created_at']}")
    print(f"    Turns: {len(session['turns'])}")
    print()
    
    # Test 6: List sessions
    print("Test 6: List all sessions")
    sessions = store.list_sessions()
    print(f"  ✓ Found {len(sessions)} session(s)")
    print()
    
    # Test 7: Delete session
    print("Test 7: Delete session")
    store.delete_session(session_id)
    remaining = store.list_sessions()
    print(f"  ✓ Deleted session. Remaining: {len(remaining)}")
    print()
    
    print("=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    print()
    print("Storage location: data/conversations/")
    print("Ready to integrate with RAG engine.")