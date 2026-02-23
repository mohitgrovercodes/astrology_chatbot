# populate_redis_with_user_data.py
"""
Populate Redis with User Data - Backend Simulator

This script mimics what your backend will do:
1. Fetch user data from MongoDB (simulated with dummy data)
2. Store directly in Redis (same format chatbot expects)
3. Chatbot reads from Redis during conversation
4. New messages get appended to conversation history in Redis

Usage:
    python populate_redis_with_user_data.py
"""

import redis
import json
from datetime import datetime


# ============================================================================
# REDIS CONNECTION
# ============================================================================

def get_redis_connection():
    """Connect to Redis."""
    try:
        r = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True  # Auto-decode bytes to strings
        )
        r.ping()
        print("[REDIS] ✅ Connected to Redis")
        return r
    except redis.ConnectionError as e:
        print(f"[REDIS] ❌ Connection failed: {e}")
        print("[REDIS] Make sure Redis is running: redis-server")
        return None


# ============================================================================
# SIMULATED USER DATA (From MongoDB)
# ============================================================================

# Simulated users from your MongoDB
USERS = {
    "user001": {
        "user_id": "user001",
        "name": "Arjun Kumar",
        "date_of_birth": "1990-07-15",
        "time_of_birth": "08:30:00",
        "place_of_birth": "New Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic"
    },
    "user002": {
        "user_id": "user002",
        "name": "Priya Sharma",
        "date_of_birth": "1995-03-15",
        "time_of_birth": "14:30:00",
        "place_of_birth": "Mumbai, India",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic"
    },
    "user003": {
        "user_id": "user003",
        "name": "Rahul Verma",
        "date_of_birth": "1988-11-20",
        "time_of_birth": "22:15:00",
        "place_of_birth": "Bangalore, India",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic"
    }
}

# Simulated conversation history from MongoDB
CONVERSATION_HISTORY = {
    "user001": [],  # New user, no history
    "user002": [
        {
            "role": "user",
            "content": "Hello",
            "timestamp": "2026-02-19T10:30:00Z"
        },
        {
            "role": "assistant",
            "content": "Namaste! How can I help you today?",
            "timestamp": "2026-02-19T10:30:02Z"
        },
        {
            "role": "user",
            "content": "What is my moon sign?",
            "timestamp": "2026-02-19T10:35:00Z"
        },
        {
            "role": "assistant",
            "content": "Your moon sign is Gemini.",
            "timestamp": "2026-02-19T10:35:03Z"
        }
    ],
    "user003": []
}

# Optional: Pre-calculated chart data (if you have it)
PRECALCULATED_CHARTS = {
    "user002": {
        "lagna": "Virgo",
        "moon_sign": "Gemini",
        "sun_sign": "Pisces",
        "planets": {
            "Sun": {"rashi": "Pisces", "house": 7, "degree": 24.5},
            "Moon": {"rashi": "Gemini", "house": 10, "degree": 81.56}
        }
    }
}


# ============================================================================
# REDIS STORAGE FUNCTIONS
# ============================================================================

def store_user_in_redis(r: redis.Redis, user_id: str, user_data: dict):
    """
    Store user data in Redis (mimics initialization).
    
    Uses user_id as session_id per your requirement.
    """
    
    print(f"\n{'='*70}")
    print(f"Storing user: {user_data['name']} (user_id: {user_id})")
    print(f"{'='*70}")
    
    # TTL values (same as session manager)
    TTL_USER_PROFILE = 86400      # 24 hours
    TTL_CHART_DATA = 604800        # 7 days
    TTL_CONVERSATION = 86400       # 24 hours
    TTL_METADATA = 86400           # 24 hours
    
    # 1. Store user profile
    profile_key = f"session:{user_id}:user_profile"
    r.setex(profile_key, TTL_USER_PROFILE, json.dumps(user_data))
    print(f"[STORED] User profile → {profile_key}")
    
    # 2. Store conversation history
    conversation = CONVERSATION_HISTORY.get(user_id, [])
    conversation_key = f"session:{user_id}:conversation"
    r.setex(conversation_key, TTL_CONVERSATION, json.dumps(conversation))
    print(f"[STORED] Conversation history ({len(conversation)} messages) → {conversation_key}")
    
    # 3. Store pre-calculated chart if available
    if user_id in PRECALCULATED_CHARTS:
        chart_key = f"session:{user_id}:chart_data"
        r.setex(chart_key, TTL_CHART_DATA, json.dumps(PRECALCULATED_CHARTS[user_id]))
        print(f"[STORED] Pre-calculated chart → {chart_key}")
    
    # 4. Store metadata
    metadata = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "has_chart": user_id in PRECALCULATED_CHARTS,
        "has_dasha": False,
        "has_transits": False
    }
    metadata_key = f"session:{user_id}:metadata"
    r.setex(metadata_key, TTL_METADATA, json.dumps(metadata))
    print(f"[STORED] Metadata → {metadata_key}")
    
    print(f"[DONE] ✅ User {user_id} ready for chatbot\n")


