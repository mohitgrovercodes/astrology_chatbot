# extract_rules_json_gemini.py
"""
Vedic Astrology Rule Extraction Script (JSON Input + Gemini)

Extracts validation rules from JSON-formatted processed texts using Google Gemini.
Handles complex structures like tables.

Usage:
    python extract_rules_json_gemini.py --input-dir ./data/processed_json --output rules.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import sys
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from vedic_validation_schema import (
    VedicValidationRule,
    VedicValidationRuleSet,
    ValidationCategory,
    ValidationSeverity,
    QueryType,
    PredictionStage,
    CheckLogic,
    RuleCancellation,
    LagnaSpecificRule
)

# Google Gemini setup
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    import google.generativeai as genai
except ImportError:
    print("ERROR: Install required packages:")
    print("pip install langchain-google-genai google-generativeai")
    sys.exit(1)


RULE_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert in Vedic astrology extracting validation rules from classical texts.

Your task: Extract NON-NEGOTIABLE validation rules that MUST be checked during astrological analysis.

Focus on rules about:
1. **Planetary States**: Combustion, retrogression, planetary war, dignity
2. **Divisional Confirmation**: When D9/D10/other divisionals must be checked
3. **Lagna-Specific**: Functional benefics/malefics by ascendant
4. **Hierarchical Logic**: Promise->Timing->Trigger workflow
5. **Lunar Considerations**: Moon's paksha, state, strength
6. **Karmic Axis**: Rahu/Ketu effects
7. **Strength Assessment**: Shadbala requirements, minimum thresholds
8. **Table-based Rules**: Rules extracted from tables (e.g., planetary dignity tables, house lordship tables)

For EACH rule found, extract:

```json
{{
  "rule_name": "Clear, descriptive name",
  "category": "planetary_state|divisional_confirmation|lagna_specific|hierarchical_logic|strength_assessment|lunar_consideration|karmic_axis|table_based_rules|general",
  "severity": "critical|high|medium|low",
  "check_order": 1,
  "applies_to_queries": ["marriage", "career", "all"],
  "prediction_stage": "promise|timing|trigger",
  "condition": "WHEN this check applies",
  "calculation": "HOW to calculate/check",
  "threshold": 8.0,
  "comparison": "<",
  "halt_on_failure": false,
  "impact_if_violated": "What goes wrong",
  "impact_percentage": 70,
  "cancellation_conditions": [
    {{
      "condition": "If planet is retrograde",
      "impact": "Combustion effect reduced",
      "percentage_reduction": 50
    }}
  ],
  "classical_reference": "BPHS 27.10-12",
  "chapter": "27",
  "verse_range": "10-12",
  "extraction_notes": "Any notes about extraction from table or complex structure"
}}
```

**For Tables**: If you see tabular data showing rules (e.g., "Exalted in Aries", "Debilitated in Libra"), extract each row as a separate rule component.

**CRITICAL REQUIREMENTS**:
1. Only extract VALIDATION RULES, not interpretations
2. Use EXACT category values: planetary_state, divisional_confirmation, lagna_specific, hierarchical_logic, strength_assessment, lunar_consideration, karmic_axis, table_based_rules, general
3. Use plural forms: "table_based_rules" NOT "table_based_rule"
4. Use EXACT query types: marriage, career, finance, health, education, children, spiritual, property, general, all, travel, happiness, lost things, etc.
5. **IMPORTANT**: "threshold" field must be a NUMBER or null. Do NOT put text descriptions in threshold field.
   - CORRECT: "threshold": 8.0 or "threshold": null
   - WRONG: "threshold": "Correct classification according to classical text"

Return as JSON array: {{"rules": [...]}}"""),
    
    ("human", """Text Source: {source_name}
Chapter/Section: {chapter}

Content Type: {content_type}

Text Content:
{text_content}

Tables (if any):
{tables}

Additional Metadata:
{metadata}

Extract ALL validation rules as JSON.""")
])


