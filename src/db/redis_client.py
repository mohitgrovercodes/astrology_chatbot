# src\db\redis_client.py
"""
Redis Client for Session Management
===================================

Handles storage and retrieval of conversation history and user context
for cross-turn continuity in the astrology chatbot.
"""

import redis
import json
from typing import List, Dict, Any, Optional
from datetime import timedelta

from src.api.config import settings

class RedisClient:
    """
    Client for Redis session management.
    Stores conversation history and user birth context.
    """
    
    def __init__(
        self,
        host: str = settings.REDIS_HOST,
        port: int = settings.REDIS_PORT,
        password: str = settings.REDIS_PASSWORD,
        db: int = 0
    ):
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Test connection
            self.client.ping()
            self.connected = True
            print(f"[REDIS] Connected to Redis at {host}:{port}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"[REDIS] WARNING: Could not connect to Redis at {host}:{port}")
            print(f"[REDIS] Session management will be disabled. Error: {e}")
            self.client = None
            self.connected = False
            
        self.session_expiry = timedelta(hours=settings.SESSION_EXPIRY_HOURS)
        self.max_history = 20  # Keep last 20 messages
        
    def store_message(self, session_id: str, role: str, content: str):
        """
        Stores a message in the session's history.
        Caps history at self.max_history messages.
        """
        if not self.connected:
            return
            
        key = f"history:{session_id}"
        message = json.dumps({"role": role, "content": content})
        
        # Push message to list
        self.client.rpush(key, message)
        
        # Trim list to last N messages
        self.client.ltrim(key, -self.max_history, -1)
        
        # Reset expiry
        self.client.expire(key, self.session_expiry)
        
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieves the conversation history for a session.
        """
        if not self.connected:
            return []
            
        key = f"history:{session_id}"
        messages = self.client.lrange(key, 0, -1)
        return [json.loads(m) for m in messages]
    
    def set_user_context(self, session_id: str, context: Dict[str, Any]):
        """
        Stores the user birth context for a session.
        """
        if not self.connected:
            return
            
        key = f"context:{session_id}"
        self.client.setex(
            key,
            self.session_expiry,
            json.dumps(context)
        )
        
    def get_user_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the user context for a session.
        """
        if not self.connected:
            return None
            
        key = f"context:{session_id}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None

    def clear_session(self, session_id: str):
        """
        Clears all data associated with a session.
        """
        if not self.connected:
            return
            
        self.client.delete(f"history:{session_id}", f"context:{session_id}")

    def ping(self) -> bool:
        """Checks if redis is alive."""
        if not self.connected:
            return False
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False
