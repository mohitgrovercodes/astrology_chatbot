<!-- src\safety\README.md -->
# Safety System

A production-ready, LLM-unified safety classification system for the NakshatraAI astrology chatbot.

## Architecture

The classifier uses a **3-gate pipeline** that prioritizes accuracy over pattern-matching speed. All language and phrasing variants — Hinglish, romanized Indian scripts, mixed-script queries — are handled correctly by the LLM without regex.

```
Query
  │
  ▼
Gate 1 — Keyword Vulgar Block
  │  Fast keyword scan for explicit vulgar/abusive content.
  │  Hard-blocks immediately (< 1ms). No LLM call.
  │
  ▼
Gate 2 — LLM Vulgarity Check
  │  LLM-based vulgarity check.
  │  Automatically skipped for queries that are clearly astrological.
  │
  ▼
Gate 3 — Unified LLM Classifier
     Single LLM call with ~17 few-shot examples covering
     first-person vs. third-party, all domains, multilingual phrasing.
     Returns: category + sub_category + disclaimer_type + confidence
```

## Classification Categories

| Category | Description | Example |
|---|---|---|
| `HARD_BLOCK` | Never answer | "When will I die?", "Do I have cancer?" |
| `SOFT_BLOCK` | Polite decline | "Mere dost ki shaadi kab hogi?" (third-party chart) |
| `CONDITIONAL` | Answer with disclaimer | "Meri shaadi kab hogi?", "Should I invest now?" |
| `REFRAME` | Transform question | "Will I get rich?" → "What periods support wealth?" |
| `SAFE` | Answer normally | "What does Jupiter in 7th house mean?" |

### Key Classification Rules

- **First-person identification**: `Mera/Meri/Main` always = personal query (never third-party)
- **"paida hoga" rule**: "Mera bachha kab paida hoga?" = personal children timing → CONDITIONAL, not SOFT_BLOCK
- **Third-party**: any query about a named or implied third person's chart → SOFT_BLOCK
- **Meta-questions**: "What did I ask last time?" → SAFE

## Disclaimer Templates

Disclaimers are natural prose — no bracket labels, no bold headers. Language variants:
- English, Hindi (`hi`), Hinglish (`hi-lat`) have hardcoded templates
- All other languages are LLM-translated from the English base

Disclaimers are **only appended to DETAILED responses**, not to the short INITIAL answer.

## Package Contents

```
src/safety/
├── __init__.py        # Clean exports
├── models.py          # Pydantic models
├── templates.py       # Disclaimer + response templates (natural prose)
├── classifier.py      # 3-gate classifier logic
├── constitution.py    # System constitution injected into every LLM prompt
├── input_validator.py # Input sanitization
└── README.md          # This file
```

## Quick Start

```python
from src.safety import create_safety_classifier, get_disclaimer

classifier = create_safety_classifier(llm=your_llm, fast_llm=your_fast_llm)

result = classifier.classify("Meri shaadi kab hogi?")
print(result.decision.category)   # CONDITIONAL
print(result.decision.sub_category)  # relationship

if result.needs_disclaimer:
    disclaimer = get_disclaimer(result.decision.disclaimer_type, language="hi-lat")
    # append to DETAILED response only
```

## Integration with LangGraph

```python
def safety_check_node(state):
    result = classifier.classify(state["query"])
    state["safety_result"] = result

    if result.is_blocked:
        from src.safety import get_template
        state["answer"] = get_template(result.get_template_key(), language=state.get("detected_language", "en"))
        state["early_exit"] = True

    if result.needs_disclaimer:
        state["disclaimer_type"] = result.decision.disclaimer_type

    return state
```

## Extending the Classifier

### Add Few-Shot Examples

Edit the few-shot example block in `classifier.py`. Each example follows the format:
```
User: <query>
Output: {"category": "...", "sub_category": "...", "disclaimer_type": "...", "confidence": 0.95}
```

### Add New Disclaimer Templates

In `templates.py`, add your template to the appropriate language block. Keep it natural prose — no bracket labels or bold headers.

## Notes

- Safety checks are non-negotiable — do not disable `ENABLE_SAFETY_CHECKS` in production
- The classifier requires a `fast_llm` (gpt-4o-mini) instance; falls back to `llm` if not provided
- All classification decisions are logged at INFO level for auditing
