import asyncio
from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator

from src.api.routes.chat_stateless import EnhancedSessionManager
import datetime
import redis.asyncio as aioredis
from copy import deepcopy

async def main():
    redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    manager = EnhancedSessionManager(redis_client)
    orchestrator = EnhancedLangGraphOrchestrator()
    
    # We will use user1010 profile
    profile_data = {
        "user_id": "user1010",
        "name": "Mohit",
        "date_of_birth": "1995-10-01",
        "time_of_birth": "07:30:00",
        "place_of_birth": "Alwar, India",
        "latitude": 27.5530,
        "longitude": 76.6346,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic",
    }
    await manager.save_profile("user1010", profile_data)
    
    print("--- Test 1: Marriage Query ---")
    req1 = {
        "query": "Meri shadi kab hogi ?",
        "user_id": "user1010",
        "session_id": "sess_1",
        "language": "hi",
        "location_context": "India",
        "time_context": datetime.datetime.now().isoformat()
    }
    
    response1 = await orchestrator.process_message(req1)
    print(f"Response: {response1.get('response', '')}")
    
    print("\n--- Test 2: Career Query ---")
    req2 = {
        "query": "Mera career kab grow hoga ?",
        "user_id": "user1010",
        "session_id": "sess_2",
        "language": "hi",
        "location_context": "India",
        "time_context": datetime.datetime.now().isoformat()
    }
    
    response2 = await orchestrator.process_message(req2)
    print(f"Response: {response2.get('response', '')}")

if __name__ == "__main__":
    asyncio.run(main())
