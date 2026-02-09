"""
Chatbot Integration Example

Demonstrates how the chatbot receives pre-fetched data from the backend
and processes it for RAG consumption.
"""

import asyncio
import logging

from src.services.backend_data_adapter import (
    BackendDataAdapter,
    BackendAstroData,
    process_backend_data_for_rag
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_basic_usage():
    """
    Example 1: Basic usage - receiving data from backend
    """
    logger.info("=" * 60)
    logger.info("Example 1: Basic Chatbot Usage")
    logger.info("=" * 60)
    
    # Simulate data received from your application backend
    # (In production, this comes from your backend API/service)
    backend_data = {
        "user_id": "user_123",
        "birth_chart": {
            "birth_details": {
                "day": 15,
                "month": 8,
                "year": 1990
            },
            "planets": [
                {"name": "Sun", "sign": "Leo", "house": 1, "full_degree": 23.5},
                {"name": "Moon", "sign": "Cancer", "house": 12, "full_degree": 15.2},
                {"name": "Mars", "sign": "Aries", "house": 9, "full_degree": 10.8}
            ],
            "ascendant": {
                "sign": "Leo",
                "degree": 12.3
            }
        },
        "dashas": {
            "current_dasha": {
                "planet": "Venus",
                "start": "2020-01-15",
                "end": "2040-01-15"
            },
            "major_dashas": [
                {"planet": "Venus", "start": "2020-01-15", "end": "2040-01-15"},
                {"planet": "Sun", "start": "2040-01-15", "end": "2046-01-15"}
            ]
        },
        "horoscope": {
            "period": "daily",
            "prediction": "Today is favorable for career growth.",
            "personal": "Focus on self-improvement",
            "profession": "Good opportunities await"
        }
    }
    
    # Process the data for RAG
    adapter = BackendDataAdapter()
    validated_data = adapter.validate_backend_data(backend_data)
    rag_context = adapter.process_backend_data(validated_data)
    
    logger.info("\nRAG Context (Text):")
    logger.info(rag_context["text"])
    logger.info("\nMetadata:")
    logger.info(rag_context["metadata"])


def example_2_convenience_function():
    """
    Example 2: Using convenience function
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Convenience Function")
    logger.info("=" * 60)
    
    # Data from backend
    backend_data = {
        "user_id": "user_456",
        "birth_chart": {
            "planets": [
                {"name": "Jupiter", "sign": "Sagittarius", "house": 5, "full_degree": 18.2}
            ]
        },
        "transits": {
            "transits": [
                {"planet": "Saturn", "sign": "Aquarius", "house": 7}
            ]
        }
    }
    
    # One-liner processing
    rag_context = process_backend_data_for_rag(backend_data)
    
    logger.info("\nRAG Context:")
    logger.info(rag_context["text"])


async def example_3_chatbot_handler():
    """
    Example 3: Full chatbot message handler
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Full Chatbot Handler")
    logger.info("=" * 60)
    
    # Simulated user query
    user_query = "What career opportunities will I have this year?"
    user_id = "user_789"
    
    # Step 1: Your backend sends astrology data to chatbot
    # (In production, this comes from your backend service)
    backend_response = {
        "user_id": user_id,
        "birth_chart": {
            "planets": [
                {"name": "Sun", "sign": "Capricorn", "house": 10, "full_degree": 15.0},
                {"name": "Saturn", "sign": "Aquarius", "house": 11, "full_degree": 20.5}
            ]
        },
        "dashas": {
            "current_dasha": {
                "planet": "Saturn",
                "start": "2022-01-01",
                "end": "2041-01-01"
            }
        },
        "horoscope": {
            "period": "yearly",
            "prediction": "Career advancement expected",
            "profession": "Leadership roles may open up"
        },
        "transits": {
            "transits": [
                {"planet": "Jupiter", "sign": "Taurus", "house": 2}
            ]
        }
    }
    
    # Step 2: Chatbot processes backend data
    logger.info("Step 1: Processing backend data...")
    rag_context = process_backend_data_for_rag(backend_response)
    
    # Step 3: Pass to RAG engine (pseudo-code)
    logger.info("\nStep 2: Querying RAG engine...")
    # rag_response = await rag_engine.query(
    #     query=user_query,
    #     context=rag_context["text"],
    #     metadata=rag_context["metadata"]
    # )
    
    # Step 4: Generate LLM response (pseudo-code)
    logger.info("\nStep 3: Generating LLM response...")
    # final_response = await llm.generate(
    #     prompt=rag_response["prompt"],
    #     context=rag_response["retrieved_chunks"]
    # )
    
    logger.info("\nAstrological Context for RAG:")
    logger.info(rag_context["text"])
    
    # In production, return final_response to user


def example_4_selective_data():
    """
    Example 4: Process only specific data types
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Selective Data Processing")
    logger.info("=" * 60)
    
    backend_data = BackendAstroData(
        user_id="user_999",
        birth_chart={"planets": [{"name": "Venus", "sign": "Libra"}]},
        dashas={"current_dasha": {"planet": "Venus"}},
        horoscope={"period": "daily", "prediction": "Good day"}
    )
    
    adapter = BackendDataAdapter()
    
    # Only process birth chart and dashas, skip horoscope
    rag_context = adapter.extract_specific_data(
        backend_data,
        data_types=["birth_chart", "dashas"]
    )
    
    logger.info("\nSelective RAG Context:")
    logger.info(rag_context["text"])


def example_5_integration_with_fastapi():
    """
    Example 5: FastAPI endpoint for chatbot
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: FastAPI Integration Pattern")
    logger.info("=" * 60)
    
    # Example FastAPI endpoint code
    example_code = '''
from fastapi import FastAPI, HTTPException
from src.services.backend_data_adapter import process_backend_data_for_rag

app = FastAPI()

@app.post("/chatbot/query")
async def handle_chatbot_query(
    user_id: str,
    query: str,
    backend_data: dict  # Data sent from your backend
):
    """
    Chatbot query endpoint
    
    Your backend calls this endpoint with:
    - user_id
    - user query
    - pre-fetched astrology data
    """
    try:
        # Process backend data for RAG
        rag_context = process_backend_data_for_rag(backend_data)
        
        # Query RAG engine
        rag_response = await rag_engine.query(
            query=query,
            context=rag_context["text"],
            metadata=rag_context["metadata"]
        )
        
        # Generate LLM response
        final_response = await llm.generate(
            prompt=rag_response["prompt"],
            context=rag_response["retrieved_chunks"]
        )
        
        return {
            "user_id": user_id,
            "query": query,
            "response": final_response,
            "metadata": rag_context["metadata"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
'''
    
    logger.info("\nFastAPI Endpoint Pattern:")
    logger.info(example_code)


if __name__ == "__main__":
    # Run examples
    example_1_basic_usage()
    example_2_convenience_function()
    asyncio.run(example_3_chatbot_handler())
    example_4_selective_data()
    example_5_integration_with_fastapi()
