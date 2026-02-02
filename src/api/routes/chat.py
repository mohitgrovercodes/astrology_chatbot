"""
Chat Routes
============

Chat endpoint for conversational astrology queries.
"""

from fastapi import APIRouter, Depends, Request, Response
from src.api.schemas.chat import ChatRequest, ChatResponse, QueryAnalysis
from src.api.middleware.auth import verify_api_key
from src.api.middleware.rate_limit import check_rate_limit
from src.api.dependencies import get_orchestrator
import time

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    response: Response,
    chat_request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Main chat endpoint for astrology queries.
    
    Processes user queries through the orchestrator and returns
    personalized astrological responses.
    
    **Rate Limit:** 10 requests per minute
    
    **Authentication:** Requires X-API-Key header
    """
    # Apply rate limiting
    await check_rate_limit(request, api_key)
    
    # Add rate limit headers
    if hasattr(request.state, 'rate_limit_info'):
        info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(info['limit'])
        response.headers["X-RateLimit-Remaining"] = str(info['remaining'])
        response.headers["X-RateLimit-Reset"] = "60"
    
    start_time = time.time()
    
    # Get orchestrator
    orchestrator = get_orchestrator()
    
    # Convert conversation history to dict format
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in chat_request.conversation_history
    ]
    
    # Process query
    result = orchestrator.process_query(
        query=chat_request.query,
        user_id=chat_request.user_id,
        conversation_history=conversation_history
    )
    
    processing_time = time.time() - start_time
    
    # Extract query analysis if available
    query_analysis = None
    if 'query_analysis' in result:
        qa = result['query_analysis']
        query_analysis = QueryAnalysis(
            category=qa['category'],
            sensitivity_level=qa['sensitivity_level'],
            handling_strategy=qa['handling_strategy']
        )
    
    # Extract chart data if requested
    chart_data = None
    if chat_request.include_chart_data and 'chart_data' in result:
        chart_data = result['chart_data']
    
    return ChatResponse(
        answer=result.get('answer', ''),
        intent=result.get('intent', 'UNKNOWN'),
        confidence=result.get('confidence', 0.0),
        processing_time=processing_time,
        query_analysis=query_analysis,
        chart_data=chart_data
    )
