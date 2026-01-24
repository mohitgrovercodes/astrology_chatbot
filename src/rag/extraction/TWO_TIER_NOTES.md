# Two-Tier Extraction Logic - Implementation Notes

## Current extract_page flow:
1. Classify page (or use forced type)
2. Extract based on type (text/table/mixed)
3. Build ExtractedPage with metadata and content blocks

## Changes needed:
1. Add confidence parsing from JSON response
2. Wrap extraction in _extract_with_model() helper
3. Check confidence after extraction
4. Retry with gemini-2.5-pro if confidence < threshold
5. Populate confidence and retry_metadata fields

## Key method to add:
`_extract_with_model(image, page_num, model_name)` - extracts with specific model

## Confidence parsing:
Parse "confidence" object from extraction JSON response and create ConfidenceMetadata

## Retry logic:
After initial extraction, if confidence.overall_score < 0.8, call _extract_with_model again with upgrade model
