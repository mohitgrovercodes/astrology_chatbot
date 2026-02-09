"""
Backend Data Adapter for Chatbot

This adapter receives pre-fetched astrology data from the application backend
and prepares it for RAG consumption. The chatbot does NOT make direct API calls.

Architecture:
    Application Backend → [This Adapter] → RAG Context Formatter → RAG Engine
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, validator

from .rag_context_formatter import RAGContextFormatter


logger = logging.getLogger(__name__)


# ============================================================================
# DATA SCHEMAS (Expected from Backend)
# ============================================================================

class BackendAstroData(BaseModel):
    """
    Schema for astrology data received from application backend
    
    The backend team should send data in this format after fetching
    from 3rd-party APIs and caching in Redis.
    """
    
    user_id: str = Field(..., description="User identifier")
    
    # Birth details
    birth_chart: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Birth chart data (planets, houses, ascendant)"
    )
    
    # Dashas
    dashas: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dasha periods (Vimshottari, Yogini, etc.)"
    )
    
    # Ayanamsa
    ayanamsa: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Ayanamsa calculation"
    )
    
    # Horoscopes
    horoscope: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Horoscope predictions (daily/weekly/monthly/yearly)"
    )
    
    # Transits
    transits: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current planetary transits"
    )
    
    # Yogas & Doshas
    yogas: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Yogas and Doshas in birth chart"
    )
    
    # Divisional charts
    divisional_charts: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Divisional charts (D1, D9, etc.)"
    )
    
    # Metadata
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="When this data was fetched"
    )
    
    source: Optional[str] = Field(
        default="backend",
        description="Data source identifier"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "birth_chart": {
                    "planets": [...],
                    "houses": [...],
                    "ascendant": {...}
                },
                "dashas": {
                    "current_dasha": {...},
                    "major_dashas": [...]
                },
                "horoscope": {
                    "period": "daily",
                    "prediction": "..."
                }
            }
        }


# ============================================================================
# BACKEND DATA ADAPTER
# ============================================================================

class BackendDataAdapter:
    """
    Adapter for chatbot to receive and process astrology data from backend
    
    This is the bridge between your application backend and the chatbot's
    RAG system. The chatbot does NOT make API calls directly.
    
    Workflow:
    1. Backend fetches data from 3rd-party APIs
    2. Backend caches in Redis
    3. Backend sends to chatbot via this adapter
    4. Adapter formats for RAG
    5. RAG engine retrieves interpretations
    6. LLM generates response
    """
    
    def __init__(self):
        """Initialize the backend data adapter"""
        self.formatter = RAGContextFormatter()
        logger.info("BackendDataAdapter initialized")
    
    def process_backend_data(
        self,
        backend_data: BackendAstroData,
        format_for_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Process astrology data received from backend
        
        Args:
            backend_data: Data received from application backend
            format_for_rag: Whether to format for RAG (default: True)
            
        Returns:
            Processed data ready for RAG or raw data
            
        Example:
            >>> adapter = BackendDataAdapter()
            >>> backend_data = BackendAstroData(
            ...     user_id="user_123",
            ...     birth_chart={...},
            ...     dashas={...}
            ... )
            >>> rag_context = adapter.process_backend_data(backend_data)
            >>> # Use rag_context with RAG engine
        """
        logger.info(f"Processing backend data for user {backend_data.user_id}")
        
        if not format_for_rag:
            return backend_data.dict()
        
        # Collect formatted contexts
        formatted_contexts = []
        
        # Format birth chart
        if backend_data.birth_chart:
            formatted_contexts.append(
                self.formatter.format_birth_chart(backend_data.birth_chart)
            )
        
        # Format dashas
        if backend_data.dashas:
            formatted_contexts.append(
                self.formatter.format_dashas(backend_data.dashas)
            )
        
        # Format horoscope
        if backend_data.horoscope:
            period = backend_data.horoscope.get("period", "daily")
            formatted_contexts.append(
                self.formatter.format_horoscope(backend_data.horoscope, period)
            )
        
        # Format transits
        if backend_data.transits:
            formatted_contexts.append(
                self.formatter.format_transits(backend_data.transits)
            )
        
        # Format yogas
        if backend_data.yogas:
            formatted_contexts.append(
                self.formatter.format_yogas(backend_data.yogas)
            )
        
        # Combine all contexts
        if formatted_contexts:
            combined = self.formatter.combine_contexts(formatted_contexts)
            
            # Add source metadata
            combined["metadata"]["user_id"] = backend_data.user_id
            combined["metadata"]["source"] = backend_data.source
            combined["metadata"]["backend_timestamp"] = (
                backend_data.timestamp.isoformat() if backend_data.timestamp else None
            )
            
            return combined
        else:
            logger.warning(f"No data to format for user {backend_data.user_id}")
            return {
                "text": "",
                "metadata": {
                    "user_id": backend_data.user_id,
                    "error": "No astrology data provided"
                },
                "structured_data": {}
            }
    
    def extract_specific_data(
        self,
        backend_data: BackendAstroData,
        data_types: List[str]
    ) -> Dict[str, Any]:
        """
        Extract and format specific data types only
        
        Args:
            backend_data: Data from backend
            data_types: List of data types to extract
                       (e.g., ["birth_chart", "dashas"])
            
        Returns:
            Formatted context with only requested data types
        """
        formatted_contexts = []
        
        for data_type in data_types:
            if data_type == "birth_chart" and backend_data.birth_chart:
                formatted_contexts.append(
                    self.formatter.format_birth_chart(backend_data.birth_chart)
                )
            elif data_type == "dashas" and backend_data.dashas:
                formatted_contexts.append(
                    self.formatter.format_dashas(backend_data.dashas)
                )
            elif data_type == "horoscope" and backend_data.horoscope:
                period = backend_data.horoscope.get("period", "daily")
                formatted_contexts.append(
                    self.formatter.format_horoscope(backend_data.horoscope, period)
                )
            elif data_type == "transits" and backend_data.transits:
                formatted_contexts.append(
                    self.formatter.format_transits(backend_data.transits)
                )
            elif data_type == "yogas" and backend_data.yogas:
                formatted_contexts.append(
                    self.formatter.format_yogas(backend_data.yogas)
                )
        
        if formatted_contexts:
            return self.formatter.combine_contexts(formatted_contexts)
        else:
            return {
                "text": "",
                "metadata": {"error": "No matching data types found"},
                "structured_data": {}
            }
    
    def validate_backend_data(
        self,
        raw_data: Dict[str, Any]
    ) -> BackendAstroData:
        """
        Validate raw backend data against schema
        
        Args:
            raw_data: Raw dictionary from backend
            
        Returns:
            Validated BackendAstroData instance
            
        Raises:
            ValidationError: If data doesn't match schema
        """
        try:
            return BackendAstroData(**raw_data)
        except Exception as e:
            logger.error(f"Backend data validation failed: {e}")
            raise


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def process_backend_data_for_rag(
    backend_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to process backend data for RAG
    
    Args:
        backend_data: Raw data from backend (will be validated)
        
    Returns:
        RAG-formatted context
        
    Example:
        >>> # In your chatbot handler
        >>> backend_data = {
        ...     "user_id": "user_123",
        ...     "birth_chart": {...},
        ...     "dashas": {...}
        ... }
        >>> rag_context = process_backend_data_for_rag(backend_data)
        >>> # Pass rag_context to RAG engine
    """
    adapter = BackendDataAdapter()
    validated_data = adapter.validate_backend_data(backend_data)
    return adapter.process_backend_data(validated_data, format_for_rag=True)
