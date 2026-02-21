# src/api/routes/chat_stateless.py
"""
Stateless Chat Routes - Redis Session Management.

Two-endpoint architecture:
1. /initialize - Initialize session with user data
2. /message - Send message (session-based)
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import time

from src.session.redis_session_manager import get_session_manager
from src.orchestration.orchestrator import create_enhanced_orchestrator


router = APIRouter()


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


class PreCalculatedData(BaseModel):
    """Optional pre-calculated astrological data."""
    birth_chart: Optional[Dict[str, Any]] = None
    dasha_data: Optional[Dict[str, Any]] = None
    transits: Optional[Dict[str, Any]] = None


class ConversationMessage(BaseModel):
    """Single conversation message."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    timestamp: Optional[str] = None


class InitializeSessionRequest(BaseModel):
    """Request to initialize a new session."""
    session_id: str = Field(..., description="Unique session identifier")
    user_profile: UserProfile
    pre_calculated_data: Optional[PreCalculatedData] = None
    conversation_history: Optional[List[ConversationMessage]] = []


class InitializeSessionResponse(BaseModel):
    """Response from session initialization."""
    status: str
    session_id: str
    message: str = "Session initialized successfully"
    cached_data: Dict[str, Any]
    ttl: Dict[str, int]


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    session_id: str
    message: str


class SendMessageResponse(BaseModel):
    """Response from message."""
    answer: str
    intent: str
    confidence: float
    processing_time: float
    metadata: Dict[str, Any]


# ============================================================================
# ENDPOINT 1: INITIALIZE SESSION
# ============================================================================

@router.post("/initialize", response_model=InitializeSessionResponse)
async def initialize_session(request: InitializeSessionRequest):
    """
    Initialize a new chatbot session.
    
    Called when user opens the chatbot. Stores all user data in Redis.
    
    Args:
        request: Session initialization data
        
    Returns:
        Session initialization result
        
    Example:
        ```
        POST /api/v1/chat/initialize
        {
          "session_id": "sess_20260220_abc123",
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
          "pre_calculated_data": {
            "birth_chart": {...},  // Optional
            "dasha_data": {...},   // Optional
            "transits": {...}      // Optional
          },
          "conversation_history": []  // Optional
        }
        ```
    """
    try:
        # Get session manager
        session_manager = get_session_manager()
        
        # Check if session already exists
        if session_manager.session_exists(request.session_id):
            # Extend existing session
            session_manager.extend_session(request.session_id)
            return InitializeSessionResponse(
                status="extended",
                session_id=request.session_id,
                message="Existing session extended",
                cached_data={"existing": True},
                ttl={"session": 86400, "chart_cache": 604800}
            )
        
        # Convert conversation history
        conversation = []
        if request.conversation_history:
            conversation = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp
                }
                for msg in request.conversation_history
            ]
        
        # Convert pre-calculated data
        pre_calc = None
        if request.pre_calculated_data:
            pre_calc = request.pre_calculated_data.dict(exclude_none=True)
        
        # Initialize session
        result = session_manager.initialize_session(
            session_id=request.session_id,
            user_id=request.user_profile.user_id,
            user_profile=request.user_profile.dict(),
            pre_calculated_data=pre_calc,
            conversation_history=conversation
        )
        
        if result['status'] == 'success':
            return InitializeSessionResponse(
                status="success",
                session_id=request.session_id,
                cached_data=result['cached_data'],
                ttl=result['ttl']
            )
        else:
            raise HTTPException(status_code=500, detail=result.get('message', 'Failed to initialize session'))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session initialization error: {str(e)}")


# ============================================================================
# ENDPOINT 2: SEND MESSAGE
# ============================================================================

@router.post("/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """
    Send a message in an existing session.
    
    Args:
        request: Message request with session_id and message
        
    Returns:
        AI response
        
    Example:
        ```
        POST /api/v1/chat/message
        {
          "session_id": "sess_20260220_abc123",
          "message": "When will I get married?"
        }
        ```
    """
    start_time = time.time()
    
    try:
        # Get session manager
        session_manager = get_session_manager()
        
        # Get session data
        session_data = session_manager.get_session_data(request.session_id)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {request.session_id}. Please call /initialize first."
            )
        
        # Get orchestrator
        orchestrator = create_enhanced_orchestrator()
        
        # Prepare session data for orchestrator
        orchestrator_session_data = {
            "chart_data": session_data.chart_data,
            "dasha_data": session_data.dasha_data,
            "transit_data": session_data.transit_data
        }
        
        # Process query
        result = orchestrator.process_query(
            query=request.message,
            user_id=session_data.user_id,
            conversation_history=session_data.conversation_history,
            user_profile_override=session_data.user_profile,
            session_data=orchestrator_session_data
        )
        
        # Extract answer and metadata
        answer = result.get('answer', '')
        intent = result.get('intent', 'UNKNOWN')
        confidence = result.get('confidence', 0.0)
        
        # Update conversation history in Redis
        session_manager.add_message(
            session_id=request.session_id,
            role="user",
            content=request.message
        )
        
        session_manager.add_message(
            session_id=request.session_id,
            role="assistant",
            content=answer,
            metadata={"intent": intent, "confidence": confidence}
        )
        
        # Store calculated data if generated
        if 'chart_data' in result and result['chart_data']:
            session_manager.store_chart_data(request.session_id, result['chart_data'])
        
        if 'dasha_data' in result and result['dasha_data']:
            session_manager.store_dasha_data(request.session_id, result['dasha_data'])
        
        if 'transit_data' in result and result['transit_data']:
            session_manager.store_transit_data(request.session_id, result['transit_data'])
        
        # Extend session (user is active)
        session_manager.extend_session(request.session_id)
        
        # Build metadata
        metadata = {
            "session_id": request.session_id,
            "user_id": session_data.user_id,
            "cached_chart": session_data.chart_data is not None,
            "cached_dasha": session_data.dasha_data is not None,
            "validation_passed": result.get('validation_result', {}).get('passed', None),
            "validation_strength": result.get('validation_result', {}).get('overall_strength', None),
            "sources_count": len(result.get('knowledge_chunks', []))
        }
        
        processing_time = time.time() - start_time
        
        return SendMessageResponse(
            answer=answer,
            intent=intent,
            confidence=confidence,
            processing_time=processing_time,
            metadata=metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Message processing error: {str(e)}")


# ============================================================================
# OPTIONAL: SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Get session status.
    
    Returns information about what data is cached for a session.
    """
    try:
        session_manager = get_session_manager()
        
        if not session_manager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_manager.get_session_data(session_id)
        
        return {
            "session_id": session_id,
            "exists": True,
            "user_id": session_data.user_id,
            "cached_data": {
                "user_profile": session_data.user_profile is not None,
                "chart_data": session_data.chart_data is not None,
                "dasha_data": session_data.dasha_data is not None,
                "transit_data": session_data.transit_data is not None,
                "conversation_messages": len(session_data.conversation_history)
            },
            "created_at": session_data.created_at
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear a session (logout/cleanup).
    
    Removes all cached data for a session.
    """
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
            "redis_connected": session_manager.redis is not None
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
