# src/session/manager.py
"""
Unified Session Manager for NakshatraAI.

Combines high-performance Redis caching for:
1. User Profiles & Conversation History
2. Astrological Calculations (D1-D60, Dashas, Transits)
3. Conversation Summarization Status
"""

import json
import redis
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from src.api.config import settings

# Standardize key patterns
# session:{user_id}:user_profile
# session:{user_id}:history
# session:{user_id}:summary
# session:{user_id}:metadata
# session:{user_id}:calculations:<type>
# session:{user_id}:transits:current

logger = logging.getLogger(__name__)

@dataclass
class CalculationStatus:
    """Metadata about what's been calculated."""
    has_d1_chart: bool = False
    has_d9_chart: bool = False
    has_d10_chart: bool = False
    has_dasha_data: bool = False
    has_transit_data: bool = False
    has_ayanamsa: bool = False
    last_calculated: Optional[str] = None

class SessionManager:
    """
    State-of-the-art Session Manager merging all Redis functionality.
    """
    
    # TTL values
    TTL_24H = 86400           # History, Profile, Summary
    TTL_30D = 2592000         # Calculations (Birth charts don't change)
    TTL_2H = 7200             # Transits (Dynamic)
    
    # Divisional charts supported
    DIVISIONAL_CHARTS = ['d1', 'd9', 'd10', 'd12', 'd16', 'd20', 'd24', 'd27', 'd30', 'd40', 'd45', 'd60']

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0, password: str = None):
        self.redis = None
        # Try multiple hosts for resilience
        for h in [host, '127.0.0.1', 'localhost']:
            try:
                client = redis.Redis(
                    host=h, 
                    port=port, 
                    db=db, 
                    password=password,
                    decode_responses=True, 
                    socket_connect_timeout=2
                )
                client.ping()
                self.redis = client
                logger.info(f"[SESSION] Redis connected on {h}:{port}")
                break
            except Exception as e:
                continue
                
        if not self.redis:
            logger.error("[SESSION] Redis not available - persistence disabled")

    def _key(self, user_id: str, data_type: str, sub_type: str = None) -> str:
        if sub_type:
            return f"session:{user_id}:{data_type}:{sub_type}"
        return f"session:{user_id}:{data_type}"

    # --- Profile & History ---

    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        if not self.redis: return None
        data = self.redis.get(self._key(user_id, "user_profile"))
        return json.loads(data) if data else None

    def get_conversation_history(self, user_id: str) -> List[Dict]:
        if not self.redis: return []
        data = self.redis.get(self._key(user_id, "history"))
        return json.loads(data) if data else []

    def add_message(self, user_id: str, role: str, content: str, metadata: Dict = None):
        if not self.redis: return False
        try:
            history = self.get_conversation_history(user_id)
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            if metadata: message["metadata"] = metadata
            
            history.append(message)
            # Use configured context window limit
            context_window = settings.CONVERSATION_CONTEXT_WINDOW
            if len(history) > context_window:
                history = history[-context_window:]
            
            # Implementation of permanent storage check
            key = self._key(user_id, "history")
            value = json.dumps(history)
            
            if settings.SESSION_EXPIRY_HOURS > 0:
                self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, value)
            else:
                self.redis.set(key, value)
                
            return True
        except Exception as e:
            logger.error(f"[SESSION] Add message error: {e}")
            return False

    def update_user_profile(self, user_id: str, profile: Dict) -> bool:
        """Compatibility helper for API routes."""
        if not self.redis:
            return False
        try:
            key = self._key(user_id, "user_profile")
            value = json.dumps(profile)
            if settings.SESSION_EXPIRY_HOURS > 0:
                self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, value)
            else:
                self.redis.set(key, value)
            return True
        except Exception as e:
            logger.error(f"[SESSION] Update profile error: {e}")
            return False

    def overwrite_conversation_history(self, user_id: str, conversation: List[Dict]) -> bool:
        """Compatibility helper to replace conversation history atomically."""
        if not self.redis:
            return False
        try:
            normalized = []
            for msg in conversation or []:
                if msg.get("question"):
                    normalized.append({"role": "user", "content": msg["question"], "timestamp": msg.get("timestamp")})
                elif msg.get("role") == "user":
                    normalized.append(msg)

                if msg.get("answer"):
                    normalized.append({"role": "assistant", "content": msg["answer"], "timestamp": msg.get("timestamp")})
                elif msg.get("role") == "assistant":
                    normalized.append(msg)

            key = self._key(user_id, "history")
            value = json.dumps(normalized)
            if settings.SESSION_EXPIRY_HOURS > 0:
                self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, value)
            else:
                self.redis.set(key, value)
            return True
        except Exception as e:
            logger.error(f"[SESSION] Overwrite history error: {e}")
            return False

    # --- Initialization ---
    def initialize_session(self, user_id: str, user_profile: Dict, conversation_history: List = None):
        if not self.redis: return {"status": "error", "message": "Redis offline"}
        try:
            # 1. Process History (Handle external backend formats)
            internal_history = []
            if conversation_history:
                for msg in conversation_history:
                    # Support both standard role/content and backend question/answer formats
                    if msg.get('question'):
                        internal_history.append({"role": "user", "content": msg['question'], "timestamp": msg.get('timestamp')})
                    elif msg.get('role') == 'user':
                        internal_history.append(msg)
                        
                    if msg.get('answer'):
                        internal_history.append({"role": "assistant", "content": msg['answer'], "timestamp": msg.get('timestamp')})
                    elif msg.get('role') == 'assistant':
                        internal_history.append(msg)

            # Helper for setting profile/metadata with TTL check
            def _set_data(data_type, data):
                key = self._key(user_id, data_type)
                val = json.dumps(data)
                if settings.SESSION_EXPIRY_HOURS > 0:
                    self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, val)
                else:
                    self.redis.set(key, val)

            _set_data("user_profile", user_profile)
            _set_data("history", internal_history)
            
            # 2. Store Metadata
            metadata = {
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "messages_imported": len(internal_history)
            }
            _set_data("metadata", metadata)
            
            return {"status": "success", "user_id": user_id}
        except Exception as e:
            logger.error(f"[SESSION] Init error: {e}")
            return {"status": "error", "message": str(e)}

    def session_exists(self, user_id: str) -> bool:
        if not self.redis: return False
        return self.redis.exists(self._key(user_id, "user_profile")) > 0

    # --- Summarization Logic ---

    def get_conversation_summary(self, user_id: str) -> Optional[str]:
        if not self.redis: return None
        data = self.redis.get(self._key(user_id, "summary"))
        return json.loads(data).get('summary') if data else None

    def store_conversation_summary(self, user_id: str, summary: str):
        if not self.redis: return
        data = {
            "summary": summary,
            "updated_at": datetime.utcnow().isoformat(),
            "message_count": len(self.get_conversation_history(user_id))
        }
        
        key = self._key(user_id, "summary")
        val = json.dumps(data)
        if settings.SESSION_EXPIRY_HOURS > 0:
            self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, val)
        else:
            self.redis.set(key, val)

    def should_update_summary(self, user_id: str) -> bool:
        """Update based on configured summary threshold."""
        history = self.get_conversation_history(user_id)
        current_count = len(history)
        
        data = self.redis.get(self._key(user_id, "summary"))
        last_count = json.loads(data).get('message_count', 0) if data else 0
        
        return (current_count - last_count) >= settings.CONVERSATION_SUMMARY_THRESHOLD

    # --- Advanced Calculation Caching ---

    def get_divisional_chart(self, user_id: str, chart_type: str) -> Optional[Dict]:
        if not self.redis or chart_type not in self.DIVISIONAL_CHARTS: return None
        data = self.redis.get(self._key(user_id, "calculations", f"{chart_type}_chart"))
        return json.loads(data) if data else None

    def store_divisional_chart(self, user_id: str, chart_type: str, chart_data: Dict):
        if not self.redis or chart_type not in self.DIVISIONAL_CHARTS: return
        self.redis.setex(self._key(user_id, "calculations", f"{chart_type}_chart"), self.TTL_30D, json.dumps(chart_data))

    def get_dasha_data(self, user_id: str) -> Optional[Dict]:
        if not self.redis: return None
        data = self.redis.get(self._key(user_id, "calculations", "dasha_data"))
        return json.loads(data) if data else None

    def store_dasha_data(self, user_id: str, dasha_data: Dict):
        if not self.redis: return
        self.redis.setex(self._key(user_id, "calculations", "dasha_data"), self.TTL_30D, json.dumps(dasha_data))

    def get_transit_data(self, user_id: str) -> Optional[Dict]:
        if not self.redis: return None
        data = self.redis.get(self._key(user_id, "transits", "current"))
        return json.loads(data) if data else None

    def store_transit_data(self, user_id: str, transit_data: Dict):
        if not self.redis: return
        transit_data['calculated_at'] = datetime.utcnow().isoformat()
        self.redis.setex(self._key(user_id, "transits", "current"), self.TTL_2H, json.dumps(transit_data))

    def get_chart_data(self, user_id: str) -> Optional[Dict]:
        """Compatibility alias for D1 chart retrieval."""
        if not self.redis:
            return None
        data = self.redis.get(self._key(user_id, "calculations", "d1_chart"))
        return json.loads(data) if data else None

    def store_chart_data(self, user_id: str, chart_data: Dict):
        """Compatibility alias for D1 chart storage."""
        if not self.redis:
            return
        self.redis.setex(self._key(user_id, "calculations", "d1_chart"), self.TTL_30D, json.dumps(chart_data))

    def get_calculation_status(self, user_id: str) -> CalculationStatus:
        status = CalculationStatus()
        if not self.redis: return status
        
        status.has_d1_chart = self.redis.exists(self._key(user_id, "calculations", "d1_chart")) > 0
        status.has_d9_chart = self.redis.exists(self._key(user_id, "calculations", "d9_chart")) > 0
        status.has_d10_chart = self.redis.exists(self._key(user_id, "calculations", "d10_chart")) > 0
        status.has_dasha_data = self.redis.exists(self._key(user_id, "calculations", "dasha_data")) > 0
        status.has_transit_data = self.redis.exists(self._key(user_id, "transits", "current")) > 0
        
        return status

    # --- Conversation Phase (Progressive Disclosure) ---

    def get_conversation_phase(self, user_id: str) -> Dict:
        """Get the current conversation phase for progressive disclosure.

        Returns dict with:
            phase: INITIAL | AWAITING_DETAIL | FOLLOWUP_LOOP
            topic: The current topic being discussed (e.g. 'marriage', 'career')
            last_query: The original question that started the current topic
            followup_count: Number of follow-up exchanges in current loop
        """
        base = {"phase": "INITIAL", "topic": None, "last_query": None, "followup_count": 0, "visited_domains": []}
        if not self.redis:
            return base
        data = self.redis.get(self._key(user_id, "conv_phase"))
        if data:
            try:
                stored = json.loads(data)
                # Backward compatible: ensure visited_domains always present
                if "visited_domains" not in stored:
                    stored["visited_domains"] = []
                return stored
            except Exception:
                return base
        return base

    def set_conversation_phase(self, user_id: str, phase: str, topic: str = None,
                               last_query: str = None, followup_count: int = 0,
                               visited_domains: Optional[List[str]] = None):
        """Store conversation phase for progressive disclosure."""
        if not self.redis: return
        existing = self.get_conversation_phase(user_id) if self.redis else {}
        # Merge visited_domains with any existing to preserve history
        _existing_visited = existing.get("visited_domains", []) if isinstance(existing, dict) else []
        _new_visited = visited_domains if visited_domains is not None else _existing_visited
        # Normalize and de-duplicate domains
        norm_visited = sorted({(d or "").strip().lower() for d in _new_visited if d})
        data = {
            "phase": phase,
            "topic": topic,
            "last_query": last_query,
            "followup_count": followup_count,
            "visited_domains": norm_visited,
            "updated_at": datetime.utcnow().isoformat()
        }
        key = self._key(user_id, "conv_phase")
        val = json.dumps(data)
        if settings.SESSION_EXPIRY_HOURS > 0:
            self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, val)
        else:
            self.redis.set(key, val)

    def store_detected_language(self, user_id: str, lang_code: str) -> None:
        """Persist detected language for multilingual continuity."""
        if not self.redis or not lang_code:
            return
        try:
            self.redis.set(self._key(user_id, "lang"), lang_code)
        except Exception as e:
            logger.error(f"[SESSION] Store language error: {e}")

    def get_detected_language(self, user_id: str) -> str:
        """Read previously detected language (default 'en')."""
        if not self.redis:
            return "en"
        try:
            val = self.redis.get(self._key(user_id, "lang"))
            return val or "en"
        except Exception:
            return "en"

    def get_voice_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored voice/consultation preferences (detail_level, remedy_preference, tone)."""
        if not self.redis:
            return None
        try:
            raw = self.redis.get(self._key(user_id, "preferences"))
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception as e:
            logger.debug(f"[SESSION] get_voice_preferences error: {e}")
            return None

    def store_voice_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """Store voice/consultation preferences. Merges with existing."""
        if not self.redis or not preferences:
            return
        try:
            existing = self.get_voice_preferences(user_id) or {}
            merged = {**existing, **{k: v for k, v in preferences.items() if v is not None}}
            if not merged:
                return
            key = self._key(user_id, "preferences")
            val = json.dumps(merged)
            if settings.SESSION_EXPIRY_HOURS > 0:
                self.redis.setex(key, settings.SESSION_EXPIRY_HOURS * 3600, val)
            else:
                self.redis.set(key, val)
            logger.info(f"[SESSION] Stored voice_preferences for {user_id}: {list(merged.keys())}")
        except Exception as e:
            logger.error(f"[SESSION] store_voice_preferences error: {e}")

    def extend_session(self, user_id: str):
        """
        Compatibility no-op.
        Session expiry is already handled by key TTL policy.
        """
        return

    def get_active_sessions_count(self) -> int:
        if not self.redis:
            return 0
        try:
            return len(self.redis.keys("session:*:metadata"))
        except Exception:
            return 0

    # --- Cleanup ---

    def clear_session(self, user_id: str, clear_calculations: bool = False):
        if not self.redis: return False
        keys = [
            self._key(user_id, "user_profile"),
            self._key(user_id, "history"),
            self._key(user_id, "summary"),
            self._key(user_id, "metadata"),
            self._key(user_id, "conv_phase"),
            self._key(user_id, "lang"),
            self._key(user_id, "preferences"),
        ]
        if clear_calculations:
            # Delete all calculation keys for this user
            calc_keys = self.redis.keys(f"session:{user_id}:calculations:*")
            transit_keys = self.redis.keys(f"session:{user_id}:transits:*")
            keys.extend(calc_keys)
            keys.extend(transit_keys)
            
        if keys:
            self.redis.delete(*keys)
        return True

# Global instance
_manager = None
def get_session_manager():
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