def setup_gemini(
    model: str = None,
    temperature: float = None,
    credentials_path: Optional[str] = None,
    project_id: Optional[str] = None
):
    """
    Initialize Google Gemini LLM
    
    Args:
        model: Gemini model name (defaults to .env LLM_MODEL or gemini-2.5-flash)
        temperature: Generation temperature (defaults to .env LLM_TEMPERATURE or 0.1)
        credentials_path: Path to service account JSON (defaults to .env GOOGLE_APPLICATION_CREDENTIALS)
        project_id: GCP project ID (defaults to .env GOOGLE_CLOUD_PROJECT)
    """
    
    # Get from .env if not provided
    if model is None:
        model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    
    if credentials_path is None:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if project_id is None:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    # Set credentials if provided
    if credentials_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    
    # Check if credentials are available
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        print("[WARN]  Warning: GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   Set in .env file or via: export GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json")
    
    # Initialize Gemini (NO deprecated parameter)
    try:
        llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature
        )
        
        print(f"[OK] Initialized Gemini: {model}")
        print(f"   Temperature: {temperature}")
        if project_id:
            print(f"   Project: {project_id}")
        return llm
        
    except Exception as e:
        print(f"[FAIL] Error initializing Gemini: {e}")
        print("\nTroubleshooting:")
        print("1. Check .env file has GOOGLE_APPLICATION_CREDENTIALS set")
        print("2. Verify service account has Vertex AI API access")
        print("3. Check GOOGLE_CLOUD_PROJECT is correct")
        print("4. Ensure Vertex AI API is enabled in Google Cloud Console")
        sys.exit(1)


def load_json_chunk_file(file_path: Path) -> Dict[str, Any]:
    """
    Load JSON file with chunk data
    
    Expected structure (user's format):
    {
      "chunks": [
        {
          "chunk_id": "...",
          "text_for_embedding": "...",
          "display_text": "...",
          "verse_sanskrit": "..." or null,
          "metadata": {
            "source_book": "...",
            "chapter": "...",
            "verse_number": "...",
            "entities": {
              "planets": [],
              "houses": [],
              "signs": [],
              "yogas": []
            }
          }
        }
      ]
    }
    
    OR array of chunks directly: [...]
    """
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Normalize structure
        if isinstance(data, list):
            # Direct array of chunks
            return {
                "source": file_path.stem,
                "chunks": data
            }
        elif isinstance(data, dict):
            if "chunks" in data:
                # Has chunks key
                return {
                    "source": data.get("source_file", file_path.stem),
                    "chunks": data["chunks"]
                }
            else:
                # Single chunk as dict
                return {
                    "source": file_path.stem,
                    "chunks": [data]
                }
        else:
            print(f"[WARN]  Unexpected structure in {file_path.name}")
            return {"source": file_path.stem, "chunks": []}
            
    except Exception as e:
        print(f"[FAIL] Error loading {file_path.name}: {e}")
        return {"source": file_path.stem, "chunks": []}


def format_tables_for_extraction(tables: List[Any]) -> str:
    """
    Format tables into readable text for LLM
    
    Args:
        tables: List of table structures (format depends on your extraction)
        
    Returns:
        Formatted table text
    """
    
    if not tables:
        return "No tables"
    
    formatted = []
    
    for i, table in enumerate(tables):
        formatted.append(f"\n--- Table {i+1} ---")
        
        # Handle different table formats
        if isinstance(table, dict):
            # Format 1: {"headers": [...], "rows": [[...]]}
            if "headers" in table and "rows" in table:
                formatted.append("Headers: " + " | ".join(table["headers"]))
                for row in table["rows"]:
                    formatted.append(" | ".join([str(cell) for cell in row]))
            
            # Format 2: {"data": [[...]]}
            elif "data" in table:
                for row in table["data"]:
                    formatted.append(" | ".join([str(cell) for cell in row]))
            
            # Format 3: Direct dict
            else:
                formatted.append(json.dumps(table, indent=2))
        
        elif isinstance(table, list):
            # List of rows
            for row in table:
                formatted.append(" | ".join([str(cell) for cell in row]))
        
        else:
            formatted.append(str(table))
    
    return "\n".join(formatted)


def extract_rules_from_chunk(
    chunk: Dict[str, Any],
    source_name: str,
    llm: ChatGoogleGenerativeAI,
    max_retries: int = 2
) -> List[Dict[str, Any]]:
    """
    Extract validation rules from a JSON chunk with retry logic
    
    Args:
        chunk: User's chunk format with:
            - "text_for_embedding": summary + content
            - "display_text": main content
            - "verse_sanskrit": Sanskrit text (or null)
            - "metadata": source, chapter, etc.
        source_name: Name of source file
        llm: Gemini LLM instance
        max_retries: Number of retries on failure (default: 2)
        
    Returns:
        List of raw rule dictionaries
    """
    
    # Extract text content
    text_content = chunk.get("display_text", "") or chunk.get("text_for_embedding", "")
    
    if not text_content or len(text_content.strip()) < 50:
        return []
    
    # Get metadata
    metadata = chunk.get("metadata", {})
    chapter = metadata.get("chapter", "Unknown")
    
    # Format any tables
    tables = []  # User's JSON chunks may not have tables explicitly
    tables_formatted = format_tables_for_extraction(tables)
    
    # Build extraction prompt
    prompt = RULE_EXTRACTION_PROMPT.format_messages(
        source_name=source_name,
        chapter=chapter,
        content_type="text" if not tables else "text with tables",
        text_content=text_content,
        tables=tables_formatted,
        metadata=json.dumps(metadata, indent=2)
    )
    
    # Retry loop
    for attempt in range(max_retries + 1):
        try:
            # Call LLM
            response = llm.invoke(prompt)
            
            # Parse JSON response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Handle empty responses
            if not response_text or len(response_text.strip()) == 0:
                if attempt < max_retries:
                    continue
                return []
            
            # Clean markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Strip whitespace
            response_text = response_text.strip()
            
            # Check if response is empty after cleaning
            if not response_text:
                if attempt < max_retries:
                    continue
                return []
            
            # Parse JSON
            result = json.loads(response_text)
            rules = result.get("rules", [])
            
            return rules
            
        except json.JSONDecodeError as e:
            # Retry on JSON errors
            if attempt < max_retries:
                continue
            else:
                # Last attempt failed - return empty
                return []
        
        except Exception as e:
            # Other errors - retry or skip
            if attempt < max_retries:
                continue
            else:
                return []
    
    return []


