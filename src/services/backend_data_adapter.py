"""
Backend Data Adapter for Chatbot

This module receives pre-fetched astrology data from the application backend
and prepares it for RAG consumption. Includes:
- Data validation (Pydantic schemas)
- RAG context formatting (JSON → semantic text)
- Backend data processing

The chatbot does NOT make direct API calls.

Architecture:
    Application Backend → [This Adapter] → RAG-formatted text → RAG Engine
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, validator


logger = logging.getLogger(__name__)


# ============================================================================
# RAG CONTEXT FORMATTER
# ============================================================================

class RAGContextFormatter:
    """
    Formats astrology API responses for RAG consumption
    
    Transforms nested JSON into flat, semantically rich text suitable for:
    - Vector embedding
    - Semantic search
    - LLM context injection
    """
    
    @staticmethod
    def format_birth_chart(api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format birth chart data for RAG"""
        try:
            facts = []
            
            if "birth_details" in api_response:
                bd = api_response["birth_details"]
                facts.append(f"Birth Date: {bd.get('day')}/{bd.get('month')}/{bd.get('year')}")
                facts.append(f"Birth Time: {bd.get('hour')}:{bd.get('min')}")
                facts.append(f"Birth Place: Lat {bd.get('lat')}, Lon {bd.get('lon')}")
            
            if "planets" in api_response:
                for planet_data in api_response["planets"]:
                    planet = planet_data.get("name")
                    sign = planet_data.get("sign")
                    house = planet_data.get("house")
                    degree = planet_data.get("full_degree")
                    facts.append(f"{planet} is in {sign} sign, {house} house at {degree}°")
            
            if "ascendant" in api_response:
                asc = api_response["ascendant"]
                facts.append(f"Ascendant (Lagna) is {asc.get('sign')} at {asc.get('degree')}°")
            
            return {
                "text": "\n".join(facts),
                "metadata": {
                    "data_type": "birth_chart",
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "astrology_api"
                },
                "structured_data": api_response
            }
        except Exception as e:
            logger.error(f"Error formatting birth chart: {e}")
            return {
                "text": "Birth chart data unavailable",
                "metadata": {"error": str(e)},
                "structured_data": api_response
            }
    
    @staticmethod
    def format_dashas(api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format dasha periods for RAG"""
        try:
            facts = []
            
            if "current_dasha" in api_response:
                cd = api_response["current_dasha"]
                facts.append(
                    f"Current Mahadasha: {cd.get('planet')} "
                    f"(from {cd.get('start')} to {cd.get('end')})"
                )
            
            if "major_dashas" in api_response:
                facts.append("\nMajor Dasha Periods:")
                for dasha in api_response["major_dashas"][:5]:
                    facts.append(f"- {dasha.get('planet')}: {dasha.get('start')} to {dasha.get('end')}")
            
            return {
                "text": "\n".join(facts),
                "metadata": {
                    "data_type": "dashas",
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "astrology_api"
                },
                "structured_data": api_response
            }
        except Exception as e:
            logger.error(f"Error formatting dashas: {e}")
            return {
                "text": "Dasha data unavailable",
                "metadata": {"error": str(e)},
                "structured_data": api_response
            }
    
    @staticmethod
    def format_horoscope(api_response: Dict[str, Any], period: str = "daily") -> Dict[str, Any]:
        """Format horoscope predictions for RAG"""
        try:
            facts = []
            
            if "prediction" in api_response:
                facts.append(f"{period.capitalize()} Horoscope:")
                facts.append(api_response["prediction"])
            
            categories = ["personal", "health", "profession", "emotions", "travel", "luck"]
            for category in categories:
                if category in api_response:
                    facts.append(f"\n{category.capitalize()}: {api_response[category]}")
            
            return {
                "text": "\n".join(facts),
                "metadata": {
                    "data_type": f"horoscope_{period}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "astrology_api"
                },
                "structured_data": api_response
            }
        except Exception as e:
            logger.error(f"Error formatting horoscope: {e}")
            return {
                "text": "Horoscope data unavailable",
                "metadata": {"error": str(e)},
                "structured_data": api_response
            }
    
    @staticmethod
    def format_transits(api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format current transits for RAG"""
        try:
            facts = ["Current Planetary Transits:"]
            
            if "transits" in api_response:
                for transit in api_response["transits"]:
                    facts.append(
                        f"- {transit.get('planet')} transiting {transit.get('sign')} "
                        f"in {transit.get('house')} house"
                    )
            
            return {
                "text": "\n".join(facts),
                "metadata": {
                    "data_type": "transits",
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "astrology_api"
                },
                "structured_data": api_response
            }
        except Exception as e:
            logger.error(f"Error formatting transits: {e}")
            return {
                "text": "Transit data unavailable",
                "metadata": {"error": str(e)},
                "structured_data": api_response
            }
    
    @staticmethod
    def format_yogas(api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Format yogas and doshas for RAG"""
        try:
            facts = []
            
            if "yogas" in api_response:
                facts.append("Beneficial Yogas:")
                for yoga in api_response["yogas"]:
                    facts.append(f"- {yoga.get('name')}: {yoga.get('description')}")
            
            if "doshas" in api_response:
                facts.append("\nDoshas (Afflictions):")
                for dosha in api_response["doshas"]:
                    facts.append(f"- {dosha.get('name')} (Severity: {dosha.get('severity')})")
            
            return {
                "text": "\n".join(facts),
                "metadata": {
                    "data_type": "yogas_doshas",
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "astrology_api"
                },
                "structured_data": api_response
            }
        except Exception as e:
            logger.error(f"Error formatting yogas: {e}")
            return {
                "text": "Yoga/Dosha data unavailable",
                "metadata": {"error": str(e)},
                "structured_data": api_response
            }
    
    @staticmethod
    def combine_contexts(contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine multiple formatted contexts into a single RAG context"""
        combined_text = []
        combined_metadata = {}
        combined_data = {}
        
        for ctx in contexts:
            combined_text.append(ctx.get("text", ""))
            combined_metadata.update(ctx.get("metadata", {}))
            combined_data.update(ctx.get("structured_data", {}))
        
        return {
            "text": "\n\n".join(combined_text),
            "metadata": combined_metadata,
            "structured_data": combined_data
        }



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
