# API Test Commands (PowerShell)
# Copy and paste these commands to test the API

# Set your API key
$API_KEY = "my-dev-key-123"
$BASE_URL = "http://localhost:8000/api/v1"

# ============================================================================
# TEST 1: Health Check (No Auth)
# ============================================================================
Write-Host "`n=== TEST 1: Health Check ===" -ForegroundColor Cyan
curl -X GET "$BASE_URL/health"

# ============================================================================
# TEST 2: Get User Profile
# ============================================================================
Write-Host "`n`n=== TEST 2: Get User Profile ===" -ForegroundColor Cyan
curl -X GET "$BASE_URL/user/user001" `
  -H "X-API-Key: $API_KEY"

# ============================================================================
# TEST 3: Chat - Greeting (CHITCHAT)
# ============================================================================
Write-Host "`n`n=== TEST 3: Chat - Greeting ===" -ForegroundColor Cyan
curl -X POST "$BASE_URL/chat" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "query": "Hello! Who are you?",
    "user_id": "user001"
  }'

# ============================================================================
# TEST 4: Chat - Chart Request (CALCULATION_ONLY)
# ============================================================================
Write-Host "`n`n=== TEST 4: Chat - Chart Request ===" -ForegroundColor Cyan
curl -X POST "$BASE_URL/chat" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "query": "Show me my birth chart",
    "user_id": "user001"
  }'

# ============================================================================
# TEST 5: Chat - Prediction (RAG_WITH_CALCULATION)
# ============================================================================
Write-Host "`n`n=== TEST 5: Chat - Prediction ===" -ForegroundColor Cyan
curl -X POST "$BASE_URL/chat" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "query": "When will I get married?",
    "user_id": "user001"
  }'

# ============================================================================
# TEST 6: Calculate Vedic Chart
# ============================================================================
Write-Host "`n`n=== TEST 6: Calculate Vedic Chart ===" -ForegroundColor Cyan
curl -X POST "$BASE_URL/calculate/vedic/chart" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "date_of_birth": "1995-03-15",
    "time_of_birth": "14:30:00",
    "latitude": 26.9124,
    "longitude": 75.7873,
    "timezone": "Asia/Kolkata"
  }'

# ============================================================================
# TEST 7: Get Yogas
# ============================================================================
Write-Host "`n`n=== TEST 7: Get Yogas ===" -ForegroundColor Cyan
curl -X POST "$BASE_URL/calculate/vedic/yogas" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "date_of_birth": "1995-03-15",
    "time_of_birth": "14:30:00",
    "latitude": 26.9124,
    "longitude": 75.7873,
    "timezone": "Asia/Kolkata"
  }'

# ============================================================================
# TEST 8: Calculate Western Chart
# ============================================================================
Write-Host "`n`n=== TEST 8: Calculate Western Chart ===" -ForegroundColor Cyan
curl -X POST "$BASE_URL/calculate/western/chart" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "date_of_birth": "1995-03-15",
    "time_of_birth": "14:30:00",
    "latitude": 26.9124,
    "longitude": 75.7873,
    "timezone": "Asia/Kolkata"
  }'

Write-Host "`n`n=== All Tests Complete! ===" -ForegroundColor Green
Write-Host "Visit http://localhost:8000/api/docs for interactive testing" -ForegroundColor Yellow