def extract_rules_from_chunks_parallel(
    chunks: List[Dict[str, Any]],
    source_name: str,
    llm: ChatGoogleGenerativeAI,
    max_workers: int = 10
) -> List[Dict[str, Any]]:
    """
    Extract rules from chunks in parallel using ThreadPoolExecutor
    
    Args:
        chunks: List of chunk dictionaries
        source_name: Source file name
        llm: Gemini LLM instance
        max_workers: Number of concurrent workers (default 10 for Gemini rate limits)
        
    Returns:
        List of all extracted rules
    """
    all_raw_rules = []
    lock = threading.Lock()
    error_count = {"json_errors": 0, "empty_responses": 0, "other_errors": 0}
    
    def process_chunk(chunk_idx_tuple):
        idx, chunk = chunk_idx_tuple
        try:
            rules = extract_rules_from_chunk(chunk, source_name, llm)
            if rules:
                with lock:
                    print(f"    Chunk {idx+1}: Found {len(rules)} rules")
                return rules
            return []
        except Exception as e:
            with lock:
                error_type = str(e)[:50]
                if "Expecting value" in error_type or "JSON" in error_type:
                    error_count["json_errors"] += 1
                elif "empty" in error_type.lower():
                    error_count["empty_responses"] += 1
                else:
                    error_count["other_errors"] += 1
            return []
    
    # Process chunks in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks
        futures = {executor.submit(process_chunk, (i, chunk)): i for i, chunk in enumerate(chunks)}
        
        # Use tqdm for progress
        for future in tqdm(as_completed(futures), total=len(chunks), desc="  Extracting", leave=False):
            try:
                rules = future.result()
                all_raw_rules.extend(rules)
            except Exception as e:
                with lock:
                    error_count["other_errors"] += 1
    
    # Print error summary
    total_errors = sum(error_count.values())
    if total_errors > 0:
        print(f"  [WARN]  Errors encountered: {total_errors} chunks")
        if error_count["json_errors"] > 0:
            print(f"     - JSON parsing errors: {error_count['json_errors']} (LLM returned invalid JSON)")
        if error_count["empty_responses"] > 0:
            print(f"     - Empty responses: {error_count['empty_responses']} (LLM returned nothing)")
        if error_count["other_errors"] > 0:
            print(f"     - Other errors: {error_count['other_errors']}")
    
    return all_raw_rules


def extract_rules_from_chunk_old(
    chunk: Dict[str, Any],
    source_name: str,
    llm: ChatGoogleGenerativeAI
) -> List[Dict[str, Any]]:
    """
    Extract validation rules from a JSON chunk
    
    Args:
        chunk: User's chunk format with:
            - "text_for_embedding": summary + content
            - "display_text": main content
            - "verse_sanskrit": Sanskrit text (or null)
            - "metadata": dict with source_book, entities, etc.
        source_name: Book name
        llm: Gemini model
        
    Returns:
        List of extracted rules
    """
    
    # Extract fields from user's format
    content = chunk.get("display_text", chunk.get("text_for_embedding", ""))
    sanskrit = chunk.get("verse_sanskrit") or ""
    metadata = chunk.get("metadata", {})
    
    # Get metadata fields
    source_book = metadata.get("source_book", source_name)
    chapter = metadata.get("chapter") or metadata.get("section", "Unknown")
    verse_number = metadata.get("verse_number", "")
    entities = metadata.get("entities", {})
    
    # Determine content type
    content_type = "text"
    if sanskrit:
        content_type = "text_with_sanskrit"
    
    # Build prompt
    parser = JsonOutputParser()
    chain = RULE_EXTRACTION_PROMPT | llm | parser
    
    try:
        result = chain.invoke({
            "text_content": content[:6000],  # Limit for tokens
            "source_name": source_book,
            "chapter": f"{chapter} (Verse {verse_number})" if verse_number else chapter,
            "content_type": content_type,
            "tables": "",  # Your format doesn't have separate tables field
            "metadata": json.dumps({
                "verse": verse_number,
                "entities": entities
            }, indent=2)[:500]
        })
        
        # Handle response format
        if isinstance(result, dict):
            if "rules" in result:
                return result["rules"]
            else:
                return [result] if result else []
        elif isinstance(result, list):
            return result
        else:
            return []
            
    except Exception as e:
        # Silently skip errors for cleaner output
        return []


