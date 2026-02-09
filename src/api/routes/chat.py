"""
Chat Routes - Backend Integration
===================================

Handles chat requests with Redis session management and internal authentication.
"""

from fastapi import APIRouter, Depends, Request
from src.api.schemas.chat import (
    ChatRequest, ChatResponse, QueryAnalysis,
    IntegrationChatRequest, IntegrationChatResponse, Source
)
from src.api.middleware.auth import verify_api_key, verify_internal_service
from src.api.middleware.rate_limit import check_rate_limit
from src.api.dependencies import get_orchestrator, get_redis_client
from src.api.config import settings
import time

router = APIRouter()


@router.post("/chat", response_model=IntegrationChatResponse)
async def chat(
    request: Request,
    chat_request: IntegrationChatRequest,
    is_authenticated: bool = Depends(verify_internal_service)
):
    """
    Backend-integrated chat endpoint for astrology queries.
    
    Processes user queries using Redis for 24h session history
    and internal service authentication.
    """
    start_time = time.time()
    
    # 1. Initialize components
    orchestrator = get_orchestrator()
    redis = get_redis_client()
    session_id = chat_request.session_id
    
    # 2. Map and Save User Context to Redis
    # Backend format matches UserProfile structure reasonably well
    user_context = chat_request.user_context.dict()
    # Map backend names to Orchestrator expected names (if different)
    # Orchestrator fix: standardized to date_of_birth, time_of_birth
    user_profile_override = {
        "user_id": session_id,  # Use session_id as anchor
        "name": "User",
        "date_of_birth": user_context.get("birth_date"),
        "time_of_birth": user_context.get("birth_time"),
        "latitude": user_context.get("latitude"),
        "longitude": user_context.get("longitude"),
        "timezone": user_context.get("timezone", "Asia/Kolkata"),
        "preferred_system": user_context.get("astrology_system", "vedic")
    }
    redis.set_user_context(session_id, user_profile_override)
    
    # 3. Retrieve History from Redis
    history = redis.get_history(session_id)
    
    # 4. Process Query
    result = orchestrator.process_query(
        query=chat_request.message,
        user_id=session_id,
        conversation_history=history,
        user_profile_override=user_profile_override
    )
    
    answer = result.get('answer', '')
    
    # 5. Save Turn to Redis (keeping it to last 20 messages as requested)
    redis.store_message(session_id, "user", chat_request.message)
    redis.store_message(session_id, "assistant", answer)
    
    # 6. Format Sources
    sources = []
    if 'knowledge_chunks' in result and result['knowledge_chunks']:
        for chunk in result['knowledge_chunks']:
            sources.append(Source(
                content=chunk.page_content if hasattr(chunk, 'page_content') else str(chunk),
                metadata=chunk.metadata if hasattr(chunk, 'metadata') else {}
            ))
            
    # 7. Construct Metadata
    metadata = {
        "tokens_used": result.get('total_tokens', 0), # Assuming cost_logger or orchestrator provides this
        "model": result.get('model_used', settings.LLM_MODEL),
        "processing_time": time.time() - start_time,
        "intent": result.get('intent')
    }
    
    return IntegrationChatResponse(
        answer=answer,
        sources=sources,
        session_id=session_id,
        metadata=metadata
    )
