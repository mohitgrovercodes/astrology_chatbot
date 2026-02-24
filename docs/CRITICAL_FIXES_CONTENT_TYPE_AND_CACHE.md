# CRITICAL FIXES: Content-Type Filter & Cache Key Mismatch

## 🚨 BUG 1: Content-Type Filter Removing All Results

### Root Cause:
```python
# In AstrologyRetriever.retrieve() with intent parameter
if intent and not filters:
    intent_content_preferences = {
        'PREDICTION': ['interpretation', 'prediction'],
        'INTERPRETATION': ['interpretation', 'general'],
        'RAG_ONLY': ['general', 'interpretation'],  # ← Applied!
        'LEARNING': ['general', 'educational'],
    }
    
    content_filter = {"content_type": {"$in": preferred_types}}
    where_clause = content_filter
```

**Problem:** Your ChromaDB chunks don't have `content_type` metadata!

**Evidence:**
```
Sample metadata keys: ['chapter', 'chunk_id', 'entity_concepts', 'entity_houses', 
                       'entity_nakshatras', 'entity_planets', 'entity_signs', 
                       'entity_yogas', 'section', 'source_book', 'source_pages', 
                       'token_count', 'tradition', 'unit_id', 'verse_number', 
                       'verse_sanskrit']
```

**NO `content_type` field!**

**Result:** Filter `{'content_type': {'$in': [...]}}` matches 0 chunks → Returns empty list

---

### FIX 1: Make Content-Type Filter Optional

**File:** `src/rag/retriever.py` (the fixed one with intent parameter)

**Find lines ~167-188 (the intent-based content type filtering):**

```python
# APPLY INTENT-BASED CONTENT TYPE FILTERING
# Different intents benefit from different content types
if intent and not filters:  # Only if user didn't provide custom filters
    intent_content_preferences = {
        'PREDICTION': ['interpretation', 'prediction'],
        'INTERPRETATION': ['interpretation', 'general'],
        'RAG_ONLY': ['general', 'interpretation'],
        'LEARNING': ['general', 'educational'],
    }
    
    if intent in intent_content_preferences:
        preferred_types = intent_content_preferences[intent]
        content_filter = {"content_type": {"$in": preferred_types}}
        
        if where_clause:
            where_clause = {"$and": [where_clause, content_filter]}
        else:
            where_clause = content_filter
            
        logger.info(f"Applied content type filter for intent {intent}: {preferred_types}")
```

**REPLACE WITH:**

```python
# APPLY INTENT-BASED CONTENT TYPE FILTERING (Optional - only if metadata exists)
# Different intents benefit from different content types
# NOTE: Only applied if content_type metadata exists in your chunks
if intent and not filters:  # Only if user didn't provide custom filters
    intent_content_preferences = {
        'PREDICTION': ['interpretation', 'prediction'],
        'INTERPRETATION': ['interpretation', 'general'],
        'RAG_ONLY': ['general', 'interpretation'],
        'LEARNING': ['general', 'educational'],
    }
    
    if intent in intent_content_preferences:
        preferred_types = intent_content_preferences[intent]
        
        # ✅ FIX: Check if content_type metadata exists before filtering
        # Try a test query to see if any chunks have content_type
        try:
            test_result = self.collection.get(limit=1, include=["metadatas"])
            has_content_type = (
                test_result and 
                test_result.get('metadatas') and 
                len(test_result['metadatas']) > 0 and
                'content_type' in test_result['metadatas'][0]
            )
            
            if has_content_type:
                content_filter = {"content_type": {"$in": preferred_types}}
                
                if where_clause:
                    where_clause = {"$and": [where_clause, content_filter]}
                else:
                    where_clause = content_filter
                    
                logger.info(f"Applied content type filter for intent {intent}: {preferred_types}")
            else:
                logger.info(f"Skipping content type filter (metadata not present in chunks)")
        except Exception as e:
            logger.warning(f"Could not check content_type metadata: {e}. Skipping filter.")
```

---

### FIX 1 (SIMPLER ALTERNATIVE): Just Disable the Filter

If you don't plan to use content_type metadata, simply comment out this entire section:

```python
# APPLY INTENT-BASED CONTENT TYPE FILTERING
# if intent and not filters:
#     # Disabled: chunks don't have content_type metadata
#     pass
```

---

## 🚨 BUG 2: Chart Cache Key Mismatch

### Root Cause:

**Orchestrator stores chart with key:**
```python
key = f"session:{user_id}:chart"
```

**chat_stateless retrieves with different key:**
```python
key = f"user:{user_id}:chart"  # ← Mismatch!
```

### Evidence from Your Logs:

```
Request 1:
[CACHE] 💾 Storing NEW chart data...
[CACHE] ✅ Chart stored

Request 2:
[CACHED DATA]
  Chart: ❌ Not cached  ← Should be cached!
```

**The chart WAS stored, but under a different key!**

---

### FIX 2: Standardize Cache Keys

You need to check which key format is being used in each place.

**File:** `src/api/routes/chat_stateless.py`

**Find the SessionManager class methods:**

```python
def store_chart_data(self, user_id: str, chart_data: dict):
    """Store chart data in Redis."""
    key = f"session:{user_id}:chart"  # Check this key!
    self.redis_client.setex(
        key,
        60 * 60 * 24 * 7,  # 7 days
        json.dumps(chart_data)
    )

def get_chart_data(self, user_id: str) -> Optional[Dict]:
    """Retrieve chart data from Redis."""
    key = f"session:{user_id}:chart"  # Check this key!
    data = self.redis_client.get(key)
    return json.loads(data) if data else None
```

