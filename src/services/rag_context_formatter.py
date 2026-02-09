"""
RAG Context Formatter

Transforms API responses into structured, RAG-friendly context for
vector embedding and semantic retrieval.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


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
        """
        Format birth chart data for RAG
        
        Args:
            api_response: Raw API response
            
        Returns:
            Structured context with text and metadata
        """
        try:
            # Extract key facts
            facts = []
            
            # Birth details
            if "birth_details" in api_response:
                bd = api_response["birth_details"]
                facts.append(f"Birth Date: {bd.get('day')}/{bd.get('month')}/{bd.get('year')}")
                facts.append(f"Birth Time: {bd.get('hour')}:{bd.get('min')}")
                facts.append(f"Birth Place: Lat {bd.get('lat')}, Lon {bd.get('lon')}")
            
            # Planetary positions
            if "planets" in api_response:
                for planet_data in api_response["planets"]:
                    planet = planet_data.get("name")
                    sign = planet_data.get("sign")
                    house = planet_data.get("house")
                    degree = planet_data.get("full_degree")
                    
                    facts.append(
                        f"{planet} is in {sign} sign, {house} house at {degree}°"
                    )
            
            # Ascendant
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
        """
        Format dasha periods for RAG
        
        Args:
            api_response: Raw API response
            
        Returns:
            Structured context with text and metadata
        """
        try:
            facts = []
            
            # Current dasha
            if "current_dasha" in api_response:
                cd = api_response["current_dasha"]
                facts.append(
                    f"Current Mahadasha: {cd.get('planet')} "
                    f"(from {cd.get('start')} to {cd.get('end')})"
                )
            
            # Major dashas
            if "major_dashas" in api_response:
                facts.append("\nMajor Dasha Periods:")
                for dasha in api_response["major_dashas"][:5]:  # Top 5
                    planet = dasha.get("planet")
                    start = dasha.get("start")
                    end = dasha.get("end")
                    facts.append(f"- {planet}: {start} to {end}")
            
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
        """
        Format horoscope predictions for RAG
        
        Args:
            api_response: Raw API response
            period: Horoscope period (daily, weekly, monthly, yearly)
            
        Returns:
            Structured context with text and metadata
        """
        try:
            facts = []
            
            # Prediction text
            if "prediction" in api_response:
                facts.append(f"{period.capitalize()} Horoscope:")
                facts.append(api_response["prediction"])
            
            # Category-wise predictions
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
        """
        Format current transits for RAG
        
        Args:
            api_response: Raw API response
            
        Returns:
            Structured context with text and metadata
        """
        try:
            facts = ["Current Planetary Transits:"]
            
            if "transits" in api_response:
                for transit in api_response["transits"]:
                    planet = transit.get("planet")
                    sign = transit.get("sign")
                    house = transit.get("house")
                    facts.append(f"- {planet} transiting {sign} in {house} house")
            
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
        """
        Format yogas and doshas for RAG
        
        Args:
            api_response: Raw API response
            
        Returns:
            Structured context with text and metadata
        """
        try:
            facts = []
            
            # Beneficial yogas
            if "yogas" in api_response:
                facts.append("Beneficial Yogas:")
                for yoga in api_response["yogas"]:
                    name = yoga.get("name")
                    description = yoga.get("description")
                    facts.append(f"- {name}: {description}")
            
            # Doshas
            if "doshas" in api_response:
                facts.append("\nDoshas (Afflictions):")
                for dosha in api_response["doshas"]:
                    name = dosha.get("name")
                    severity = dosha.get("severity")
                    facts.append(f"- {name} (Severity: {severity})")
            
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
    def format_for_retrieval(
        data_type: str,
        api_response: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generic formatter that routes to specific formatters
        
        Args:
            data_type: Type of astrology data
            api_response: Raw API response
            **kwargs: Additional parameters
            
        Returns:
            Formatted context for RAG
        """
        formatters = {
            "birth_chart": RAGContextFormatter.format_birth_chart,
            "dashas": RAGContextFormatter.format_dashas,
            "horoscope": lambda r: RAGContextFormatter.format_horoscope(
                r, kwargs.get("period", "daily")
            ),
            "transits": RAGContextFormatter.format_transits,
            "yogas": RAGContextFormatter.format_yogas,
        }
        
        formatter = formatters.get(data_type)
        if formatter:
            return formatter(api_response)
        else:
            logger.warning(f"No formatter found for data type: {data_type}")
            return {
                "text": str(api_response),
                "metadata": {
                    "data_type": data_type,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "structured_data": api_response
            }
    
    @staticmethod
    def combine_contexts(contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine multiple formatted contexts into a single RAG context
        
        Args:
            contexts: List of formatted contexts
            
        Returns:
            Combined context
        """
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
