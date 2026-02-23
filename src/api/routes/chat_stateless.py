# src/api/routes/chat_stateless.py
"""
Stateless Chat Routes - Redis Session Management.

Two-endpoint architecture:
1. /initialize - Initialize session with user data
2. /message - Send message (session-based)
"""

import os
CONTEXT_WINDOW = int(os.getenv('CONVERSATION_CONTEXT_WINDOW', '5'))

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import time
import redis
import json
from datetime import datetime

from src.api.orchestrator_helper import get_orchestrator


router = APIRouter()


# ============================================================================
# INLINE SESSION MANAGER (no external dependency)
# ============================================================================

class SimpleSessionManager:
    """Simple session manager for Redis."""
    
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            self.redis.ping()
            print("[SESSION] Redis connection established")
        except:
            self.redis = None
            print("[SESSION] Redis not available")
    
    def get_user_profile(self, user_id: str):
        if not self.redis:
            return None
        try:
            data = self.redis.get(f"session:{user_id}:user_profile")
            return json.loads(data) if data else None
        except:
            return None
    
    def get_conversation_history(self, user_id: str):
        if not self.redis:
            return []
        try:
            data = self.redis.get(f"session:{user_id}:conversation")
            return json.loads(data) if data else []
        except:
            return []
    
    def get_chart_data(self, user_id: str):
        if not self.redis:
            return None
        try:
            data = self.redis.get(f"session:{user_id}:chart_data")
            return json.loads(data) if data else None
        except:
            return None
    
    def get_dasha_data(self, user_id: str):
        if not self.redis:
            return None
        try:
            data = self.redis.get(f"session:{user_id}:dasha_data")
            return json.loads(data) if data else None
        except:
            return None
    
    def get_transit_data(self, user_id: str):
        if not self.redis:
            return None
        try:
            data = self.redis.get(f"session:{user_id}:transit_data")
            return json.loads(data) if data else None
        except:
            return None
    
    def session_exists(self, user_id: str):
        if not self.redis:
            return False
        return self.redis.exists(f"session:{user_id}:metadata") > 0
    
    def initialize_session(self, user_id: str, user_profile: dict, conversation_history: list = None):
        if not self.redis:
            return {"status": "error", "message": "Redis not available"}
        
        try:
            # Store user profile (24h)
            self.redis.setex(f"session:{user_id}:user_profile", 86400, json.dumps(user_profile))
            
            # Convert conversation history from external format to internal format
            internal_conversation = []
            if conversation_history:
                for msg in conversation_history:
                    # Add question (user message)
                    if msg.get('question'):
                        internal_conversation.append({
                            "role": "user",
                            "content": msg['question'],
                            "timestamp": msg.get('timestamp', {}).get('$date') if isinstance(msg.get('timestamp'), dict) else msg.get('timestamp')
                        })
                    
                    # Add answer (assistant message)
                    if msg.get('answer'):
                        internal_conversation.append({
                            "role": "assistant",
                            "content": msg['answer'],
                            "timestamp": msg.get('timestamp', {}).get('$date') if isinstance(msg.get('timestamp'), dict) else msg.get('timestamp'),
                            "metadata": {
                                "source": msg.get('source', 'external')
                            }
                        })
            
            # Store conversation (24h)
            self.redis.setex(f"session:{user_id}:conversation", 86400, json.dumps(internal_conversation))
            
            # Store metadata
            metadata = {
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "messages_imported": len(internal_conversation)
            }
            self.redis.setex(f"session:{user_id}:metadata", 86400, json.dumps(metadata))
            
            return {
                "status": "success",
                "user_id": user_id
            }
        except Exception as e:
            print(f"[SESSION] Error initializing: {e}")
            return {
                "status": "error",
                "user_id": user_id,
                "message": str(e)
            }
    
    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        if not self.redis:
            return False
        
        try:
            conversation = self.get_conversation_history(session_id)
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            if metadata:
                message["metadata"] = metadata
            
            conversation.append(message)
            
            # Keep last 20 messages
            if len(conversation) > 20:
                conversation = conversation[-20:]
            
            self.redis.setex(f"session:{session_id}:conversation", 86400, json.dumps(conversation))
            return True
        except:
            return False
    
    def store_chart_data(self, user_id: str, chart_data: dict):
        if not self.redis:
            return
        try:
            self.redis.setex(f"session:{user_id}:chart_data", 604800, json.dumps(chart_data))
            print(f"[CACHE] 💾 Stored chart data for {user_id} (TTL: 7d)")
        except:
            pass
    
    def store_dasha_data(self, user_id: str, dasha_data: dict):
        if not self.redis:
            return
        try:
            self.redis.setex(f"session:{user_id}:dasha_data", 604800, json.dumps(dasha_data))
            print(f"[CACHE] 💾 Stored dasha data for {user_id} (TTL: 7d)")
        except:
            pass
    
    def store_transit_data(self, user_id: str, transit_data: dict):
        if not self.redis:
            return
        try:
            self.redis.setex(f"session:{user_id}:transit_data", 7200, json.dumps(transit_data))
            print(f"[CACHE] 💾 Stored transit data for {user_id} (TTL: 2h)")
        except:
            pass
    
    def extend_session(self, user_id: str):
        if not self.redis:
            return
        try:
            for key in [f"session:{user_id}:user_profile", f"session:{user_id}:conversation", f"session:{user_id}:metadata"]:
                if self.redis.exists(key):
                    self.redis.expire(key, 86400)
        except:
            pass
    
    def clear_session(self, session_id: str):
        if not self.redis:
            return False
        try:
            keys = [
                f"session:{session_id}:user_profile",
                f"session:{session_id}:conversation",
                f"session:{session_id}:metadata",
                f"session:{session_id}:chart_data",
                f"session:{session_id}:dasha_data",
                f"session:{session_id}:transit_data"
            ]
            self.redis.delete(*keys)
            return True
        except:
            return False
    
    def get_active_sessions_count(self):
        if not self.redis:
            return 0
        try:
            keys = self.redis.keys("session:*:metadata")
            return len(keys)
        except:
            return 0


