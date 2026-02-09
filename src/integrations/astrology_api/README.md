# Production Astrology API Integration

Complete production-grade integration layer for 3rd-party astrology APIs with Redis caching and RAG context preparation.

---

## 🎯 Overview

This integration provides:

✅ **30+ Astrology API Endpoints** - Birth charts, dashas, horoscopes, transits, yogas, remedies  
✅ **Redis Caching Layer** - Configurable TTL, automatic cache-aside pattern  
✅ **RAG-Ready Formatting** - Converts API responses to semantic text for vector embedding  
✅ **Production Features** - Retry logic, error handling, connection pooling, logging  
✅ **Clean Architecture** - Separated concerns, no impact on existing code  

---

## 📁 File Structure

```
src/
├── integrations/astrology_api/
│   ├── client.py              # Base API client (existing)
│   ├── extended_client.py     # ✨ NEW: 30+ production endpoints
│   └── __init__.py            # Updated exports
│
├── services/
│   ├── astrology_service.py   # ✨ NEW: Main orchestrator
│   ├── cache_manager.py       # ✨ NEW: Redis operations
│   ├── rag_context_formatter.py # ✨ NEW: RAG formatting
│   └── __init__.py            # ✨ NEW: Service exports
│
└── examples/
    └── production_integration_example.py # ✨ NEW: Usage examples
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install redis hiredis httpx pydantic tenacity
```

### 2. Set Environment Variables

```bash
# API Credentials
ASTRO_USERNAME=your_username
ASTRO_PASSWORD=your_password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Optional: Custom TTL (in seconds)
CACHE_TTL_BIRTH_CHART=86400    # 24 hours
CACHE_TTL_DASHAS=604800        # 7 days
CACHE_TTL_HOROSCOPE=3600       # 1 hour
```

### 3. Basic Usage

```python
from src.integrations.astrology_api import BirthDetailsRequest
from src.services import AstrologyDataService

# Initialize service
service = AstrologyDataService()
await service.initialize()

# User's birth details
birth_data = BirthDetailsRequest(
    day=15, month=8, year=1990,
    hour=14, min=30,
    lat=28.6139, lon=77.2090, tzone=5.5
)

# Fetch birth chart (auto-cached, RAG-formatted)
birth_chart = await service.get_birth_chart(
    user_id="user_123",
    birth_data=birth_data,
    format_for_rag=True
)

print(birth_chart["text"])  # RAG-ready text
```

---

## 🔧 Core Components

### 1. Extended API Client

**File**: [`extended_client.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/integrations/astrology_api/extended_client.py)

**30+ Endpoints**:
- Birth charts (Vedic & Western)
- Planetary positions
- Dashas (Vimshottari, Yogini, Char)
- Divisional charts (D1-D60)
- Horoscopes (daily, weekly, monthly, yearly)
- Transits
- Compatibility
- Yogas & Doshas
- Panchang & Choghadiya
- Remedies (gemstones, rudraksha)

### 2. Cache Manager

**File**: [`cache_manager.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/services/cache_manager.py)

**Features**:
- Namespaced keys: `astro:user_123:birth_chart:abc123`
- Configurable TTL per data type
- Cache-aside pattern: `get_or_fetch()`
- Graceful degradation on Redis failures
- Bulk invalidation: `invalidate_user_cache()`

### 3. RAG Context Formatter

**File**: [`rag_context_formatter.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/services/rag_context_formatter.py)

**Transforms**:
```json
{
  "planets": [{"name": "Sun", "sign": "Leo", "degree": 23.5}]
}
```

**Into**:
```
Sun is in Leo sign, 1 house at 23.5°
Moon is in Cancer sign, 12 house at 15.2°
...
```

### 4. Astrology Data Service

**File**: [`astrology_service.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/services/astrology_service.py)

**Main Orchestrator**:
- Unified interface for all data types
- Automatic caching with TTL
- Parallel data fetching
- RAG formatting on demand

---

## 📊 Architecture Flow

```
User Query: "What's my career prediction?"
    ↓
[Chatbot Orchestrator]
    ↓
[AstrologyDataService.get_all_astro_data()]
    ↓
┌─────────────────────────────────────┐
│ Check Redis Cache                   │
│  ├─ HIT: Return cached data         │
│  └─ MISS: Call API → Cache → Return │
└─────────────────────────────────────┘
    ↓
[RAGContextFormatter.format_for_retrieval()]
    ↓
Structured Text: "Sun in Leo, Moon in Cancer..."
    ↓
[RAG Engine] → Retrieve relevant interpretations
    ↓
[LLM] → Generate natural language response
    ↓
User Response
```

---

## 💡 Usage Examples

### Example 1: Complete Astrological Profile

```python
# Fetch all data in parallel (birth chart, dashas, horoscope, transits)
complete_data = await service.get_all_astro_data(
    user_id="user_123",
    birth_data=birth_data,
    include_horoscope=True,
    include_transits=True,
    format_for_rag=True
)

# Ready for RAG
rag_context = complete_data["text"]
```

### Example 2: Individual Endpoints

```python
# Vimshottari Dashas
dashas = await service.get_dashas(
    user_id="user_123",
    birth_data=birth_data,
    dasha_type="vimshottari"
)

# Daily Horoscope
horoscope = await service.get_horoscope(
    user_id="user_123",
    birth_data=birth_data,
    period="daily"
)

# Current Transits
transits = await service.get_transits(
    user_id="user_123",
    birth_data=birth_data
)
```

