#!/usr/bin/env python3
"""
Phase 4: Semantic Segmentation

Transform page-based structure into semantic units (verse + commentary pairs,
concept explanations, etc.) that form the natural "atoms" of knowledge.
"""

import re
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Handle both relative and direct imports
try:
    from .schemas import (
        LinkedPage,
        LinkedDocument,
        SemanticUnit,
        SemanticDocument,
        UnitType,
        VerseData,
    )
except ImportError:
    from schemas import (
        LinkedPage,
        LinkedDocument,
        SemanticUnit,
        SemanticDocument,
        UnitType,
        VerseData,
    )


class SemanticSegmenter:
    """
    Segment linked pages into semantic units.
    Extracts verse-commentary pairs and concept explanations.
    """
    
    # Maximum tokens per unit (leave room for query + response in RAG)
    MAX_TOKENS_PER_UNIT = 6000
    
    # Approximate chars per token for English + Sanskrit mix
    CHARS_PER_TOKEN = 4
    
    # Verse number patterns
    VERSE_PATTERN = r'॥\s*(\d+(?:\s*[-–]\s*\d+)?)\s*॥'
    
    # Section heading patterns (numbered sections like "1. Introduction")
    SECTION_PATTERN = r'^(\d+)\.\s+([A-Z][^\n]+)'
    
    def __init__(self, source_book: Optional[str] = None):
        """
        Initialize semantic segmenter.
        
        Args:
            source_book: Name of the source book
        """
        self.source_book = source_book or "Unknown Source"
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from character count."""
        return len(text) // self.CHARS_PER_TOKEN
    
    def generate_unit_id(self, chapter: Optional[str], verse_num: Optional[str], unit_type: UnitType) -> str:
        """Generate a unique ID for a semantic unit."""
        parts = []
        
        # Book abbreviation
        book_abbr = ''.join(word[0].lower() for word in self.source_book.split()[:3])
        parts.append(book_abbr)
        
        # Chapter if available
        if chapter:
            chapter_slug = re.sub(r'[^a-zA-Z0-9]+', '-', chapter.lower())[:20]
            parts.append(chapter_slug)
        
        # Verse number or unit type (sanitize to ASCII)
        if verse_num:
            # Remove non-ASCII characters and sanitize
            verse_clean = re.sub(r'[^0-9\-_]', '', verse_num.replace('-', '_'))
            if verse_clean:
                parts.append(f"v{verse_clean}")
            else:
                parts.append(f"v{hash(verse_num) % 10000}")
        else:
            parts.append(unit_type.value[:10])
        
        # Short unique suffix
        short_uuid = str(uuid.uuid4())[:8]
        parts.append(short_uuid)
        
        return '-'.join(parts)
    
    def merge_continuation_pages(self, pages: List[LinkedPage]) -> List[Dict]:
        """
        Merge pages that are continuations into single text blocks.
        
        Args:
            pages: List of linked pages
            
        Returns:
            List of merged content blocks with metadata
        """
        if not pages:
            return []
        
        blocks = []
        current_block = {
            "content": pages[0].content,
            "pages": [pages[0].page_number],
            "chapter": pages[0].chapter,
            "section": pages[0].section,
            "verses": list(pages[0].verses),
            "verse_numbers": list(pages[0].verse_numbers),
            "tables": list(pages[0].tables),
        }
        
        for i in range(1, len(pages)):
            page = pages[i]
            
            if page.continues_from_previous:
                # Merge with current block
                current_block["content"] += "\n\n" + page.content
                current_block["pages"].append(page.page_number)
                current_block["verses"].extend(page.verses)
                current_block["verse_numbers"].extend(page.verse_numbers)
                current_block["tables"].extend(page.tables)
                
                # Update chapter/section if this page has them
                if page.chapter:
                    current_block["chapter"] = page.chapter
                if page.section:
                    current_block["section"] = page.section
            else:
                # Save current block and start new one
                blocks.append(current_block)
                current_block = {
                    "content": page.content,
                    "pages": [page.page_number],
                    "chapter": page.chapter,
                    "section": page.section,
                    "verses": list(page.verses),
                    "verse_numbers": list(page.verse_numbers),
                    "tables": list(page.tables),
                }
        
        # Don't forget the last block
        blocks.append(current_block)
        
        return blocks
    
    def extract_verse_commentary_units(self, block: Dict) -> List[SemanticUnit]:
        """
        Extract verse-commentary pairs from a content block.
        
        Args:
            block: Merged content block
            
        Returns:
            List of SemanticUnit objects
        """
        units = []
        content = block["content"]
        
        # Find all verse markers with their positions
        verse_matches = list(re.finditer(self.VERSE_PATTERN, content))
        
        if not verse_matches:
            # No verses found - treat as concept explanation
            return self.create_concept_units(block)
        
        # Extract each verse with its commentary
        for i, match in enumerate(verse_matches):
            verse_num = match.group(1).strip()
            verse_start = match.start()
            
            # Find the Sanskrit verse text (text before the ॥number॥)
            # Look backwards for the start of the verse (previous verse end or section start)
            if i > 0:
                prev_end = verse_matches[i-1].end()
                search_start = prev_end
            else:
                search_start = 0
            
            # The verse text is between search_start and verse_start
            verse_region = content[search_start:verse_start]
            
            # Find the actual Sanskrit verse (look for Devanagari text)
            # Sanskrit verses typically start with Devanagari and end with ॥
            devanagari_match = re.search(r'[\u0900-\u097F][\s\S]*$', verse_region)
            if devanagari_match:
                sanskrit_text = devanagari_match.group(0).strip()
            else:
                sanskrit_text = verse_region.strip()[-200:]  # Last part before marker
            
            # Commentary is text after the verse number marker until next verse or end
            commentary_start = match.end()
            if i < len(verse_matches) - 1:
                # Find where next verse's Sanskrit starts
                next_start = verse_matches[i+1].start()
                # Look for where next Sanskrit verse begins
                next_region = content[commentary_start:next_start]
                next_sanskrit = re.search(r'[\u0900-\u097F]', next_region)
                if next_sanskrit:
                    commentary_end = commentary_start + next_sanskrit.start()
                else:
                    commentary_end = next_start
            else:
                commentary_end = len(content)
            
            commentary_text = content[commentary_start:commentary_end].strip()
            
            # Split commentary into interpretation and notes
            notes_match = re.search(r'\bNotes?\s*:', commentary_text, re.IGNORECASE)
            if notes_match:
                interpretation = commentary_text[:notes_match.start()].strip()
                notes = commentary_text[notes_match.end():].strip()
            else:
                interpretation = commentary_text
                notes = None
            
            # Combine for searchable text
            combined = f"Verse {verse_num}\n\n{sanskrit_text}\n\n{interpretation}"
            if notes:
                combined += f"\n\nNotes: {notes}"
            
            # Create verse data
            verse_data = VerseData(
                number=verse_num,
                sanskrit=sanskrit_text,
                iast=None,  # Could add transliteration later
            )
            
            unit = SemanticUnit(
                unit_id=self.generate_unit_id(block["chapter"], verse_num, UnitType.VERSE_COMMENTARY),
                unit_type=UnitType.VERSE_COMMENTARY,
                source_pages=block["pages"],
                source_book=self.source_book,
                chapter=block["chapter"],
                section=block["section"],
                verse=verse_data,
                commentary=interpretation,
                notes=notes,
                combined_text=combined,
                related_units=[],
                token_count=self.estimate_tokens(combined),
            )
            
            units.append(unit)
        
        return units
    
    def create_concept_units(self, block: Dict) -> List[SemanticUnit]:
        """
        Create concept explanation units from non-verse content.
        
        Args:
            block: Content block without verses
            
        Returns:
            List of SemanticUnit objects
        """
        content = block["content"]
        units = []
        
        # Check if this is a chapter introduction
        if block["chapter"] and content.find(block["chapter"]) < 100:
            unit_type = UnitType.CHAPTER_INTRO
        else:
            unit_type = UnitType.CONCEPT_EXPLANATION
        
        # Split by sections if there are numbered sections
        section_matches = list(re.finditer(self.SECTION_PATTERN, content, re.MULTILINE))
        
        if section_matches:
            # Create unit for each section
            for i, match in enumerate(section_matches):
                section_start = match.start()
                section_end = section_matches[i+1].start() if i < len(section_matches) - 1 else len(content)
                section_content = content[section_start:section_end].strip()
                section_title = match.group(0).strip()
                
                unit = SemanticUnit(
                    unit_id=self.generate_unit_id(block["chapter"], None, unit_type),
                    unit_type=unit_type,
                    source_pages=block["pages"],
                    source_book=self.source_book,
                    chapter=block["chapter"],
                    section=section_title,
                    verse=None,
                    commentary=section_content,
                    notes=None,
                    combined_text=section_content,
                    related_units=[],
                    token_count=self.estimate_tokens(section_content),
                )
                units.append(unit)
        else:
            # Single concept unit for entire block
            unit = SemanticUnit(
                unit_id=self.generate_unit_id(block["chapter"], None, unit_type),
                unit_type=unit_type,
                source_pages=block["pages"],
                source_book=self.source_book,
                chapter=block["chapter"],
                section=block["section"],
                verse=None,
                commentary=content,
                notes=None,
                combined_text=content,
                related_units=[],
                token_count=self.estimate_tokens(content),
            )
            units.append(unit)
        
        return units
    
    def create_table_units(self, block: Dict) -> List[SemanticUnit]:
        """
        Create table-context units for tables in the block.
        
        Args:
            block: Content block with tables
            
        Returns:
            List of SemanticUnit objects
        """
        units = []
        
        for table in block["tables"]:
            if not table:
                continue
            
            # Convert table to text representation
            table_title = table.get("title", "Table")
            headers = table.get("headers", [])
            data = table.get("data", [])
            
            # Build table text
            table_text = f"Table: {table_title}\n\n"
            if headers:
                table_text += " | ".join(headers) + "\n"
                table_text += "-" * 50 + "\n"
            for row in data:
                table_text += " | ".join(str(cell) for cell in row) + "\n"
            
            # Find surrounding context (text near table mention)
            # For now, just use the table itself
            combined = table_text
            
            unit = SemanticUnit(
                unit_id=self.generate_unit_id(block["chapter"], None, UnitType.TABLE_CONTEXT),
                unit_type=UnitType.TABLE_CONTEXT,
                source_pages=block["pages"],
                source_book=self.source_book,
                chapter=block["chapter"],
                section=table_title,
                verse=None,
                commentary=table_text,
                notes=None,
                combined_text=combined,
                related_units=[],
                token_count=self.estimate_tokens(combined),
            )
            units.append(unit)
        
        return units
    
    def split_oversized_unit(self, unit: SemanticUnit) -> List[SemanticUnit]:
        """
        Split an oversized unit into smaller chunks with overlap.
        
        Args:
            unit: Oversized semantic unit
            
        Returns:
            List of smaller units
        """
        if unit.token_count <= self.MAX_TOKENS_PER_UNIT:
            return [unit]
        
        # Split by paragraphs
        paragraphs = unit.combined_text.split('\n\n')
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)
            
            if current_tokens + para_tokens > self.MAX_TOKENS_PER_UNIT:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        # Create new units for each chunk
        result = []
        for i, chunk_text in enumerate(chunks):
            new_unit = SemanticUnit(
                unit_id=f"{unit.unit_id}-part{i+1}",
                unit_type=unit.unit_type,
                source_pages=unit.source_pages,
                source_book=unit.source_book,
                chapter=unit.chapter,
                section=unit.section,
                verse=unit.verse if i == 0 else None,  # Verse only in first part
                commentary=chunk_text if unit.unit_type != UnitType.VERSE_COMMENTARY else None,
                notes=None,
                combined_text=chunk_text,
                related_units=[f"{unit.unit_id}-part{j+1}" for j in range(len(chunks)) if j != i],
                token_count=self.estimate_tokens(chunk_text),
            )
            result.append(new_unit)
        
        return result
    
    def segment_document(self, linked_doc: LinkedDocument) -> SemanticDocument:
        """
        Segment an entire document into semantic units.
        
        Args:
            linked_doc: Linked document from Phase 3
            
        Returns:
            SemanticDocument with all units
        """
        all_units: List[SemanticUnit] = []
        
        # Step 1: Merge continuation pages
        blocks = self.merge_continuation_pages(linked_doc.pages)
        
        # Step 2: Extract units from each block
        for block in blocks:
            # Extract verse-commentary units
            verse_units = self.extract_verse_commentary_units(block)
            all_units.extend(verse_units)
            
            # Extract table units
            if block["tables"]:
                table_units = self.create_table_units(block)
                all_units.extend(table_units)
        
        # Step 3: Split oversized units
        final_units = []
        for unit in all_units:
            if unit.token_count > self.MAX_TOKENS_PER_UNIT:
                split_units = self.split_oversized_unit(unit)
                final_units.extend(split_units)
            else:
                final_units.append(unit)
        
        # Step 4: Build related_units references
        # Units from same chapter are related
        chapter_units: Dict[str, List[str]] = {}
        for unit in final_units:
            if unit.chapter:
                if unit.chapter not in chapter_units:
                    chapter_units[unit.chapter] = []
                chapter_units[unit.chapter].append(unit.unit_id)
        
        for unit in final_units:
            if unit.chapter and unit.chapter in chapter_units:
                unit.related_units = [
                    uid for uid in chapter_units[unit.chapter]
                    if uid != unit.unit_id
                ][:5]  # Limit to 5 related units
        
        return SemanticDocument(
            units=final_units,
            source_file=linked_doc.source_file,
            source_book=self.source_book,
        )
    
    def process_file(
        self,
        input_file: str,
        output_file: Optional[str] = None,
    ) -> SemanticDocument:
        """
        Process a linked JSON file through Phase 4 segmentation.
        
        Args:
            input_file: Path to linked JSON from Phase 3
            output_file: Optional output path
            
        Returns:
            SemanticDocument
        """
        input_path = Path(input_file)
        
        # Load linked document
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        linked_doc = LinkedDocument(**data)
        
        # Segment
        semantic_doc = self.segment_document(linked_doc)
        
        # Save output
        if output_file is None:
            output_file = str(input_path.parent / f"{input_path.stem}_segmented.json")
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(semantic_doc.model_dump(), f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Created {len(semantic_doc.units)} semantic units")
        print(f"[OK] Saved to: {output_path}")
        
        return semantic_doc


def test_with_sample():
    """Test semantic segmenter with sample data."""
    from structural_cleaner import StructuralCleaner
    from page_analyzer import PageAnalyzer
    
    sample_file = Path(__file__).parent.parent.parent.parent / "extracted" / "sample_bphs_pages.json"
    
    if not sample_file.exists():
        print(f"Sample file not found: {sample_file}")
        return
    
    # Phase 2: Clean
    print("Phase 2: Cleaning...")
    cleaner = StructuralCleaner()
    cleaned_doc = cleaner.clean_document(
        [__import__('schemas').ExtractedPage(**p) for p in json.loads(sample_file.read_text(encoding='utf-8'))],
        source_file=str(sample_file)
    )
    
    # Phase 3: Analyze
    print("\nPhase 3: Analyzing...")
    analyzer = PageAnalyzer(use_llm=False)
    linked_doc = analyzer.analyze_document(cleaned_doc)
    
    # Phase 4: Segment
    print("\nPhase 4: Segmenting...")
    segmenter = SemanticSegmenter(source_book="Brihat Parasara Hora Shastra")
    semantic_doc = segmenter.segment_document(linked_doc)
    
    print("\n" + "=" * 70)
    print("PHASE 4 SEGMENTATION RESULTS")
    print("=" * 70)
    
    for unit in semantic_doc.units:
        print(f"\nUnit: {unit.unit_id}")
        print(f"  Type: {unit.unit_type}")
        print(f"  Pages: {unit.source_pages}")
        print(f"  Chapter: {unit.chapter}")
        if unit.verse:
            verse_num_display = unit.verse.number.encode('ascii', 'replace').decode('ascii')
            print(f"  Verse: {verse_num_display}")
        print(f"  Tokens: {unit.token_count}")
        preview = unit.combined_text[:150].encode('ascii', 'replace').decode('ascii')
        print(f"  Preview: {preview}...")
    
    print(f"\nTotal units: {len(semantic_doc.units)}")


if __name__ == "__main__":
    test_with_sample()