# Global session manager
_session_manager = None

def get_session_manager():
    global _session_manager
    if _session_manager is None:
        _session_manager = SimpleSessionManager()
    return _session_manager


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class UserProfile(BaseModel):
    """User profile data."""
    user_id: str
    name: str
    date_of_birth: str = Field(..., description="YYYY-MM-DD format")
    time_of_birth: str = Field(..., description="HH:MM:SS format")
    place_of_birth: str
    latitude: float
    longitude: float
    timezone: str = "Asia/Kolkata"
    preferred_system: str = "vedic"


class ConversationHistoryItem(BaseModel):
    """Single conversation item from external system."""
    question: str
    answer: str
    source: str = "external"
    timestamp: Any  # Can be string or dict with $date


class InitializeSessionRequest(BaseModel):
    """Request to initialize a new session."""
    user_id: str = Field(..., description="User identifier (also used as session_id)")
    user_profile: UserProfile
    conversation_history: Optional[List[ConversationHistoryItem]] = []


class InitializeSessionResponse(BaseModel):
    """Response from session initialization."""
    user_id: str
    status: str  # "success" or "error"


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    user_id: str = Field(..., description="User identifier (same as session_id)")
    question: str = Field(..., description="User's question")


class SendMessageResponse(BaseModel):
    """Response from message."""
    user_id: str
    question: str
    answer: str
    source: str = "openai"  # "openai" or "external"


# ============================================================================
# ENDPOINT 1: INITIALIZE SESSION
# ============================================================================

