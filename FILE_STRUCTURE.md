<!-- FILE_STRUCTURE.md -->
# File Structure Summary

After consolidation, the integration now consists of **3 main files**:

## For Chatbot Team

### [`backend_data_adapter.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/services/backend_data_adapter.py)
**All-in-one chatbot service**

Includes:
- `RAGContextFormatter` - Formats API responses to semantic text
- `BackendDataAdapter` - Receives & validates backend data
- `BackendAstroData` - Pydantic schema for data validation
- `process_backend_data_for_rag()` - Convenience function

**Usage**:
```python
from src.services import process_backend_data_for_rag

# Receive data from backend
backend_data = {...}

# Process for RAG
rag_context = process_backend_data_for_rag(backend_data)

# Use with RAG engine
response = await rag_engine.query(
    query=user_query,
    context=rag_context["text"]
)
```

---

## For Backend Team

### [`extended_client.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/integrations/astrology_api/extended_client.py)
**30+ astrology API endpoints**

```python
from src.integrations.astrology_api import ExtendedAstrologyAPIClient

client = ExtendedAstrologyAPIClient()
birth_chart = await client.get_vedic_birth_chart(birth_data)
```

### [`cache_manager.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/services/cache_manager.py)
**Redis caching layer**

```python
from src.services import CacheManager

cache = CacheManager()
await cache.connect()

# Cache-aside pattern
data = await cache.get_or_fetch(
    user_id="user_123",
    data_type="birth_chart",
    fetch_fn=lambda: client.get_vedic_birth_chart(birth_data)
)
```

### [`astrology_service.py`](file:///d:/AI/IMGProjects/astro_chatbot/astro_chatbot/src/services/astrology_service.py)
**Orchestrator (optional helper)**

Combines API client + cache for backend convenience
```python
from src.services import AstrologyDataService

service = AstrologyDataService()
data = await service.get_all_astro_data(user_id, birth_data)
```

---

## File Count Summary

**Before**: 5 files (extended_client, cache_manager, rag_formatter, backend_adapter, astrology_service)  
**After**: 4 files (merged rag_formatter into backend_adapter)

**Chatbot needs**: 1 file (`backend_data_adapter.py`)  
**Backend needs**: 2-3 files (`extended_client.py`, `cache_manager.py`, optional `astrology_service.py`)

---

## Quick Import Guide

### Chatbot
```python
from src.services import (
    BackendDataAdapter,
    BackendAstroData,
    RAGContextFormatter,
    process_backend_data_for_rag
)
```

### Backend
```python
from src.integrations.astrology_api import ExtendedAstrologyAPIClient
from src.services import CacheManager, CacheConfig, AstrologyDataService
```
