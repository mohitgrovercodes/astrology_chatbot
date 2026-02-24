# enrich_metadata_json_gemini.py
"""
Enhanced Metadata Enrichment for JSON Chunks (Gemini)

Works with your specific JSON chunk structure.
Uses Google Gemini for extraction.

Usage:
    python enrich_metadata_json_gemini.py \
        --input-dir ./data/json_chunks \
        --output ./data/enriched_chunks \
        --credentials /path/to/google-credentials.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent))

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    print("ERROR: Install langchain-google-genai")
    sys.exit(1)


METADATA_ENRICHMENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are enriching metadata for Vedic astrology text chunks.

Extract/enhance the following metadata:

1. **Content Type**:
   - validation_rule: Rules that MUST be checked
   - interpretation: What placement means
   - combination_rule: Multi-factor synthesis
   - timing_technique: Dasha/transit methods
   - general_principle: Foundational concepts
   - remedial_measure: Upayas

2. **If validation_rule**:
   - validation_category: planetary_state|divisional_confirmation|lagna_specific|hierarchical_logic|strength_assessment|lunar_consideration|karmic_axis
   - severity: critical|high|medium|low
   - check_order: Integer
   - halt_on_failure: true/false

3. **Prediction Stage**: promise|timing|trigger|synthesis

4. **Applies To**: marriage, career, finance, health, education, children, spiritual, property, general, all

5. **Additional**: divisional_charts, yogas_mentioned

6. **Classification**: is_beneficial, is_malefic

7. **Tier**: tier1_classical|tier2_specialized|tier3_modern

Return JSON:
```json
{
  "content_type": "interpretation",
  "is_validation_rule": false,
  "validation_category": null,
  "severity": null,
  "check_order": null,
  "halt_on_failure": false,
  "prediction_stage": "promise",
  "applies_to_queries": ["all"],
  "tier": "tier1_classical",
  "divisional_charts": [],
  "yogas_mentioned": [],
  "is_beneficial": null,
  "is_malefic": null
}
```"""),
    
    ("human", """Source: {source}
Verse: {verse}

Entities (already extracted):
- Planets: {planets}
- Houses: {houses}
- Signs: {signs}
- Yogas: {yogas}

Text:
{content}

Sanskrit:
{sanskrit}

Extract enhanced metadata as JSON.""")
])


def setup_gemini(
    model: str = None,
    temperature: float = None,
    credentials_path: str = None
):
    """Initialize Gemini (reads from .env if not provided)"""
    
    # Get from .env if not provided
    if model is None:
        model = os.getenv("LLM_MODEL", "gemini-3.0-flash")
    
    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    
    if credentials_path is None:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if credentials_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   Set in .env file or export GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json")
    
    try:
        llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
        )
        print(f"✅ Initialized Gemini: {model}")
        print(f"   Temperature: {temperature}")
        return llm
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nCheck:")
        print("1. .env has GOOGLE_APPLICATION_CREDENTIALS")
        print("2. Service account has Vertex AI access")
        print("3. Vertex AI API is enabled")
        sys.exit(1)


def enrich_chunk(chunk: Dict[str, Any], llm: ChatGoogleGenerativeAI) -> Dict[str, Any]:
    """
    Enrich a single chunk with enhanced metadata
    
    Input chunk structure (your format):
    {
        "chunk_id": "...",
        "text_for_embedding": "...",
        "display_text": "...",
        "verse_sanskrit": "..." or null,
        "metadata": {
            "source_book": "...",
            "chapter": "...",
            "verse_number": "...",
            "tradition": "vedic",
            "entities": {
                "planets": [],
                "houses": [],
                "signs": [],
                "yogas": [],
                "concepts": []
            }
        },
        "summary": "..."
    }
    """
    
    parser = JsonOutputParser()
    chain = METADATA_ENRICHMENT_PROMPT | llm | parser
    
    # Extract existing data
    metadata = chunk.get("metadata", {})
    entities = metadata.get("entities", {})
    
    try:
        # Call LLM
        enhanced = chain.invoke({
            "source": metadata.get("source_book", "Unknown"),
            "verse": metadata.get("verse_number", ""),
            "planets": entities.get("planets", []),
            "houses": entities.get("houses", []),
            "signs": entities.get("signs", []),
            "yogas": entities.get("yogas", []),
            "content": chunk.get("display_text", "")[:2000],
            "sanskrit": chunk.get("verse_sanskrit", "") or ""
        })
        
        # Merge enhanced metadata
        if "enhanced_metadata" not in metadata:
            metadata["enhanced_metadata"] = {}
        
        metadata["enhanced_metadata"].update(enhanced)
        chunk["metadata"] = metadata
        
        return chunk
        
    except Exception as e:
        # print(f"  ⚠️  Error: {str(e)[:50]}")
        return chunk