def process_json_file(
    file_path: Path,
    llm: ChatGoogleGenerativeAI,
    starting_rule_id: int,
    max_workers: int = 10
) -> List[VedicValidationRule]:
    """
    Process a single JSON file and extract rules from all chunks IN PARALLEL
    
    Args:
        file_path: Path to JSON file
        llm: Gemini model
        starting_rule_id: Starting ID for rules
        max_workers: Number of concurrent workers (default 10 for Gemini)
        
    Returns:
        List of VedicValidationRule objects
    """
    
    print(f"\n📖 Processing: {file_path.name}")
    
    # Load JSON
    data = load_json_chunk_file(file_path)
    source_name = data.get("source", file_path.stem)
    chunks = data.get("chunks", [])
    
    print(f"  📄 Found {len(chunks)} chunks")
    print(f"  ⚡ Using {max_workers} parallel workers for speed")
    
    all_rules = []
    rule_counter = starting_rule_id
    conversion_stats = {"attempted": 0, "successful": 0, "failed": 0}
    
    # INCREMENTAL SAVE: Create output file path from input file
    output_partial = file_path.parent / f"{file_path.stem}_rules_partial.json"
    
    # === PARALLEL EXTRACTION ===
    print(f"  [LAUNCH] Extracting rules in parallel...")
    raw_rules_all = extract_rules_from_chunks_parallel(chunks, source_name, llm, max_workers)
    
    print(f"  [OK] Extraction complete: Found {len(raw_rules_all)} raw rules")
    
    # === SEQUENTIAL CONVERSION (must be sequential for rule_counter) ===
    print(f"  🔄 Converting to schema...")
    for raw_rule in tqdm(raw_rules_all, desc="  Converting", leave=False):
        conversion_stats["attempted"] += 1
        rule_id = f"VR{rule_counter:03d}"
        rule = convert_to_rule_schema(raw_rule, rule_id)
        
        if rule:
            all_rules.append(rule)
            rule_counter += 1
            conversion_stats["successful"] += 1
        else:
            conversion_stats["failed"] += 1
    
    # Final save for this file
    if len(all_rules) > 0:
        try:
            with open(output_partial, "w", encoding='utf-8') as f:
                json.dump({
                    "file": str(file_path.name),
                    "chunks_processed": len(chunks),
                    "total_chunks": len(chunks),
                    "rules_count": len(all_rules),
                    "conversion_stats": conversion_stats,
                    "rules": [r.model_dump() if hasattr(r, 'model_dump') else (r.dict() if hasattr(r, 'dict') else r) for r in all_rules]
                }, f, indent=2, ensure_ascii=False)
            print(f"  [SAVE] Saved: {len(all_rules)} rules -> {output_partial.name}")
        except Exception as e:
            print(f"  [WARN]  Could not save: {e}")
    
    print(f"  [OK] Extracted {len(all_rules)} rules from {file_path.name}")
    print(f"     (Attempted: {conversion_stats['attempted']}, Successful: {conversion_stats['successful']}, Failed: {conversion_stats['failed']})")
    
    return all_rules