### Example 3: Cache Invalidation

```python
# User updates birth time
await service.invalidate_user_cache("user_123")

# Next fetch will call API, not cache
fresh_data = await service.get_birth_chart(
    user_id="user_123",
    birth_data=new_birth_data
)
```

### Example 4: RAG Integration

```python
# Step 1: Get astrological context
astro_context = await service.get_all_astro_data(
    user_id="user_123",
    birth_data=birth_data,
    format_for_rag=True
)

# Step 2: Query RAG with context
rag_response = await rag_engine.query(
    query="What career opportunities will I have?",
    context=astro_context["text"],
    metadata=astro_context["metadata"]
)

# Step 3: Generate LLM response
final_response = await llm.generate(
    prompt=rag_response["prompt"],
    context=rag_response["retrieved_chunks"]
)
```

---

## ⚙️ Configuration

### Cache TTL Strategy

| Data Type | Default TTL | Rationale |
|-----------|-------------|-----------|
| Birth Chart | 24 hours | Rarely changes |
| Dashas | 7 days | Static for long periods |
| Horoscope (Daily) | 1 hour | Changes daily |
| Transits | 30 minutes | Changes frequently |
| Ayanamsa | 7 days | Changes very slowly |

### Custom Configuration

```python
from src.services import CacheConfig

cache_config = CacheConfig(
    host="localhost",
    port=6379,
    ttl_birth_chart=7200,  # 2 hours
    ttl_horoscope=1800,    # 30 minutes
    key_prefix="my_app"
)

service = AstrologyDataService(cache_config=cache_config)
```

---

## 🔍 Error Handling

### Graceful Fallback Strategy

```
1. Check Redis → HIT: return cached
              → MISS: call API

2. Call API → SUCCESS: cache + return
           → FAILURE: check stale cache

3. Stale cache → EXISTS: return with warning
              → NONE: return error
```

### Exception Types

```python
from src.integrations.astrology_api import (
    AstrologyAPIError,
    AuthenticationError,
    ValidationError,
    RateLimitError
)

try:
    data = await service.get_birth_chart(user_id, birth_data)
except AuthenticationError:
    # Invalid credentials
except ValidationError:
    # Invalid birth data
except RateLimitError:
    # API quota exceeded
except AstrologyAPIError as e:
    # Other API errors
```

---

## 📈 Performance Considerations

### Caching Benefits

- **First call**: ~500-1000ms (API latency)
- **Cached call**: ~5-10ms (Redis lookup)
- **Improvement**: **50-100x faster**

### Parallel Fetching

```python
# Sequential (slow)
birth_chart = await service.get_birth_chart(...)
dashas = await service.get_dashas(...)
# Total: ~2 seconds

# Parallel (fast)
complete_data = await service.get_all_astro_data(...)
# Total: ~1 second (concurrent API calls)
```

---

## 🧪 Testing

Run the examples:

```bash
python examples/production_integration_example.py
```

Expected output:
- Cache hit/miss logs
- RAG-formatted text
- Metadata structures
- Timing comparisons

---

## 🔗 Integration with Existing System

### Chatbot Orchestrator Integration

```python
# In your chatbot orchestrator
from src.services import AstrologyDataService

class ChatbotOrchestrator:
    def __init__(self):
        self.astro_service = AstrologyDataService()
        # ... other components
    
    async def handle_user_query(self, user_id, query, birth_data):
        # Get astrological context
        astro_context = await self.astro_service.get_all_astro_data(
            user_id=user_id,
            birth_data=birth_data,
            format_for_rag=True
        )
        
        # Pass to RAG
        rag_response = await self.rag_engine.query(
            query=query,
            context=astro_context["text"]
        )
        
        # Generate response
        return await self.llm.generate(rag_response)
```

---

## 🎓 Design Principles

### ✅ Separation of Concerns

- **API Client**: Handles HTTP communication
- **Cache Manager**: Handles Redis operations
- **Formatter**: Handles RAG transformation
- **Service**: Orchestrates all components

### ✅ No Impact on Existing Code

All new files in separate directories:
- `src/integrations/astrology_api/extended_client.py` (new)
- `src/services/` (new directory)

Existing code untouched.

### ✅ Production-Ready

- Retry logic with exponential backoff
- Comprehensive error handling
- Structured logging
- Connection pooling
- Type safety (Pydantic)

---

## 📚 Next Steps

1. **Test the integration** with your Redis instance
2. **Wire up with your RAG engine** using the formatted context
3. **Monitor cache hit rates** and adjust TTLs
4. **Add more endpoints** as needed from AstrologyAPI.com docs

---

## 🆘 Troubleshooting

### Redis Connection Failed

```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Check environment variables
echo $REDIS_HOST
echo $REDIS_PORT
```

### API Authentication Failed

```bash
# Verify credentials
echo $ASTRO_USERNAME
echo $ASTRO_PASSWORD

# Test API directly
curl -u username:password https://json.astrologyapi.com/v1/birth_details
```

### Import Errors

```bash
# Ensure all dependencies installed
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

---

**Questions?** Check the implementation plan: [`implementation_plan.md`](file:///C:/Users/mogr1/.gemini/antigravity/brain/edcb3df8-6a89-4925-bc6e-d9b178ffc1f1/implementation_plan.md)