**MAKE SURE both methods use the SAME key format!**

**Current Keys:**
```python
# In SessionManager (chat_stateless.py)
CHART_KEY = f"session:{user_id}:chart"
DASHA_KEY = f"session:{user_id}:dasha"
TRANSIT_KEY = f"session:{user_id}:transit"
SUMMARY_KEY = f"session:{user_id}:summary"
HISTORY_KEY = f"session:{user_id}:history"
```

**If orchestrator uses different keys, update orchestrator to match!**

---

### FIX 2 (DETAILED): Check Both Files

#### Step 1: Check chat_stateless.py SessionManager

**Find around line 622:**

```python
def store_chart_data(self, user_id: str, chart_data: dict):
    key = f"session:{user_id}:chart"
    print(f"[SESSION] Storing chart with key: {key}")  # ← Add this!
    self.redis_client.setex(key, 60 * 60 * 24 * 7, json.dumps(chart_data))

def get_chart_data(self, user_id: str) -> Optional[Dict]:
    key = f"session:{user_id}:chart"
    print(f"[SESSION] Retrieving chart with key: {key}")  # ← Add this!
    data = self.redis_client.get(key)
    if data:
        print(f"[SESSION] ✅ Found chart in Redis")
    else:
        print(f"[SESSION] ❌ No chart found at key: {key}")
    return json.loads(data) if data else None
```

#### Step 2: Check if orchestrator has different cache methods

**Search orchestrator.py for cache storage:**

```bash
grep -n "redis\|cache" orchestrator.py
```

**If orchestrator has its own cache methods, they might use different keys!**

---

### FIX 2 (NUCLEAR OPTION): Clear Redis and Restart

If key format was changed recently:

```bash
# Connect to Redis
redis-cli

# Check what keys exist
KEYS session:*
KEYS user:*

# Clear all if needed
FLUSHDB

# Exit
exit
```

Then restart API and test fresh.

---

## 📋 COMPLETE FIX CHECKLIST

### Fix 1: Content-Type Filter

- [ ] Open `src/rag/retriever.py` (the one with intent parameter)
- [ ] Find the content_type filtering section (~line 167-188)
- [ ] Either:
  - [ ] Option A: Add the check for metadata existence (safe)
  - [ ] Option B: Comment out the entire filter section (simple)
- [ ] Save file

### Fix 2: Chart Cache Keys

- [ ] Open `src/api/routes/chat_stateless.py`
- [ ] Add debug logging to `store_chart_data` and `get_chart_data` methods
- [ ] Verify keys match: `session:{user_id}:chart`
- [ ] Check if orchestrator has its own cache methods
- [ ] If different keys found, standardize them
- [ ] Optional: Clear Redis and restart fresh

### Restart & Test

- [ ] Restart API
- [ ] Make request 1: Check logs for "Storing chart with key: session:..."
- [ ] Make request 2: Check logs for "Retrieving chart with key: session:..."
- [ ] Verify keys match
- [ ] Verify retrieval returns results (not 0 chunks)

---

## 🔍 DIAGNOSTIC COMMANDS

### Check Redis Keys

```bash
redis-cli KEYS "*chart*"
```

Expected output:
```
1) "session:test_user_123:chart"
```

### Check Key Content

```bash
redis-cli GET "session:test_user_123:chart"
```

Should return JSON data, not nil.

### Check Retrieval

Add this temporary test in chat_stateless.py:

```python
# After storing chart
stored_chart = session_manager.get_chart_data(user_id)
print(f"[TEST] Immediately retrieved: {stored_chart is not None}")
```

Should print: `[TEST] Immediately retrieved: True`

---

## 🎯 EXPECTED RESULTS AFTER FIXES

### Request 1:
```
[RAG] Retrieving knowledge...
[RAG] Retrieved 8 chunks  ← Not 0!

[SESSION] Storing chart with key: session:test_user:chart
[CACHE] ✅ Chart stored
```

### Request 2:
```
[SESSION] Retrieving chart with key: session:test_user:chart
[SESSION] ✅ Found chart in Redis

[CACHED DATA]
  Chart: ✅ Cached  ← Fixed!

[CACHE] ✅ Passing cached chart to orchestrator

[RAG] Retrieved 8 chunks  ← Not 0!
```

---

## 📝 QUICK FIXES (Copy-Paste Ready)

### Quick Fix 1: Disable Content-Type Filter

**File:** `src/rag/retriever.py` around line 167

**Find:**
```python
# APPLY INTENT-BASED CONTENT TYPE FILTERING
if intent and not filters:
```

**Replace entire section with:**
```python
# APPLY INTENT-BASED CONTENT TYPE FILTERING
# DISABLED: Chunks don't have content_type metadata
# if intent and not filters:
#     pass
```

### Quick Fix 2: Add Cache Key Logging

**File:** `src/api/routes/chat_stateless.py` around line 622

**Add to store_chart_data:**
```python
def store_chart_data(self, user_id: str, chart_data: dict):
    key = f"session:{user_id}:chart"
    print(f"[REDIS] STORE key={key}")  # ← Add this
    self.redis_client.setex(key, 60 * 60 * 24 * 7, json.dumps(chart_data))
```

**Add to get_chart_data:**
```python
def get_chart_data(self, user_id: str) -> Optional[Dict]:
    key = f"session:{user_id}:chart"
    print(f"[REDIS] GET key={key}")  # ← Add this
    data = self.redis_client.get(key)
    print(f"[REDIS] Found={data is not None}")  # ← Add this
    return json.loads(data) if data else None
```

---

**Fix content-type filter first (causes 0 results), then verify cache keys match!**
