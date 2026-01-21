"""
Specialized prompts for Vision LLM extraction of astrology texts.
These prompts are designed to handle:
- Sanskrit/Hindi verses (shlokas) with English translations
- Complex astrological tables
- Mixed content pages
- Multilingual text (English + Devanagari)
"""

# ============================================================================
# SYSTEM PROMPT - Sets the context for all extractions
# ============================================================================

SYSTEM_PROMPT = """You are an expert OCR and document extraction system specialized in Vedic and Western astrology texts. You have deep knowledge of:

1. **Sanskrit and Hindi**: You can accurately read and transcribe Devanagari script, including classical Sanskrit used in Jyotish texts.

2. **Astrological Terminology**: You understand terms like:
   - Grahas (planets): Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu
   - Rashis (signs): Aries/Mesha through Pisces/Meena
   - Bhavas (houses): 1st through 12th houses
   - Nakshatras (lunar mansions): Ashwini through Revati
   - Dashas: Vimshottari, Ashtottari, etc.
   - Yogas: Raja Yoga, Dhana Yoga, etc.
   - Karakas: Chara, Sthira, Naisargika

3. **Document Structure**: These texts typically have:
   - Sanskrit shlokas (verses) with verse numbers
   - English translations following each shloka
   - Notes/commentary sections
   - Tables showing planetary relationships, degrees, effects, etc.

4. **Common OCR Errors**: You can intelligently correct:
   - Garbled Devanagari characters
   - Misread numbers (especially verse numbers)
   - Table alignment issues
   - Mixed script recognition errors

Your goal is to extract content accurately while preserving the semantic structure."""


# ============================================================================
# PAGE CLASSIFICATION PROMPT
# ============================================================================

PAGE_CLASSIFICATION_PROMPT = """Analyze this page image and classify it into ONE of the following categories:

1. **text_heavy**: Primarily contains verses (shlokas) and prose text with translations
2. **table_heavy**: Primarily contains tabular data (planetary relationships, degrees, etc.)
3. **mixed**: Contains both substantial text AND tables
4. **chart**: Contains astrological charts or diagrams (birth charts, divisional charts)
5. **title**: Title page, chapter beginning, or section header
6. **index**: Table of contents, index, or reference list

Also identify:
- Book title if visible
- Chapter title/number if visible
- Whether Devanagari (Sanskrit/Hindi) script is present
- Whether tables are present
- Whether charts/diagrams are present

Respond in this exact JSON format:
{
    "page_type": "<one of: text_heavy, table_heavy, mixed, chart, title, index>",
    "book_title": "<title or null>",
    "chapter_title": "<chapter title or null>",
    "chapter_number": <number or null>,
    "has_sanskrit": <true/false>,
    "has_tables": <true/false>,
    "has_charts": <true/false>,
    "page_number": <number from page if visible, or null>,
    "confidence": <0.0-1.0>
}"""


# ============================================================================
# TEXT-HEAVY PAGE EXTRACTION PROMPT
# ============================================================================

TEXT_EXTRACTION_PROMPT = """Extract ALL text content from this astrology book page. This page is primarily TEXT (verses and prose).

**IMPORTANT RULES:**

1. **Sanskrit Shlokas**: 
   - Extract the COMPLETE Devanagari text exactly as shown
   - Include verse numbers (e.g., ॥९५॥ or ||95||)
   - Do NOT attempt to transliterate - preserve original Devanagari

2. **English Translations**:
   - Extract the complete translation following each shloka
   - Preserve verse number references (e.g., "13-14", "15-16")
   - Keep the paragraph structure intact

3. **Notes Sections**:
   - Extract content labeled "Notes:", "Note:", or similar
   - Preserve any examples or elaborations

4. **Headings**:
   - Capture chapter titles, section headings
   - Note page numbers if visible

**OUTPUT FORMAT** - Respond with JSON:
```json
{
    "page_number": <number or null>,
    "chapter_title": "<title or null>",
    "section_title": "<section or null>",
    "content_blocks": [
        {
            "type": "heading|shloka|translation|notes|prose",
            "verse_number": "<e.g., '13-14' or null>",
            "sanskrit_text": "<Devanagari text or null>",
            "english_text": "<English text>",
            "topic": "<brief topic description>"
        }
    ],
    "raw_text": "<complete raw text as fallback>",
    "extraction_quality": "<good|fair|poor>",
    "issues": ["<any issues encountered>"]
}
```

Extract the content now, preserving the original structure and language."""


# ============================================================================
# TABLE-HEAVY PAGE EXTRACTION PROMPT
# ============================================================================

