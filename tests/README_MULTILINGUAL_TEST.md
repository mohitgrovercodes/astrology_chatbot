# Multilingual RAG Performance Test

## Purpose

Test your **current OpenAI embeddings** to see if they handle multilingual queries well enough, or if you need to upgrade to Cohere/Voyage multilingual embeddings.

## What This Tests

**3 Difficulty Levels:**
1. **Simple** - Universal concepts (moon sign, zodiac)
2. **Domain** - Astrology terms (Sade Sati, Mahadasha)
3. **Sanskrit** - Romanized/native terms (Guru, Shani, nakshatra)

**3 Languages:**
- Hindi (Devanagari script)
- Tamil (Tamil script)
- Hinglish (Romanized Hindi)

## How to Run

```bash
# Make sure your vector database is set up
cd D:\AI\IMGProjects\astro_chatbot\astro_chatbot

# Run the test
python tests/test_multilingual_rag.py
```

## What to Look For

### Good Performance (Keep Current Embeddings)
```
OVERALL PERFORMANCE:
  Average Similarity: 0.750+
  Average Topic Coverage: 70%+
  
QUALITY ASSESSMENT:
  Overall Grade: A or B
  Recommendation: Current embeddings working well!
```

### Poor Performance (Upgrade Needed)
```
OVERALL PERFORMANCE:
  Average Similarity: <0.600
  Average Topic Coverage: <50%
  
QUALITY ASSESSMENT:
  Overall Grade: C or D
  Recommendation: STRONGLY recommend multilingual embeddings
```

## Interpreting Results

**Average Similarity:**
- 0.8+ = Excellent match
- 0.6-0.8 = Good match
- 0.4-0.6 = Mediocre match
- <0.4 = Poor match

**Topic Coverage:**
- 80%+ = Retrieved correct content
- 50-80% = Partial match
- <50% = Missed key concepts

## What to Do After

### If Grade is A or B:
✅ Keep current OpenAI embeddings
- They work well enough for your use case
- Save time and money
- No migration needed

### If Grade is C or D:
❌ Upgrade to multilingual embeddings
- Cost: ~$1-2 for re-embedding
- Benefit: 2-3x better multilingual retrieval
- Time: 2-3 hours migration

## Example Output

```
==================================================
Language: HINDI
Query: शनि की साढ़ेसाती कब शुरू होती है?
English: When does Sade Sati start?
Difficulty: domain
==================================================

Retrieved 5 chunks:

[1] Score: 0.723 | Source: Brihat Parasara Hora Sastra
    Topics: ['saturn', 'sade sati', 'transit']
    Text: Saturn's seven and a half year period...

[2] Score: 0.681 | Source: Phaladeepika
    Topics: ['saturn', '7.5 years']
    Text: When Saturn transits...

RESULTS SUMMARY:
  Average Similarity: 0.702
  Topic Coverage: 80% (4/5)
  Quality: ✓ GOOD
```

## Troubleshooting

**Error: "Collection not found"**
- Make sure your vector database is initialized
- Check `data/vectordb/` exists with chunks

**Error: "Retriever not initialized"**
- Set `OPENAI_API_KEY` environment variable
- Check embedder is working: `python -c "from src.rag.preprocessing.embedder import Embedder; e = Embedder(); print('OK')"`

**Error: "No chunks retrieved"**
- Your knowledge base might be empty
- Run ingestion pipeline first