def display_redis_data(r: redis.Redis, user_id: str):
    """Display what's stored in Redis for a user."""
    
    print(f"\n{'='*70}")
    print(f"Redis Data for user_id: {user_id}")
    print(f"{'='*70}\n")
    
    # Get all keys for this user
    keys = r.keys(f"session:{user_id}:*")
    
    if not keys:
        print(f"❌ No data found for {user_id}")
        return
    
    print(f"Found {len(keys)} keys:\n")
    
    for key in sorted(keys):
        ttl = r.ttl(key)
        data = r.get(key)
        
        print(f"📝 {key}")
        print(f"   TTL: {ttl} seconds ({ttl/3600:.1f} hours)")
        
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                if 'name' in parsed:
                    print(f"   Data: {parsed.get('name')} - DOB: {parsed.get('date_of_birth')}")
                elif 'lagna' in parsed:
                    print(f"   Data: Lagna={parsed.get('lagna')}, Moon={parsed.get('moon_sign')}")
                elif 'user_id' in parsed:
                    print(f"   Data: {parsed}")
                elif isinstance(parsed, list):
                    print(f"   Data: {len(parsed)} messages")
                    for msg in parsed[-2:]:  # Last 2 messages
                        print(f"     - {msg['role']}: {msg['content'][:50]}...")
            else:
                print(f"   Data: {str(parsed)[:100]}")
        except:
            print(f"   Data: {str(data)[:100]}")
        
        print()


def clear_user_from_redis(r: redis.Redis, user_id: str):
    """Clear all data for a user (cleanup)."""
    
    keys = r.keys(f"session:{user_id}:*")
    
    if keys:
        r.delete(*keys)
        print(f"[DELETED] Removed {len(keys)} keys for {user_id}")
    else:
        print(f"[INFO] No data to delete for {user_id}")


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def populate_all_users():
    """Populate Redis with all test users."""
    
    print("\n" + "="*70)
    print("POPULATING REDIS WITH USER DATA")
    print("="*70)
    print("\nThis simulates your backend sending user data to chatbot.\n")
    
    r = get_redis_connection()
    if not r:
        return
    
    # Store each user
    for user_id, user_data in USERS.items():
        store_user_in_redis(r, user_id, user_data)
    
    print("="*70)
    print(f"✅ Stored {len(USERS)} users in Redis")
    print("="*70)
    print("\nNow you can:")
    print("1. Run chatbot.py or API")
    print("2. Use these user_ids: user001, user002, user003")
    print("3. Chatbot will read data from Redis")
    print("4. New messages will be appended to Redis")


def view_all_users():
    """View all users in Redis."""
    
    r = get_redis_connection()
    if not r:
        return
    
    print("\n" + "="*70)
    print("VIEWING ALL USERS IN REDIS")
    print("="*70)
    
    # Get all session keys
    all_keys = r.keys("session:*:metadata")
    
    if not all_keys:
        print("\n❌ No users found in Redis")
        print("Run populate_all_users() first")
        return
    
    # Extract unique user_ids
    user_ids = set()
    for key in all_keys:
        # session:user001:metadata → user001
        user_id = key.split(':')[1]
        user_ids.add(user_id)
    
    print(f"\nFound {len(user_ids)} users:\n")
    
    for user_id in sorted(user_ids):
        metadata = r.get(f"session:{user_id}:metadata")
        if metadata:
            meta = json.loads(metadata)
            print(f"👤 {user_id}")
            print(f"   Created: {meta.get('created_at')}")
            print(f"   Has chart: {meta.get('has_chart')}")
            
            # Get name from profile
            profile = r.get(f"session:{user_id}:user_profile")
            if profile:
                prof = json.loads(profile)
                print(f"   Name: {prof.get('name')}")
            print()