TABLE_EXTRACTION_PROMPT = """Extract ALL tables from this astrology book page. This page contains primarily TABULAR data.

**IMPORTANT RULES:**

1. **Table Identification**:
   - Identify EACH distinct table on the page
   - Note table titles/captions if present
   - Identify what type of astrological data it contains

2. **Table Structure**:
   - Extract column headers accurately
   - Extract ALL rows, preserving alignment
   - Handle merged cells by repeating the value
   - Convert to clean markdown table format

3. **Table Types** (common in astrology texts):
   - Planetary relationships (friends/enemies/neutral)
   - Exaltation/Debilitation degrees
   - Nakshatra lords and characteristics
   - Dasha periods and effects
   - House significations
   - Seasonal correspondences (Ritu)
   - Trimshamsha/Divisional chart mappings

4. **Surrounding Text**:
   - Extract any text BEFORE or AFTER tables that provides context
   - Include verse references if tables illustrate a shloka

**OUTPUT FORMAT** - Respond with JSON:
```json
{
    "page_number": <number or null>,
    "tables": [
        {
            "table_number": 1,
            "title": "<table title or null>",
            "table_type": "<e.g., planetary_relationships, exaltation_degrees>",
            "context_before": "<text before table>",
            "context_after": "<text after table>",
            "headers": ["col1", "col2", ...],
            "rows": [
                ["cell1", "cell2", ...],
                ...
            ],
            "markdown": "| col1 | col2 |\\n|---|---|\\n| cell1 | cell2 |",
            "notes": "<any notes about the table>"
        }
    ],
    "other_text": "<any non-table text on page>",
    "extraction_quality": "<good|fair|poor>",
    "issues": ["<any issues encountered>"]
}
```

Extract all tables now, ensuring accurate structure."""


# ============================================================================
# MIXED PAGE EXTRACTION PROMPT
# ============================================================================

MIXED_EXTRACTION_PROMPT = """Extract ALL content from this astrology book page. This page contains BOTH text AND tables.

**IMPORTANT RULES:**

1. **Preserve Order**: Extract content in the order it appears on the page
2. **Identify Content Types**: Mark each block as verse, translation, table, notes, etc.
3. **Link Related Content**: Connect tables to the verses they illustrate

**For Sanskrit/Hindi Text**:
- Preserve exact Devanagari script
- Include verse numbers
- Keep translations paired with their shlokas

**For Tables**:
- Extract as structured data
- Include headers and all rows
- Note what the table represents

**OUTPUT FORMAT** - Respond with JSON:
```json
{
    "page_number": <number or null>,
    "chapter_title": "<title or null>",
    "content_blocks": [
        {
            "sequence": 1,
            "type": "heading|shloka|translation|notes|prose|table",
            "content": {
                // For text types:
                "verse_number": "<or null>",
                "sanskrit_text": "<or null>",
                "english_text": "<text content>",
                
                // For tables:
                "table_title": "<or null>",
                "table_type": "<e.g., planetary_friendships>",
                "headers": ["col1", "col2"],
                "rows": [["cell1", "cell2"]],
                "markdown": "<markdown table>"
            },
            "topic": "<brief topic>"
        }
    ],
    "raw_text": "<complete raw text fallback>",
    "extraction_quality": "<good|fair|poor>",
    "issues": ["<any issues>"]
}
```

Extract all content in sequence now."""


# ============================================================================
# COMPLEX TABLE PROMPT (for very difficult tables)
# ============================================================================

COMPLEX_TABLE_PROMPT = """This image contains a COMPLEX astrological table that needs careful extraction.

**TABLE CHARACTERISTICS to handle:**
- Multi-level headers (merged column headers)
- Borderless or partially bordered tables
- Mixed language content (English + Devanagari)
- Nested data or sub-tables
- Astronomical/astrological symbols

**EXTRACTION STRATEGY:**
1. First, identify the overall table structure
2. Count columns and rows
3. Identify header rows (may be multiple levels)
4. Extract data row by row, left to right
5. Handle merged cells by noting the span

**For Astrological Tables specifically:**
- Planet names: Sun/Surya, Moon/Chandra, Mars/Mangal, Mercury/Budha, Jupiter/Guru, Venus/Shukra, Saturn/Shani, Rahu, Ketu
- Sign names: Aries/Mesha, Taurus/Vrishabha, etc.
- Nakshatra names: Ashwini, Bharani, Krittika, etc.
- Relationships: Friend/Mitra, Enemy/Shatru, Neutral/Sama

**OUTPUT FORMAT** - Respond with JSON:
```json
{
    "table_title": "<title if identifiable>",
    "table_type": "<type of astrological data>",
    "structure": {
        "total_columns": <number>,
        "total_rows": <number>,
        "header_rows": <number of header rows>,
        "has_merged_cells": <true/false>
    },
    "headers": [
        {
            "level": 1,
            "cells": ["header1", "header2", ...]
        }
    ],
    "data_rows": [
        {
            "row_label": "<row header if any>",
            "cells": ["cell1", "cell2", ...]
        }
    ],
    "markdown": "<full markdown representation>",
    "extraction_notes": "<any difficulties or uncertainties>"
}
```

Extract this complex table carefully."""


