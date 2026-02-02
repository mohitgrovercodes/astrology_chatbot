"""
Chat Schemas - Pydantic Models
================================

Request and response models for chat endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class Message(BaseModel):
    """Conversation message."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat endpoint request."""
    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    user_id: str = Field(..., min_length=1, description="User ID")
    conversation_history: Optional[List[Message]] = Field(
        default=[],
        description="Recent conversation history"
    )
    include_chart_data: bool = Field(
        default=False,
        description="Include full chart data in response"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "When will I get married?",
                "user_id": "user123",
                "conversation_history": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello! How can I help you?"}
                ],
                "include_chart_data": False
            }
        }


class QueryAnalysis(BaseModel):
    """Safety query analysis."""
    category: str = Field(..., description="Sensitivity category")
    sensitivity_level: float = Field(..., ge=0.0, le=1.0, description="Sensitivity score")
    handling_strategy: str = Field(..., description="Handling strategy")


class ChatResponse(BaseModel):
    """Chat endpoint response."""
    answer: str = Field(..., description="Bot response")
    intent: str = Field(..., description="Classified intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intent confidence")
    processing_time: float = Field(..., description="Processing time in seconds")
    query_analysis: Optional[QueryAnalysis] = Field(
        default=None,
        description="Safety analysis"
    )
    chart_data: Optional[Dict] = Field(
        default=None,
        description="Birth chart data (if requested)"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Response timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Based on your 7th house and Venus placement...",
                "intent": "NEEDS_RAG",
                "confidence": 0.85,
                "processing_time": 1.23,
                "query_analysis": {
                    "category": "general",
                    "sensitivity_level": 0.0,
                    "handling_strategy": "proceed_normal"
                },
                "chart_data": None,
                "timestamp": "2026-02-02T14:00:00Z"
            }
        }
