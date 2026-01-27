# Quick Reference - Vision Extraction System

## 🚀 Quick Start

```bash
# Run batch extraction with hybrid strategy
python batch_extract.py --pdf "data/raw/your_book.pdf" --start 1 --end 500
```

## 📊 Model Selection (Automatic)

| Page Type | Model Used | Speed | Cost |
|-----------|-----------|-------|------|
| Text-heavy | Flash-Lite | ⚡⚡ Fast | 💰 Cheap |
| Table-heavy | Flash | ⚡ Medium | 💰💰 Medium |
| Low confidence | Pro | 🐌 Slow | 💰💰💰 Expensive |

## ⚙️ Configuration Presets

### Recommended (Hybrid)
```python
config = ExtractionConfig(
    enable_hybrid_strategy=True,
    confidence_threshold=0.90,
    enable_content_validation=True,
    max_workers=5
)
```

### Speed-Optimized
```python
config = ExtractionConfig(
    primary_model="gemini-2.5-flash-lite",
    enable_hybrid_strategy=False,
    enable_auto_upgrade=False,
    max_workers=10
)
```

### Quality-Optimized
```python
config = ExtractionConfig(
    primary_model="gemini-2.5-flash",
    confidence_threshold=0.95,
    enable_auto_upgrade=True
)
```

## 🔍 Monitoring

### Check Validation Flags
```python
for page in result.pages:
    if page.confidence and "validation_override" in page.confidence.flags:
        print(f"⚠️ Page {page.metadata.page_number}: {page.confidence.reasoning}")
```

### Key Metrics
- **Confidence < 0.90** → Pro model fallback triggered
- **`validation_override` flag** → Content quality issue detected
- **`high_empty_ratio` flag** → >50% empty blocks
- **`low_text_volume` flag** → <100 chars extracted

## 📈 Performance Expectations

| Pages | Time (5 workers) | Cost (Hybrid) |
|-------|-----------------|---------------|
| 50 | ~2 min | ~$0.01 |
| 500 | ~20 min | ~$0.10 |
| 5000 | ~3 hours | ~$1.00 |

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Low confidence | Check `validation_override` flags |
| Empty blocks | Enable `enable_content_validation=True` |
| Slow processing | Increase `max_workers` to 7-10 |
| High cost | Disable `enable_auto_upgrade` |

## 📚 Documentation

- **Production Guide:** `docs/VISION_EXTRACTION_PRODUCTION.md`
- **Implementation Summary:** `docs/IMPLEMENTATION_SUMMARY_2026-01-27.md`
- **Project Status:** `docs/PROJECT_STATUS.md`
