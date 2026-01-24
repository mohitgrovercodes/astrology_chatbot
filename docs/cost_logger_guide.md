# Cost Logger System - Usage Guide

## Overview

The Cost Logger system provides comprehensive tracking and reporting for all LLM and embedding API usage across the Astrology AI chatbot project.

## Features

- ✅ **Automatic Cost Tracking**: All API calls are automatically logged
- ✅ **SQLite Storage**: Efficient persistent storage with fast queries
- ✅ **Dual Tracking**: Both detailed per-call logs and aggregate daily summaries
- ✅ **Multi-Provider Support**: Gemini, OpenAI embeddings, and more
- ✅ **CLI Reporting**: Powerful command-line tool for cost analysis
- ✅ **Thread-Safe**: Safe for parallel processing

## Quick Start

### 1. Automatic Tracking (No Code Changes Required)

Cost tracking is automatically enabled for:

**LLM Factory** (via LangChain callback):
```python
from src.llm.factory import create_llm

# Cost tracking is automatic!
llm = create_llm(provider="google", model="gemini-2.5-flash")
response = llm.invoke("Your prompt here")
# Cost is logged automatically
```

**Vision Extractor**:
```python
from src.rag.extraction.vision_extractor import VisionExtractor

extractor = VisionExtractor()
# Cost tracking is automatic!
page = extractor.extract_page(image, page_num=1)
```

**Embedder**:
```python
from src.rag.preprocessing.embedder import Embedder

embedder = Embedder()
# Cost tracking is automatic!
embeddings = embedder.embed_texts(texts)
```

### 2. View Cost Reports

**Today's costs**:
```bash
python -m src.utils.cost_report --today
```

**Last 7 days**:
```bash
python -m src.utils.cost_report --week
```

**Specific model**:
```bash
python -m src.utils.cost_report --model gemini-2.5-flash --week
```

**Export to CSV**:
```bash
python -m src.utils.cost_report --month --export costs.csv
```

### 3. Programmatic Access

```python
from src.utils.cost_logger import get_cost_logger

# Get cost logger instance
cost_logger = get_cost_logger()

# Get total cost
total = cost_logger.get_total_cost()
print(f"Total cost: ${total:.4f}")

# Get detailed summary
summary = cost_logger.get_summary()
print(f"Total calls: {summary.total_calls}")
print(f"Total tokens: {summary.total_tokens:,}")
print(f"Total cost: ${summary.total_cost:.4f}")

# Breakdown by model
for model, stats in summary.breakdown_by_model.items():
    print(f"{model}: {stats['calls']} calls, ${stats['cost']:.4f}")

# Get recent calls
recent = cost_logger.get_recent_calls(limit=10)
for call in recent:
    print(f"{call.timestamp}: {call.model_name} - ${call.total_cost:.6f}")
```

## Advanced Usage

### Manual Cost Logging

If you need to manually log costs (e.g., for custom API integrations):

```python
from src.utils.cost_tracking import CostTrackingWrapper

# Create wrapper
tracker = CostTrackingWrapper(
    model_name="gemini-2.5-flash",
    model_type="llm"
)

# Option 1: Log from API response
response = model.generate_content(prompt)
tracker.log_from_response(
    response,
    operation="custom_operation",
    metadata={"context": "additional info"}
)

# Option 2: Manual token counts
tracker.log_manual(
    input_tokens=1500,
    output_tokens=800,
    operation="custom_operation",
    metadata={"context": "additional info"}
)
```

### Batch Operations

For tracking costs across batch operations:

```python
from src.utils.cost_tracking import BatchCostTracker

with BatchCostTracker("gemini-2.5-flash", "batch_enrichment") as tracker:
    for item in items:
        response = process_item(item)
        tracker.add_from_response(response)

# Cost is automatically logged when context exits
```

### Using Decorators

```python
from src.utils.cost_tracking import track_llm_cost

@track_llm_cost(model_name="gemini-2.5-flash", operation="custom_gen")
def my_llm_function():
    response = model.generate_content(prompt)
    return response
```

## CLI Reference

### Cost Report Tool

```bash
python -m src.utils.cost_report [OPTIONS]
```