# ============================================================================
# CHART/DIAGRAM PROMPT
# ============================================================================

CHART_EXTRACTION_PROMPT = """This page contains an astrological CHART or DIAGRAM.

**CHART TYPES in Vedic Astrology:**
1. **Birth Chart (Kundali)**: North Indian (diamond) or South Indian (square) format
2. **Divisional Charts**: D-9 (Navamsa), D-10, etc.
3. **Chakras**: Nakshatra chakras, Dasha chakras
4. **Diagrams**: Planetary motion, aspect diagrams

**EXTRACTION APPROACH:**
- For Birth Charts: Extract house positions and planetary placements
- For Other Diagrams: Describe the structure and key elements
- Extract any accompanying text or labels

**OUTPUT FORMAT** - Respond with JSON:
```json
{
    "chart_type": "<birth_chart|divisional|chakra|diagram|other>",
    "chart_format": "<north_indian|south_indian|other>",
    "description": "<description of what the chart shows>",
    "positions": {
        "house_1": ["planets/signs here"],
        "house_2": ["planets/signs here"],
        // ... etc
    },
    "labels": ["<any text labels on the chart>"],
    "accompanying_text": "<any explanatory text>",
    "extraction_quality": "<good|fair|poor>"
}
```

Extract the chart information now."""


# ============================================================================
# POST-PROCESSING / CLEANUP PROMPT
# ============================================================================

CLEANUP_PROMPT = """Review and clean up this extracted text from an astrology book.

**COMMON ISSUES TO FIX:**

1. **OCR Errors in Sanskrit**:
   - Fix broken/garbled Devanagari characters
   - Correct common misreadings
   - Ensure verse numbers are correct (॥१॥, ॥२॥, etc.)

2. **Number Corrections**:
   - Fix verse numbers that got mangled
   - Correct degree/minute/second values (e.g., 15°-30'-20")
   - Fix page numbers

3. **Terminology Standardization**:
   - Standardize planet names (Sun not 5un, Mars not Nars)
   - Standardize sign names
   - Fix common astrological term misspellings

4. **Structure Issues**:
   - Reconnect broken sentences
   - Fix paragraph breaks
   - Ensure tables are properly aligned

**INPUT**: {extracted_content}

**OUTPUT** - Return the cleaned version in the same JSON format, with a "corrections_made" field listing what was fixed."""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_prompt_for_page_type(page_type: str) -> str:
    """Get the appropriate extraction prompt based on page type."""
    prompts = {
        "text_heavy": TEXT_EXTRACTION_PROMPT,
        "table_heavy": TABLE_EXTRACTION_PROMPT,
        "mixed": MIXED_EXTRACTION_PROMPT,
        "chart": CHART_EXTRACTION_PROMPT,
        "title": TEXT_EXTRACTION_PROMPT,  # Treat titles as text
        "index": TEXT_EXTRACTION_PROMPT,   # Treat index as text
    }
    return prompts.get(page_type, MIXED_EXTRACTION_PROMPT)


def build_extraction_prompt(page_type: str, additional_context: str = None) -> str:
    """Build the complete extraction prompt with optional context."""
    base_prompt = get_prompt_for_page_type(page_type)
    
    if additional_context:
        return f"{base_prompt}\n\n**ADDITIONAL CONTEXT:**\n{additional_context}"
    
    return base_prompt


# ============================================================================
# METADATA ENRICHMENT PROMPTS
# ============================================================================

TOPIC_CLASSIFICATION_PROMPT = """Based on this extracted content, classify the main astrological topic(s).

**CONTENT:**
{content}

**TOPICS TO CHOOSE FROM:**
- zodiac_signs: Description of zodiac signs/rashis
- planets: Planetary characteristics and effects  
- planetary_relationships: Friendships, enmities between planets
- houses: House meanings and significations
- nakshatras: Lunar mansion descriptions
- dasha_systems: Dasha periods and their effects
- yogas: Planetary combinations (Raja Yoga, etc.)
- divisional_charts: Vargas like Navamsa, Dasamsa
- karakas: Significators (Chara, Sthira)
- muhurta: Auspicious timing
- calculations: Astronomical calculations
- predictions: Predictive techniques
- remedies: Astrological remedies
- general: General/introductory content

**OUTPUT** - Respond with JSON:
```json
{
    "primary_topic": "<main topic>",
    "secondary_topics": ["<other relevant topics>"],
    "entities_mentioned": {
        "planets": ["<planets mentioned>"],
        "signs": ["<signs mentioned>"],
        "houses": ["<house numbers>"],
        "nakshatras": ["<nakshatras>"]
    },
    "confidence": <0.0-1.0>
}
```"""