@router.post("/initialize", response_model=InitializeSessionResponse)
async def initialize_session(request: InitializeSessionRequest):
    """
    Initialize a new chatbot session.
    
    Called when user opens the chatbot. Stores user data and conversation history in Redis.
    
    NOTE: user_id IS the session_id (they are the same).
    
    Args:
        request: Session initialization data
        
    Returns:
        Session initialization result
        
    Example:
        ```
        POST /api/v1/chat/initialize
        {
          "user_id": "user_12345",
          "user_profile": {
            "user_id": "user_12345",
            "name": "Priya Sharma",
            "date_of_birth": "1995-03-15",
            "time_of_birth": "14:30:00",
            "place_of_birth": "Mumbai, India",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "timezone": "Asia/Kolkata",
            "preferred_system": "vedic"
          },
          "conversation_history": [
            {
              "question": "When will I get married?",
              "answer": "Based on your chart...",
              "source": "external",
              "timestamp": {"$date": "2026-02-20T11:25:57.567Z"}
            }
          ]
        }
        ```
    """
    try:
        session_manager = get_session_manager()
        user_id = request.user_id
        
        # Check if session already exists
        if session_manager.session_exists(user_id):
            # Extend existing session
            session_manager.extend_session(user_id)
            print(f"[SESSION] Extended existing session for {user_id}")
            return InitializeSessionResponse(
                user_id=user_id,
                status="success"
            )
        
        # Convert conversation history from Pydantic models to dicts
        conversation = []
        if request.conversation_history:
            conversation = [item.dict() for item in request.conversation_history]
        
        # Initialize session
        result = session_manager.initialize_session(
            user_id=user_id,
            user_profile=request.user_profile.dict(),
            conversation_history=conversation
        )
        
        print(f"[SESSION] Initialized session for {user_id} - Status: {result['status']}")
        
        return InitializeSessionResponse(
            user_id=result['user_id'],
            status=result['status']
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[SESSION] Error initializing session: {e}")
        return InitializeSessionResponse(
            user_id=request.user_id,
            status="error"
        )


# ============================================================================
# ENDPOINT 2: SEND MESSAGE
# ============================================================================

@router.post("/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """
    Send a message in an existing session.
    
    Context Management:
    - Retrieves full conversation history from Redis
    - Sends only last N messages to orchestrator (default: 5)
    - Stores all messages in Redis for future reference
    
    Args:
        request: Message request with user_id and question
        
    Returns:
        AI response
        
    Example:
        ```
        POST /api/v1/chat/message
        {
          "user_id": "user_12345",
          "question": "When will I get married?"
        }
        ```
    """
    start_time = time.time()
    
    try:
        session_manager = get_session_manager()
        user_id = request.user_id
        question = request.question
        
        # Get user profile
        user_profile = session_manager.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found for user: {user_id}. Please call /initialize first."
            )
        
        # ====================================================================
        # CONTEXT WINDOW: Get last N messages for orchestrator
        # ====================================================================
        full_history = session_manager.get_conversation_history(user_id) or []
        
        if len(full_history) > CONTEXT_WINDOW:
            recent_history = full_history[-CONTEXT_WINDOW:]
            print(f"[CONTEXT] Sending last {CONTEXT_WINDOW} of {len(full_history)} messages")
        else:
            recent_history = full_history
            print(f"[CONTEXT] Sending all {len(full_history)} messages")
        
        # Get orchestrator
        orchestrator = get_orchestrator()
        
        # ====================================================================
        # SMART CACHING: Get cached calculations if available
        # ====================================================================
        cached_chart = session_manager.get_chart_data(user_id)
        cached_dasha = session_manager.get_dasha_data(user_id)
        cached_transit = session_manager.get_transit_data(user_id)
        
        # Log cache status
        print(f"[CACHE] Chart: {'✅ Cached' if cached_chart else '❌ Not cached'}")
        print(f"[CACHE] Dasha: {'✅ Cached' if cached_dasha else '❌ Not cached'}")
        print(f"[CACHE] Transit: {'✅ Cached' if cached_transit else '❌ Not cached'}")
        
        # Prepare session data with cached calculations
        orchestrator_session_data = {
            "chart_data": cached_chart,
            "dasha_data": cached_dasha,
            "transit_data": cached_transit
        }
        
        # ====================================================================
        # PROCESS QUERY
        # ====================================================================
        result = orchestrator.process_query(
            query=question,
            user_id=user_id,
            conversation_history=recent_history,
            user_profile_override=user_profile,
            session_data=orchestrator_session_data
        )
        
        answer = result.get('answer', '')
        intent = result.get('intent', 'UNKNOWN')
        confidence = result.get('confidence', 0.0)
        
        # ====================================================================
        # STORE NEW CALCULATIONS IN CACHE
        # ====================================================================
        if result.get('chart_data') and not cached_chart:
            session_manager.store_chart_data(user_id, result['chart_data'])
        
        if result.get('dasha_data') and not cached_dasha:
            session_manager.store_dasha_data(user_id, result['dasha_data'])
        
        if result.get('transit_data') and not cached_transit:
            session_manager.store_transit_data(user_id, result['transit_data'])
        
        # ====================================================================
        # UPDATE CONVERSATION HISTORY
        # ====================================================================
        session_manager.add_message(user_id, "user", question)
        session_manager.add_message(
            user_id,
            "assistant",
            answer,
            metadata={
                "intent": intent,
                "confidence": confidence,
                "source": "openai"
            }
        )
        
        # Extend session
        session_manager.extend_session(user_id)
        
        processing_time = time.time() - start_time
        
        # Log processing info (for debugging)
        print(f"[RESPONSE] User: {user_id}, Intent: {intent}, Confidence: {confidence:.2f}, Time: {processing_time:.2f}s")
        
        # Return simplified response
        return SendMessageResponse(
            user_id=user_id,
            question=question,
            answer=answer,
            source="openai"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Message processing error: {str(e)}")


# ============================================================================
# OPTIONAL ENDPOINTS
# ============================================================================

@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session status."""
    try:
        session_manager = get_session_manager()
        
        if not session_manager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        user_profile = session_manager.get_user_profile(session_id)
        conversation = session_manager.get_conversation_history(session_id)
        
        return {
            "session_id": session_id,
            "exists": True,
            "user_id": user_profile.get('user_id') if user_profile else None,
            "cached_data": {
                "user_profile": user_profile is not None,
                "chart_data": session_manager.get_chart_data(session_id) is not None,
                "dasha_data": session_manager.get_dasha_data(session_id) is not None,
                "transit_data": session_manager.get_transit_data(session_id) is not None,
                "conversation_messages": len(conversation)
            },
            "context_window_size": CONTEXT_WINDOW,
            "messages_sent_to_llm": min(len(conversation), CONTEXT_WINDOW)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a session."""
    try:
        session_manager = get_session_manager()
        success = session_manager.clear_session(session_id)
        
        if success:
            return {"status": "success", "message": f"Session {session_id} cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear session")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get chatbot statistics."""
    try:
        session_manager = get_session_manager()
        
        return {
            "active_sessions": session_manager.get_active_sessions_count(),
            "redis_connected": session_manager.redis is not None,
            "context_window_size": CONTEXT_WINDOW,
            "context_window_env_var": "CONVERSATION_CONTEXT_WINDOW"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))