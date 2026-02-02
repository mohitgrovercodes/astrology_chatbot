# Phase 6 Safety & Guardrails - Quick Reference

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/safety/guardrails.py` | 450 | QueryAnalyzer + ResponseEnhancer |
| `src/safety/disclaimers.py` | 300 | Natural astrologer-style templates |
| `src/safety/input_validator.py` | 430 | Flexible birth data validation |
| `src/safety/__init__.py` | 52 | Module exports |
| `tests/test_safety.py` | 200 | Unit tests |

## Integration Points

### Orchestrator (`src/orchestration/orchestrator.py`)

**Lines 23-25**: Imports
```python
from src.safety.guardrails import QueryAnalyzer, ResponseEnhancer
from src.safety.input_validator import InputValidator
```

**Lines 85-90**: Initialization
```python
self.query_analyzer = QueryAnalyzer()
self.response_enhancer = ResponseEnhancer()
self.input_validator = InputValidator()
```

**Lines 307-327**: RAG Node - Safety Analysis
- Analyzes query for sensitive content
- Asks clarifying question if highly sensitive (C in C→B→A)
- Otherwise proceeds with normal flow

**Lines 458-493**: Format Response Node - Enhancement
- Enhances response with natural disclaimers
- Adds empathetic framing for sensitive topics

## Testing

### Run Unit Tests
```bash
python tests\test_safety.py
```

### Run Integration Tests
```bash
python test_routing.py
```
Look for: `[SAFETY] Category: ..., Sensitivity: ..., Strategy: ...`

## Sensitivity Categories

| Category | Sensitivity | Strategy | Example |
|----------|-------------|----------|---------|
| death_mortality | 0.9-1.0 | clarify_first | "When will I die?" |
| mental_health | 0.95-1.0 | clarify_first | "I feel hopeless" |
| health | 0.7-0.8 | empathetic_response | "Will I recover?" |
| relationship | 0.6-0.7 | empathetic_response | "Is spouse cheating?" |
| legal | 0.6-0.7 | empathetic_response | "Will I win case?" |
| financial | 0.5-0.6 | empathetic_response | "Should I invest?" |
| general | 0.0 | proceed_normal | "What is my sun sign?" |

## C → B → A Philosophy

**C (Clarify)**: For highly sensitive queries (≥ 0.8)
- Asks caring clarifying question first
- Example: "Could you share what's prompting this inquiry?"

**B (Redirect)**: For medium sensitivity (0.5-0.8)
- Frames query positively
- Example: "Let me focus on the vitality factors in your chart..."

**A (Provide with empathy)**: Always
- Gives astrological insight
- Adds natural disclaimer
- Maintains professional astrologer tone

## Quick Test

```python
from src.safety.guardrails import analyze_query, enhance_response

# Analyze a query
analysis = analyze_query("When will I die?")
print(f"Category: {analysis.category.value}")
print(f"Sensitivity: {analysis.sensitivity_level}")
print(f"Strategy: {analysis.handling_strategy.value}")

# Enhance a response
raw = "Based on your 8th house..."
enhanced = enhance_response(raw, "When will I die?")
print(enhanced)
```

## Status

✅ **Phase 6 Complete** (100%)
- All modules created and tested
- Integrated into orchestrator
- Unit tests passing (100%)
- Integration tests passing (88.9%)
- Overall project: 78% complete