def convert_to_rule_schema(raw_rule: Dict[str, Any], rule_id: str) -> Optional[VedicValidationRule]:
    """Convert raw extracted rule to Pydantic schema with robust error handling"""
    
    try:
        # === STEP 1: Handle CheckLogic fields ===
        threshold = raw_rule.get("threshold")
        # Convert string numbers to float
        if isinstance(threshold, str):
            try:
                threshold = float(threshold)
            except (ValueError, TypeError):
                threshold = None
        
        comparison = raw_rule.get("comparison")
        # Normalize comparison operators to accepted values
        if comparison:
            comparison_map = {
                # Equality variations
                "equals": "==",
                "equal": "==",
                "is": "==",
                "=": "==",
                "is_equal_to": "==",
                "equal_to": "==",
                "exact_match": "==",
                # Range/containment checks
                "range_extent": "==",
                "is_in": "==",
                "is_in_list": "==",
                "in": "==",
                "contains": "==",
                # Invalid/text operators - default to ==
                "*": "==",
                "reduction": "==",
                "greatest": ">",
                "strongest": ">",
                "is devoid of strength": "<",
            }
            comparison = comparison_map.get(comparison, comparison)
            
            # If still not a valid operator, default to ==
            valid_ops = ["<", ">", "<=", ">=", "==", "!=", "=", "equals"]
            if comparison not in valid_ops:
                # Check if it's a long text description or contains underscore/space
                if len(str(comparison)) > 10 or " " in str(comparison) or "_" in str(comparison):
                    comparison = "=="  # Default for text descriptions
        
        check_logic = CheckLogic(
            condition=raw_rule.get("condition", ""),
            calculation=raw_rule.get("calculation", ""),
            threshold=threshold,
            comparison=comparison
        )
        
        # === STEP 2: Handle cancellation_conditions (might be None or not a list) ===
        cancellations = []
        cancel_list = raw_rule.get("cancellation_conditions")
        
        # Handle None, empty, or non-list values
        if cancel_list is None:
            cancel_list = []
        elif not isinstance(cancel_list, list):
            cancel_list = []
        
        for cancel in cancel_list:
            if isinstance(cancel, dict):
                # Convert percentage_reduction to int if it's float
                perc_red = cancel.get("percentage_reduction")
                if isinstance(perc_red, float):
                    perc_red = int(perc_red)
                
                cancellations.append(RuleCancellation(
                    condition=cancel.get("condition", ""),
                    impact=cancel.get("impact", ""),
                    percentage_reduction=perc_red
                ))
        
        # === STEP 3: Handle lagna_specific_rules (might be None or not a list) ===
        lagna_rules = None
        lagna_raw = raw_rule.get("lagna_specific_rules")
        
        if lagna_raw and isinstance(lagna_raw, list):
            try:
                lagna_rules = []
                for lr in lagna_raw:
                    if isinstance(lr, dict):
                        # Ensure list fields are actually lists
                        lr_clean = {
                            "lagna": lr.get("lagna", ""),
                            "yogakarakas": lr.get("yogakarakas") if isinstance(lr.get("yogakarakas"), list) else [],
                            "functional_malefics": lr.get("functional_malefics") if isinstance(lr.get("functional_malefics"), list) else [],
                            "neutral": lr.get("neutral") if isinstance(lr.get("neutral"), list) else []
                        }
                        lagna_rules.append(LagnaSpecificRule(**lr_clean))
            except Exception as e:
                print(f"      Warning: Could not parse lagna_specific_rules: {e}")
                lagna_rules = None
        
        # === STEP 4: Handle applies_to_queries (might be None, empty, or not a list) ===
        applies_to = raw_rule.get("applies_to_queries", ["all"])
        
        if applies_to is None or not applies_to:
            applies_to = ["all"]
        elif not isinstance(applies_to, list):
            applies_to = ["all"]
        elif len(applies_to) == 0:
            applies_to = ["all"]
        
        # === STEP 5: Handle check_order (convert float to int, handle strings) ===
        check_order = raw_rule.get("check_order", 99)
        
        if isinstance(check_order, str):
            try:
                check_order = int(float(check_order))  # Handle "1.5" strings
            except (ValueError, TypeError):
                check_order = 99
        elif isinstance(check_order, float):
            check_order = int(check_order)
        elif not isinstance(check_order, int):
            check_order = 99
        
        # === STEP 6: Handle impact_percentage (convert float to int, handle strings) ===
        impact_pct = raw_rule.get("impact_percentage")
        
        if isinstance(impact_pct, str):
            try:
                impact_pct = int(float(impact_pct))
            except (ValueError, TypeError):
                impact_pct = None
        elif isinstance(impact_pct, float):
            impact_pct = int(impact_pct)
        
        # === STEP 7: Handle extraction_confidence (must be float 0.0-1.0) ===
        extraction_conf = raw_rule.get("extraction_confidence", 0.8)
        
        if isinstance(extraction_conf, str):
            try:
                extraction_conf = float(extraction_conf)
            except (ValueError, TypeError):
                extraction_conf = 0.8
        
        # Clamp to 0.0-1.0 range
        if extraction_conf < 0.0:
            extraction_conf = 0.0
        elif extraction_conf > 1.0:
            extraction_conf = 1.0
        
        # === STEP 8: Handle depends_on_rules and conflicts_with_rules (must be lists) ===
        depends_on = raw_rule.get("depends_on_rules", [])
        if not isinstance(depends_on, list):
            depends_on = []
        
        conflicts_with = raw_rule.get("conflicts_with_rules", [])
        if not isinstance(conflicts_with, list):
            conflicts_with = []
        
        # === STEP 9: Handle halt_on_failure (must be boolean) ===
        halt_on_failure = raw_rule.get("halt_on_failure", False)
        if isinstance(halt_on_failure, str):
            halt_on_failure = halt_on_failure.lower() in ['true', 'yes', '1']
        elif not isinstance(halt_on_failure, bool):
            halt_on_failure = False
        
        # === STEP 10: Handle impact_if_violated (must be string) ===
        impact_violated = raw_rule.get("impact_if_violated")
        if impact_violated is None or (isinstance(impact_violated, str) and not impact_violated.strip()):
            impact_violated = "Impact not specified"
        
        # === STEP 11: Handle classical_reference (must be string) ===
        classical_ref = raw_rule.get("classical_reference")
        if classical_ref is None or (isinstance(classical_ref, str) and not classical_ref.strip()):
            classical_ref = "Reference not specified"
        
        # === STEP 12: Handle category (must be string, not list) ===
        category = raw_rule.get("category", "general")
        if isinstance(category, list):
            # If list, join with | or take first element
            category = "|".join(category) if len(category) > 1 else (category[0] if category else "general")
        
        # === STEP 13: Handle prediction_stage (must be string, not list) ===
        pred_stage = raw_rule.get("prediction_stage", "promise")
        if isinstance(pred_stage, list):
            # If list, join with | or take first element
            pred_stage = "|".join(pred_stage) if len(pred_stage) > 1 else (pred_stage[0] if pred_stage else "promise")
        
        # === STEP 14: Create rule with all validated fields ===
        rule = VedicValidationRule(
            rule_id=rule_id,
            rule_name=raw_rule.get("rule_name", "Unknown Rule"),
            category=ValidationCategory(category),
            severity=ValidationSeverity(raw_rule.get("severity", "medium")),
            check_order=check_order,
            applies_to_queries=[QueryType(q) for q in applies_to],
            prediction_stage=PredictionStage(pred_stage),
            check_logic=check_logic,
            halt_on_failure=halt_on_failure,
            impact_if_violated=impact_violated,
            impact_percentage=impact_pct,
            cancellation_conditions=cancellations,
            lagna_specific_rules=lagna_rules,
            classical_reference=classical_ref,
            chapter=raw_rule.get("chapter"),
            verse_range=raw_rule.get("verse_range"),
            extraction_confidence=extraction_conf,
            expert_verified=False,
            extraction_notes=raw_rule.get("extraction_notes"),
            depends_on_rules=depends_on,
            conflicts_with_rules=conflicts_with
        )
        
        return rule
        
    except Exception as e:
        error_details = str(e)
        rule_name = raw_rule.get('rule_name', 'Unknown')
        
        # Print detailed error message
        print(f"  [WARN]  Error converting rule '{rule_name}': {error_details}")
        
        # Debug output for common issues
        if "NoneType" in error_details:
            print(f"      Debug: applies_to_queries = {raw_rule.get('applies_to_queries')} (type: {type(raw_rule.get('applies_to_queries'))})")
            print(f"      Debug: cancellation_conditions = {raw_rule.get('cancellation_conditions')} (type: {type(raw_rule.get('cancellation_conditions'))})")
        
        if "validation error" in error_details.lower():
            print(f"      Debug: Full raw_rule keys: {list(raw_rule.keys())}")
        
        return None


