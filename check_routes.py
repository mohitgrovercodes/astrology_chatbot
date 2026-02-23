# check_routes.py
"""
Quick script to check what routes are available in the API.
"""

import requests
import json

API_BASE = "http://localhost:6262"

print("\n" + "="*70)
print("CHECKING API ROUTES")
print("="*70 + "\n")

# Check root
print("1. Testing root endpoint...")
try:
    response = requests.get(f"{API_BASE}/")
    if response.status_code == 200:
        print(f"   ✅ Root: {response.status_code}")
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
    else:
        print(f"   ❌ Root: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check docs
print("2. Testing /docs endpoint...")
try:
    response = requests.get(f"{API_BASE}/docs")
    if response.status_code == 200:
        print(f"   ✅ Docs: {response.status_code}")
        print(f"   Open: {API_BASE}/docs")
    else:
        print(f"   ❌ Docs: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check chat routes
print("3. Testing chat routes...")

routes_to_check = [
    "/api/v1/chat/stats",
    "/api/v1/chat/session/user001/status",
]

for route in routes_to_check:
    try:
        response = requests.get(f"{API_BASE}{route}")
        if response.status_code in [200, 404]:  # 404 is OK for session (means route exists)
            status = "✅" if response.status_code == 200 else "⚠️"
            print(f"   {status} {route}: {response.status_code}")
            if response.status_code == 200:
                print(f"       {response.json()}")
        else:
            print(f"   ❌ {route}: {response.status_code}")
    except Exception as e:
        print(f"   ❌ {route}: {e}")

print()

# Check OpenAPI schema
print("4. Checking available endpoints from OpenAPI...")
try:
    response = requests.get(f"{API_BASE}/openapi.json")
    if response.status_code == 200:
        openapi = response.json()
        paths = openapi.get('paths', {})
        print(f"   ✅ Found {len(paths)} endpoints:")
        for path in sorted(paths.keys()):
            methods = list(paths[path].keys())
            print(f"      - {path} ({', '.join(methods).upper()})")
    else:
        print(f"   ❌ Cannot get OpenAPI schema: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("="*70)
print("DIAGNOSIS:")
print("="*70)

# Try stats endpoint
try:
    response = requests.get(f"{API_BASE}/api/v1/chat/stats")
    if response.status_code == 404:
        print("\n❌ ISSUE FOUND: Chat routes NOT registered")
        print("\nSOLUTION:")
        print("  1. Check your src/api/main.py file")
        print("  2. Make sure it includes:")
        print("     from src.api.routes import chat_stateless")
        print("     app.include_router(chat_stateless.router, prefix='/api/v1/chat')")
        print("  3. Restart the API server")
        print("\n  OR use the main.py file provided in outputs folder")
    elif response.status_code == 200:
        print("\n✅ Chat routes are working!")
        data = response.json()
        print(f"\n   Active sessions: {data.get('active_sessions')}")
        print(f"   Redis connected: {data.get('redis_connected')}")
        print(f"   Context window: {data.get('context_window_size')}")
except Exception as e:
    print(f"\n❌ Cannot connect to API: {e}")
    print("\nMake sure API is running:")
    print("  uvicorn src.api.main:app --reload --host 0.0.0.0 --port 6262")

print()