def process_json_file(
    file_path: Path,
    llm: ChatGoogleGenerativeAI,
    output_dir: Path
) -> int:
    """Process one JSON file"""
    
    print(f"📄 {file_path.name}")
    
    # Load
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle structure: {"chunks": [...]} or [...]
        if isinstance(data, dict) and "chunks" in data:
            chunks = data["chunks"]
        elif isinstance(data, list):
            chunks = data
        else:
            chunks = [data]
    
    except Exception as e:
        print(f"  ❌ Error loading: {e}")
        return 0
    
    # Enrich
    enriched = []
    for chunk in tqdm(chunks, desc="  Enriching", leave=False):
        enriched_chunk = enrich_chunk(chunk, llm)
        enriched.append(enriched_chunk)
    
    # Save
    output_file = output_dir / file_path.name
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "source_file": file_path.name,
            "total_chunks": len(enriched),
            "chunks": enriched
        }, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ {len(enriched)} chunks → {output_file.name}")
    return len(enriched)


def generate_report(output_dir: Path):
    """Generate enrichment report"""
    
    stats = {
        "total": 0,
        "by_content_type": {},
        "by_validation_category": {},
        "by_severity": {},
        "validation_rules": 0
    }
    
    for file_path in output_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            chunks = data.get("chunks", [])
            stats["total"] += len(chunks)
            
            for chunk in chunks:
                enhanced = chunk.get("metadata", {}).get("enhanced_metadata", {})
                
                ct = enhanced.get("content_type", "unknown")
                stats["by_content_type"][ct] = stats["by_content_type"].get(ct, 0) + 1
                
                if enhanced.get("is_validation_rule"):
                    stats["validation_rules"] += 1
                    
                    vc = enhanced.get("validation_category")
                    if vc:
                        stats["by_validation_category"][vc] = stats["by_validation_category"].get(vc, 0) + 1
                    
                    sev = enhanced.get("severity")
                    if sev:
                        stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
        
        except:
            pass
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Enrich JSON chunks with Gemini")
    parser.add_argument("--input-dir", required=True, help="Input directory with JSON files")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--model", help="Gemini model (default: from .env or gemini-3.0-flash)")
    parser.add_argument("--temperature", type=float, help="Temperature (default: from .env or 0.1)")
    parser.add_argument("--credentials", help="Google credentials JSON path (default: from .env)")
    parser.add_argument("--limit", type=int, help="Limit files (testing)")
    
    args = parser.parse_args()
    
    # Setup
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"❌ Not found: {input_dir}")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🚀 Metadata Enrichment (JSON + Gemini)")
    print(f"📁 Input: {input_dir}")
    print(f"💾 Output: {output_dir}")
    print("=" * 60)
    
    # Initialize Gemini (will use .env defaults)
    llm = setup_gemini(
        model=args.model,
        temperature=args.temperature,
        credentials_path=args.credentials
    )
    
    # Find files
    json_files = list(input_dir.glob("*.json"))
    if args.limit:
        json_files = json_files[:args.limit]
    
    print(f"\n📚 Found {len(json_files)} files\n")
    
    # Process
    total = 0
    for file_path in json_files:
        count = process_json_file(file_path, llm, output_dir)
        total += count
    
    # Report
    print("\n📊 Generating report...")
    stats = generate_report(output_dir)
    
    print("\n" + "=" * 60)
    print("✅ ENRICHMENT COMPLETE")
    print(f"📊 Total: {stats['total']}")
    print(f"\n  Content Types:")
    for ct, count in sorted(stats["by_content_type"].items()):
        print(f"    - {ct}: {count}")
    print(f"\n  Validation Rules: {stats['validation_rules']}")
    if stats["by_validation_category"]:
        print(f"  Categories:")
        for vc, count in stats["by_validation_category"].items():
            print(f"    - {vc}: {count}")
    print(f"\n💾 Saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