def deduplicate_rules(rules: List[VedicValidationRule]) -> List[VedicValidationRule]:
    """Remove duplicate rules"""
    
    seen = set()
    unique_rules = []
    
    for rule in rules:
        sig = f"{rule.rule_name}_{rule.category}_{rule.classical_reference}"
        
        if sig not in seen:
            seen.add(sig)
            unique_rules.append(rule)
    
    print(f"\n[SEARCH] Deduplication: {len(rules)} -> {len(unique_rules)} rules")
    return unique_rules


def generate_statistics(rules: List[VedicValidationRule]) -> Dict[str, Dict[str, int]]:
    """Generate statistics"""
    
    stats = {
        "by_category": {},
        "by_severity": {},
        "by_stage": {},
        "by_query_type": {}
    }
    
    for rule in rules:
        # Handle both enum and string values
        cat = rule.category.value if hasattr(rule.category, 'value') else str(rule.category)
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        
        sev = rule.severity.value if hasattr(rule.severity, 'value') else str(rule.severity)
        stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
        
        stage = rule.prediction_stage.value if hasattr(rule.prediction_stage, 'value') else str(rule.prediction_stage)
        stats["by_stage"][stage] = stats["by_stage"].get(stage, 0) + 1
        
        for qt in rule.applies_to_queries:
            qt_val = qt.value if hasattr(qt, 'value') else str(qt)
            stats["by_query_type"][qt_val] = stats["by_query_type"].get(qt_val, 0) + 1
    
    return stats