def view_specific_user(user_id: str):
    """View detailed data for a specific user."""
    
    r = get_redis_connection()
    if not r:
        return
    
    display_redis_data(r, user_id)


def cleanup_all():
    """Remove all test data from Redis."""
    
    r = get_redis_connection()
    if not r:
        return
    
    print("\n" + "="*70)
    print("CLEANING UP REDIS")
    print("="*70)
    
    confirm = input("\n⚠️  Delete all session data? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Cancelled")
        return
    
    # Delete all session keys
    keys = r.keys("session:*")
    
    if keys:
        r.delete(*keys)
        print(f"\n[DELETED] Removed {len(keys)} keys")
    else:
        print("\n[INFO] No data to delete")


def test_conversation_flow():
    """
    Test: Simulate conversation flow.
    
    Shows how conversation history gets appended.
    """
    
    print("\n" + "="*70)
    print("TESTING CONVERSATION FLOW")
    print("="*70)
    
    r = get_redis_connection()
    if not r:
        return
    
    user_id = "user001"
    
    # 1. Store initial user
    print("\n1. Initial user data (from backend):")
    store_user_in_redis(r, user_id, USERS[user_id])
    
    # 2. Display initial state
    print("\n2. Initial Redis state:")
    conversation_key = f"session:{user_id}:conversation"
    conv = json.loads(r.get(conversation_key))
    print(f"   Conversation messages: {len(conv)}")
    
    # 3. Simulate chatbot appending messages
    print("\n3. Simulating chatbot conversation:")
    
    # User sends message
    user_msg = {
        "role": "user",
        "content": "When will I get married?",
        "timestamp": datetime.utcnow().isoformat()
    }
    conv.append(user_msg)
    print(f"   [USER] {user_msg['content']}")
    
    # Bot responds
    bot_msg = {
        "role": "assistant",
        "content": "Based on your chart, Jupiter's transit in March 2026 indicates...",
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {"intent": "RAG_WITH_CALCULATION"}
    }
    conv.append(bot_msg)
    print(f"   [BOT] {bot_msg['content'][:60]}...")
    
    # Save back to Redis
    r.setex(conversation_key, 86400, json.dumps(conv))
    print(f"\n   [SAVED] Updated conversation in Redis")
    
    # 4. Display updated state
    print("\n4. Updated Redis state:")
    conv_updated = json.loads(r.get(conversation_key))
    print(f"   Conversation messages: {len(conv_updated)}")
    print(f"   Last message: {conv_updated[-1]['content'][:50]}...")
    
    # 5. Show full conversation
    print("\n5. Full conversation history:")
    for i, msg in enumerate(conv_updated, 1):
        role = "👤 USER" if msg['role'] == 'user' else "🤖 BOT"
        print(f"   {i}. {role}: {msg['content'][:60]}...")


# ============================================================================
# INTERACTIVE MENU
# ============================================================================

def main():
    """Interactive menu."""
    
    print("\n" + "="*70)
    print("REDIS USER DATA POPULATOR")
    print("="*70)
    print("\nSimulates your backend storing user data in Redis")
    print("Chatbot reads from Redis during conversations\n")
    
    while True:
        print("\nOPTIONS:")
        print("1. Populate all users in Redis")
        print("2. View all users in Redis")
        print("3. View specific user details")
        print("4. Test conversation flow")
        print("5. Cleanup all data")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            populate_all_users()
        elif choice == '2':
            view_all_users()
        elif choice == '3':
            user_id = input("Enter user_id (user001/user002/user003): ").strip()
            view_specific_user(user_id)
        elif choice == '4':
            test_conversation_flow()
        elif choice == '5':
            cleanup_all()
        elif choice == '6':
            print("\nGoodbye!")
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
