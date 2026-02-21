# src/session/redis_session_manager.py
"""
Redis Session Manager for Stateless Chatbot Architecture.

Manages user sessions, profiles, chart data, and conversation history in Redis.
No local database dependency - all data comes from main application via API.
"""

import json
import redis
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class UserProfile:
    """User profile data."""
    user_id: str
    name: str
    date_of_birth: str  # YYYY-MM-DD
    time_of_birth: str  # HH:MM:SS
    place_of_birth: str
    latitude: float
    longitude: float
    timezone: str
    preferred_system: str = "vedic"


@dataclass
class SessionData:
    """Complete session data."""
    session_id: str
    user_id: str
    user_profile: Dict[str, Any]
    chart_data: Optional[Dict[str, Any]] = None
    dasha_data: Optional[Dict[str, Any]] = None
    transit_data: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, str]] = None
    created_at: str = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()


class RedisSessionManager:
    """
    Manages chatbot sessions in Redis.
    
    Key Structure:
    - session:{session_id}:user_profile → User data (TTL: 24h)
    - session:{session_id}:chart_data → Birth chart (TTL: 7d)
    - session:{session_id}:dasha_data → Dasha periods (TTL: 7d)
    - session:{session_id}:transit_data → Transits (TTL: 2h)
    - session:{session_id}:conversation → Chat history (TTL: 24h)
    - session:{session_id}:metadata → Session metadata (TTL: 24h)
    """
    
    # TTL values in seconds
    TTL_USER_PROFILE = 86400      # 24 hours
    TTL_CHART_DATA = 604800        # 7 days
    TTL_DASHA_DATA = 604800        # 7 days
    TTL_TRANSIT_DATA = 7200        # 2 hours (transits change frequently)
    TTL_CONVERSATION = 86400       # 24 hours
    TTL_METADATA = 86400           # 24 hours
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, **redis_kwargs):
        """
        Initialize Redis session manager.
        
        Args:
            redis_client: Existing Redis client, or None to create new
            **redis_kwargs: Redis connection parameters (host, port, db, password)
        """
        if redis_client:
            self.redis = redis_client
        else:
            # Default connection
            self.redis = redis.Redis(
                host=redis_kwargs.get('host', 'localhost'),
                port=redis_kwargs.get('port', 6379),
                db=redis_kwargs.get('db', 0),
                password=redis_kwargs.get('password', None),
                decode_responses=True  # Automatically decode bytes to strings
            )
        
        # Test connection
        try:
            self.redis.ping()
            print("[SESSION] Redis connection established")
        except redis.ConnectionError as e:
            print(f"[SESSION] ⚠️  Redis connection failed: {e}")
            print("[SESSION] Running in STATELESS mode (no caching)")
            self.redis = None
    
    def _key(self, session_id: str, data_type: str) -> str:
        """Generate Redis key."""
        return f"session:{session_id}:{data_type}"
    
    # ========================================================================
    # SESSION INITIALIZATION
    # ========================================================================
    
    def initialize_session(
        self,
        user_id: str,  # user_id IS the session_id
        user_profile: Dict[str, Any],
        pre_calculated_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Initialize a new session with user data.
        
        Called when user opens chatbot. Stores all data in Redis.
        
        NOTE: user_id IS the session_id (they are the same).
        
        Args:
            user_id: User identifier (also used as session_id)
            user_profile: User profile data (name, dob, coordinates, etc.)
            pre_calculated_data: Optional pre-calculated chart/dasha/transit data
            conversation_history: Optional previous conversation messages
            
        Returns:
            Session initialization result
        """
        if not self.redis:
            return {"status": "no_cache", "message": "Redis not available"}
        
        session_id = user_id  # user_id = session_id per requirement
        
        try:
            # 1. Store user profile
            self.redis.setex(
                self._key(session_id, "user_profile"),
                self.TTL_USER_PROFILE,
                json.dumps(user_profile)
            )
            
            # 2. Store pre-calculated data (if provided)
            if pre_calculated_data:
                if 'birth_chart' in pre_calculated_data:
                    self.redis.setex(
                        self._key(session_id, "chart_data"),
                        self.TTL_CHART_DATA,
                        json.dumps(pre_calculated_data['birth_chart'])
                    )
                
                if 'dasha_data' in pre_calculated_data:
                    self.redis.setex(
                        self._key(session_id, "dasha_data"),
                        self.TTL_DASHA_DATA,
                        json.dumps(pre_calculated_data['dasha_data'])
                    )
                
                if 'transits' in pre_calculated_data:
                    self.redis.setex(
                        self._key(session_id, "transit_data"),
                        self.TTL_TRANSIT_DATA,
                        json.dumps(pre_calculated_data['transits'])
                    )
            
            # 3. Store conversation history
            conversation = conversation_history or []
            self.redis.setex(
                self._key(session_id, "conversation"),
                self.TTL_CONVERSATION,
                json.dumps(conversation)
            )
            
            # 4. Store metadata
            metadata = {
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "has_chart": 'birth_chart' in (pre_calculated_data or {}),
                "has_dasha": 'dasha_data' in (pre_calculated_data or {}),
                "has_transits": 'transits' in (pre_calculated_data or {})
            }
            self.redis.setex(
                self._key(session_id, "metadata"),
                self.TTL_METADATA,
                json.dumps(metadata)
            )
            
            print(f"[SESSION] Initialized session: {session_id} for user: {user_id}")
            
            return {
                "status": "success",
                "session_id": session_id,  # Same as user_id
                "cached_data": {
                    "user_profile": True,
                    "chart_data": 'birth_chart' in (pre_calculated_data or {}),
                    "dasha_data": 'dasha_data' in (pre_calculated_data or {}),
                    "transit_data": 'transits' in (pre_calculated_data or {}),
                    "conversation_history": len(conversation)
                },
                "ttl": {
                    "session": self.TTL_USER_PROFILE,
                    "chart_cache": self.TTL_CHART_DATA
                }
            }
            
        except Exception as e:
            print(f"[SESSION] Error initializing session: {e}")
            return {"status": "error", "message": str(e)}
    
    # ========================================================================
    # SESSION DATA RETRIEVAL
    # ========================================================================
    
    def get_session_data(self, session_id: str) -> Optional[SessionData]:
        """
        Get all session data for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionData object or None if session not found
        """
        if not self.redis:
            return None
        
        try:
            # Get metadata first to check if session exists
            metadata_key = self._key(session_id, "metadata")
            metadata_str = self.redis.get(metadata_key)
            
            if not metadata_str:
                print(f"[SESSION] Session not found: {session_id}")
                return None
            
            metadata = json.loads(metadata_str)
            user_id = metadata.get('user_id')
            
            # Get user profile
            user_profile_str = self.redis.get(self._key(session_id, "user_profile"))
            if not user_profile_str:
                print(f"[SESSION] User profile missing for session: {session_id}")
                return None
            
            user_profile = json.loads(user_profile_str)
            
            # Get optional data
            chart_data = self._get_json(session_id, "chart_data")
            dasha_data = self._get_json(session_id, "dasha_data")
            transit_data = self._get_json(session_id, "transit_data")
            conversation = self._get_json(session_id, "conversation") or []
            
            return SessionData(
                session_id=session_id,
                user_id=user_id,
                user_profile=user_profile,
                chart_data=chart_data,
                dasha_data=dasha_data,
                transit_data=transit_data,
                conversation_history=conversation,
                created_at=metadata.get('created_at')
            )
            
        except Exception as e:
            print(f"[SESSION] Error retrieving session: {e}")
            return None
    
    def _get_json(self, session_id: str, data_type: str) -> Optional[Dict]:
        """Helper to get and parse JSON data."""
        try:
            data_str = self.redis.get(self._key(session_id, data_type))
            return json.loads(data_str) if data_str else None
        except:
            return None
    
    def get_user_profile(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile for a session."""
        return self._get_json(session_id, "user_profile")
    
    def get_chart_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached birth chart data."""
        return self._get_json(session_id, "chart_data")
    
    def get_dasha_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached dasha data."""
        return self._get_json(session_id, "dasha_data")
    
    def get_transit_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached transit data."""
        return self._get_json(session_id, "transit_data")
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self._get_json(session_id, "conversation") or []
    
    # ========================================================================
    # SESSION DATA UPDATE
    # ========================================================================
    
    def store_chart_data(self, session_id: str, chart_data: Dict[str, Any]) -> bool:
        """
        Store calculated birth chart data.
        
        Args:
            session_id: Session identifier
            chart_data: Birth chart data
            
        Returns:
            True if stored successfully
        """
        if not self.redis:
            return False
        
        try:
            self.redis.setex(
                self._key(session_id, "chart_data"),
                self.TTL_CHART_DATA,
                json.dumps(chart_data)
            )
            print(f"[SESSION] Stored chart data for session: {session_id}")
            return True
        except Exception as e:
            print(f"[SESSION] Error storing chart data: {e}")
            return False
    
    def store_dasha_data(self, session_id: str, dasha_data: Dict[str, Any]) -> bool:
        """Store calculated dasha data."""
        if not self.redis:
            return False
        
        try:
            self.redis.setex(
                self._key(session_id, "dasha_data"),
                self.TTL_DASHA_DATA,
                json.dumps(dasha_data)
            )
            return True
        except Exception as e:
            print(f"[SESSION] Error storing dasha data: {e}")
            return False
    
    def store_transit_data(self, session_id: str, transit_data: Dict[str, Any]) -> bool:
        """Store calculated transit data."""
        if not self.redis:
            return False
        
        try:
            self.redis.setex(
                self._key(session_id, "transit_data"),
                self.TTL_TRANSIT_DATA,
                json.dumps(transit_data)
            )
            return True
        except Exception as e:
            print(f"[SESSION] Error storing transit data: {e}")
            return False
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a message to conversation history.
        
        Args:
            session_id: Session identifier
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata (intent, confidence, etc.)
            
        Returns:
            True if added successfully
        """
        if not self.redis:
            return False
        
        try:
            # Get current conversation
            conversation = self.get_conversation_history(session_id)
            
            # Add new message
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if metadata:
                message["metadata"] = metadata
            
            conversation.append(message)
            
            # Keep only last 20 messages (configurable)
            if len(conversation) > 20:
                conversation = conversation[-20:]
            
            # Store back
            self.redis.setex(
                self._key(session_id, "conversation"),
                self.TTL_CONVERSATION,
                json.dumps(conversation)
            )
            
            return True
            
        except Exception as e:
            print(f"[SESSION] Error adding message: {e}")
            return False
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        if not self.redis:
            return False
        return self.redis.exists(self._key(session_id, "metadata")) > 0
    
    def extend_session(self, session_id: str) -> bool:
        """
        Extend session TTL (useful for active conversations).
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if extended successfully
        """
        if not self.redis:
            return False
        
        try:
            # Extend all session keys
            keys_to_extend = [
                (self._key(session_id, "user_profile"), self.TTL_USER_PROFILE),
                (self._key(session_id, "conversation"), self.TTL_CONVERSATION),
                (self._key(session_id, "metadata"), self.TTL_METADATA),
            ]
            
            for key, ttl in keys_to_extend:
                if self.redis.exists(key):
                    self.redis.expire(key, ttl)
            
            return True
            
        except Exception as e:
            print(f"[SESSION] Error extending session: {e}")
            return False
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear all session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if cleared successfully
        """
        if not self.redis:
            return False
        
        try:
            keys = [
                self._key(session_id, "user_profile"),
                self._key(session_id, "chart_data"),
                self._key(session_id, "dasha_data"),
                self._key(session_id, "transit_data"),
                self._key(session_id, "conversation"),
                self._key(session_id, "metadata"),
            ]
            
            self.redis.delete(*keys)
            print(f"[SESSION] Cleared session: {session_id}")
            return True
            
        except Exception as e:
            print(f"[SESSION] Error clearing session: {e}")
            return False
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        if not self.redis:
            return 0
        
        try:
            # Count metadata keys (one per session)
            keys = self.redis.keys("session:*:metadata")
            return len(keys)
        except:
            return 0


# ============================================================================
# GLOBAL SESSION MANAGER INSTANCE
# ============================================================================

_session_manager = None


def get_session_manager(**redis_kwargs) -> RedisSessionManager:
    """
    Get global session manager instance.
    
    Args:
        **redis_kwargs: Redis connection parameters
        
    Returns:
        RedisSessionManager instance
    """
    global _session_manager
    
    if _session_manager is None:
        _session_manager = RedisSessionManager(**redis_kwargs)
    
    return _session_manager