def load_checkpoint_if_exists(checkpoint_file: Path) -> List[Dict]:
    """Load checkpoint if it exists"""
    if checkpoint_file.exists():
        try:
            print(f"\n📂 Found checkpoint file: {checkpoint_file}")
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            rules = data.get("rules", [])
            files_done = data.get("files_processed", 0)
            
            print(f"[OK] Checkpoint contains:")
            print(f"   - {len(rules)} rules")
            print(f"   - {files_done} files processed")
            
            response = input("\n❓ Load checkpoint? (y/n): ").strip().lower()
            if response == 'y':
                print("[OK] Loading checkpoint data...")
                return rules, files_done
            else:
                print("⏭️  Skipping checkpoint, starting fresh...")
                return [], 0
        except Exception as e:
            print(f"[WARN]  Could not load checkpoint: {e}")
            return [], 0
    return [], 0


def main():
    parser = argparse.ArgumentParser(description="Extract Vedic validation rules from JSON with Gemini")
    parser.add_argument("--input-dir", type=str, required=True, help="Directory with JSON files")
    parser.add_argument("--output", type=str, default="vedic_validation_rules.json", help="Output JSON")
    parser.add_argument("--model", type=str, help="Gemini model (default: from .env or gemini-3.0-flash)")
    parser.add_argument("--temperature", type=float, help="Temperature (default: from .env or 0.1)")
    parser.add_argument("--credentials", type=str, help="Path to Google service account JSON (default: from .env)")
    parser.add_argument("--project-id", type=str, help="GCP project ID (default: from .env)")
    parser.add_argument("--limit", type=int, help="Limit files (for testing)")
    parser.add_argument("--max-workers", type=int, default=10, help="Parallel workers for extraction (default: 10, max rate limit)")
    
    args = parser.parse_args()
    
    # Setup
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"[FAIL] Input directory not found: {input_dir}")
        return
    
    print("[LAUNCH] Vedic Validation Rule Extraction (JSON + Gemini) - PARALLEL MODE")
    print(f"📁 Input: {input_dir}")
    print(f"[SAVE] Output: {args.output}")
    print(f"⚡ Workers: {args.max_workers} concurrent")
    print("=" * 60)
    
    # Initialize Gemini (will use .env defaults if args not provided)
    llm = setup_gemini(
        model=args.model,
        temperature=args.temperature,
        credentials_path=args.credentials,
        project_id=args.project_id
    )
    
    # Check for checkpoint
    checkpoint_file = Path("checkpoint_rules.json")
    loaded_rules, files_processed = load_checkpoint_if_exists(checkpoint_file)
    
    # Find JSON files
    json_files = sorted(input_dir.glob("*.json"))
    
    # Skip already processed files if loading checkpoint
    if files_processed > 0:
        print(f"⏭️  Skipping first {files_processed} files (already processed)")
        json_files = json_files[files_processed:]
    
    if args.limit:
        json_files = json_files[:args.limit]
    
    print(f"\n📚 Found {len(json_files)} JSON files\n")
    
    # Process all files with checkpointing
    all_rules = loaded_rules  # Start with loaded rules if any
    rule_counter = len(loaded_rules) + 1  # Continue numbering
    checkpoint_file = Path("checkpoint_rules.json")
    
    for idx, file_path in enumerate(json_files, 1):
        print(f"📖 [{idx}/{len(json_files)}] Processing: {file_path.name}")
        
        try:
            rules = process_json_file(file_path, llm, rule_counter, max_workers=args.max_workers)
            all_rules.extend(rules)
            rule_counter += len(rules)
            
            # CHECKPOINT: Save after EVERY file (not every 5!)
            if len(all_rules) > 0:
                print(f"[SAVE] Checkpoint: Saving {len(all_rules)} rules...")
                try:
                    with open(checkpoint_file, "w", encoding='utf-8') as f:
                        json.dump({
                            "saved_at": str(Path().absolute()),
                            "files_processed": idx,
                            "total_files": len(json_files),
                            "rules_count": len(all_rules),
                            "rules": [r if isinstance(r, dict) else (r.model_dump() if hasattr(r, 'model_dump') else r.dict()) for r in all_rules]
                        }, f, indent=2, ensure_ascii=False)
                    print(f"[OK] Checkpoint saved: {idx}/{len(json_files)} files, {len(all_rules)} rules")
                except Exception as e:
                    print(f"[WARN]  Checkpoint failed: {e}")
        
        except KeyboardInterrupt:
            print(f"\n\n[WARN]  Interrupted by user at file {idx}/{len(json_files)}")
            print(f"[SAVE] Saving emergency checkpoint with {len(all_rules)} rules...")
            try:
                with open(checkpoint_file, "w", encoding='utf-8') as f:
                    json.dump({
                        "emergency_save": True,
                        "files_processed": idx,
                        "total_files": len(json_files),
                        "rules_count": len(all_rules),
                        "rules": [r if isinstance(r, dict) else (r.model_dump() if hasattr(r, 'model_dump') else r.dict()) for r in all_rules]
                    }, f, indent=2, ensure_ascii=False)
                print(f"[OK] Emergency checkpoint saved to: {checkpoint_file}")
                print(f"   Files processed: {idx}/{len(json_files)}")
                print(f"   Rules extracted: {len(all_rules)}")
                print(f"\n[IDEA] To continue later, load this file and process remaining files.")
            except Exception as e:
                print(f"[FAIL] Could not save emergency checkpoint: {e}")
            return
        
        except Exception as e:
            print(f"[FAIL] Error processing {file_path.name}: {e}")
            print("   Continuing with next file...")
            continue
    
    # Final checkpoint after all files
    print(f"\n[SAVE] Final checkpoint: Saving {len(all_rules)} rules...")
    try:
        with open(checkpoint_file, "w", encoding='utf-8') as f:
            json.dump({
                "final_save": True,
                "files_processed": len(json_files),
                "rules_count": len(all_rules),
                "rules": [r if isinstance(r, dict) else (r.model_dump() if hasattr(r, 'model_dump') else r.dict()) for r in all_rules]
            }, f, indent=2, ensure_ascii=False)
        print(f"[OK] All rules checkpointed")
    except Exception as e:
        print(f"[WARN]  Final checkpoint failed: {e}")
    
    # Deduplicate
    print(f"\n[SEARCH] Deduplication: {len(all_rules)} -> ", end="")
    unique_rules = deduplicate_rules(all_rules)
    print(f"{len(unique_rules)} rules")
    
    # SAVE RULES IMMEDIATELY (before statistics to prevent data loss)
    from datetime import datetime
    
    output_path = Path(args.output)
    
    # Create ruleset dict with basic info
    ruleset_dict = {
        "version": "1.0.0",
        "last_updated": datetime.now().isoformat(),
        "total_rules": len(unique_rules),
        "rules": [r if isinstance(r, dict) else (r.model_dump() if hasattr(r, 'model_dump') else r.dict()) for r in unique_rules],
        "by_category": {},
        "by_severity": {},
        "by_stage": {}
    }
    
    # SAVE IMMEDIATELY
    print(f"\n[SAVE] Saving {len(unique_rules)} rules...")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(ruleset_dict, f, indent=2, ensure_ascii=False)
        print(f"[OK] Rules saved to: {output_path}")
    except Exception as e:
        print(f"[FAIL] Error saving rules: {e}")
        return
    
    # NOW try to generate statistics (optional, won't lose data if it fails)
    print("\n[STATS] Generating statistics...")
    try:
        stats = generate_statistics(unique_rules)
        
        # Update ruleset with stats
        ruleset_dict["by_category"] = stats["by_category"]
        ruleset_dict["by_severity"] = stats["by_severity"]
        ruleset_dict["by_stage"] = stats["by_stage"]
        
        # Re-save with stats
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(ruleset_dict, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print("\n" + "=" * 60)
        print("[OK] EXTRACTION COMPLETE")
        print(f"[STATS] Total Rules Extracted: {len(unique_rules)}")
        print(f"\n📈 Statistics:")
        print(f"  By Category:")
        for cat, count in sorted(stats["by_category"].items()):
            print(f"    - {cat}: {count}")
        print(f"  By Severity:")
        for sev, count in sorted(stats["by_severity"].items()):
            print(f"    - {sev}: {count}")
        print(f"  By Stage:")
        for stage, count in sorted(stats["by_stage"].items()):
            print(f"    - {stage}: {count}")
        print(f"\n[SAVE] Saved to: {output_path}")
        print(f"🗑️  Clean up checkpoints:")
        print(f"    rm checkpoint_rules.json")
        print(f"    rm *_rules_partial.json  # Per-file checkpoints")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[WARN]  Warning: Statistics generation failed: {e}")
        print("   But all rules are saved successfully!")
        print("\n" + "=" * 60)
        print("[OK] EXTRACTION COMPLETE")
        print(f"[STATS] Total Rules Extracted: {len(unique_rules)}")
        print(f"[SAVE] Saved to: {output_path}")
        print(f"🗑️  Clean up checkpoint: rm checkpoint_rules.json")
        print("=" * 60)


if __name__ == "__main__":
    main()