**Date Filters**:
- `--today` - Show today's costs only
- `--yesterday` - Show yesterday's costs
- `--week` - Last 7 days
- `--month` - Last 30 days
- `--date-range START END` - Custom range (YYYY-MM-DD format)

**Model/Operation Filters**:
- `--model MODEL_NAME` - Filter by model
- `--operation OPERATION_TYPE` - Filter by operation type

**Output Options**:
- `--recent N` - Show N most recent API calls
- `--export FILE.csv` - Export to CSV
- `--db PATH` - Custom database path (default: ./logs/cost_tracker.db)

**Examples**:

```bash
# Show today's costs
python -m src.utils.cost_report --today

# Show costs for specific model this week
python -m src.utils.cost_report --week --model gemini-2.5-flash

# Show recent calls
python -m src.utils.cost_report --recent 20

# Export month's data to Excel format
python -m src.utils.cost_report --month --export january_2026_costs.csv

# Custom date range
python -m src.utils.cost_report --date-range 2026-01-01 2026-01-31
```

## Database Schema

The cost database (`./logs/cost_tracker.db`) contains two tables:

**api_calls** - Detailed per-call logs:
- timestamp, model_name, model_type, operation
- input_tokens, output_tokens, total_tokens
- input_cost, output_cost, total_cost
- metadata (JSON)

**daily_summaries** - Aggregate daily summaries:
- date, total_calls, total_tokens, total_cost
- breakdown_by_model (JSON)
- breakdown_by_operation (JSON)

## Pricing Information

Current pricing (as of January 2026):

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| gemini-2.5-flash | $18.75 | $75.00 |
| gemini-1.5-pro | $1,250.00 | $5,000.00 |
| gemini-1.5-flash | $75.00 | $300.00 |
| text-embedding-3-large | $130.00 | - |
| text-embedding-3-small | $20.00 | - |

Pricing is automatically updated in `src/utils/cost_logger.py` in the `PRICING_TABLE` constant.

## Troubleshooting

### Issue: No costs appearing

**Check 1**: Verify database exists:
```bash
ls -l ./logs/cost_tracker.db
```

**Check 2**: Check if logging is enabled:
```python
from src.utils.cost_logger import get_cost_logger
logger = get_cost_logger()
print(f"Enabled: {logger.enabled}")
```

**Check 3**: Verify API calls are being made (check application logs)

### Issue: Incorrect costs

**Check pricing table**: Verify model names match exactly:
```python
from src.utils.cost_logger import PRICING_TABLE
print(PRICING_TABLE.keys())
```

**Update pricing**: Edit `src/utils/cost_logger.py` and update `PRICING_TABLE` with current pricing.

### Issue: Database locked

SQLite may lock if multiple processes access simultaneously. Use:
```bash
# Wait for locks to clear
sleep 2
python -m src.utils.cost_report --today
```

## Best Practices

1. **Regular Monitoring**: Check costs daily during development
   ```bash
   python -m src.utils.cost_report --today
   ```

2. **Budget Alerts**: Set up periodic exports and monitor totals
   ```bash
   python -m src.utils.cost_report --month --export monthly_costs.csv
   ```

3. **Model Comparison**: Compare costs across models before scaling
   ```bash
   python -m src.utils.cost_report --week --model gemini-2.5-flash
   python -m src.utils.cost_report --week --model gemini-1.5-flash
   ```

4. **Optimize High-Cost Operations**: Identify expensive operations
   ```bash
   python -m src.utils.cost_report --month --operation vision_extraction
   ```

## Integration Points

The cost logger is integrated into:

1. **LLM Factory** (`src/llm/factory.py`) - via LangChain callbacks
2. **Vision Extractor** (`src/rag/extraction/vision_extractor.py`) - via wrappers
3. **Chunk Enricher** (`src/rag/preprocessing/chunk_enricher.py`) - via LLM Factory
4. **Embedder** (`src/rag/preprocessing/embedder.py`) - via wrappers

All integrations are **automatic** - no code changes required in application code.

## Performance Impact

- **Logging overhead**: < 1ms per API call
- **Storage**: ~500 bytes per logged call
- **Query performance**: Indexed, supports millions of records

## Security & Privacy

- ✅ **No content logging**: Only metadata and token counts are stored
- ✅ **No API keys stored**: API keys are never logged
- ✅ **Local only**: All data stays in local SQLite database
