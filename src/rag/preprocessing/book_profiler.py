#!/usr/bin/env python3
"""
Phase 3.5: Automated Book Profiling
Discovers structural DNA (regex patterns, semantic markers) of a book using LLM.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

try:
    from src.llm.factory import LLMFactory
except ImportError:
    # Fallback for standalone testing
    class LLMFactory:
        @classmethod
        def create(cls, **kwargs):
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=kwargs.get("model", "gemini-2.5-flash"))

class BookProfile(BaseModel):
    book_id: str
    parsing_strategy: Dict
    technical_limits: Dict = {"max_tokens": 700, "chunk_overlap": 50}

class BookProfiler:
    """
    Analyzes a text sample to discover structural patterns.
    """
    
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model = LLMFactory.create(
            provider="google",
            model=model_name,
            temperature=0.0
        )
    
    def discover_profile(self, book_title: str, text_sample: str) -> Dict:
        """
        Use LLM to discover regex patterns and markers.
        """
        prompt = f"""You are an Expert Knowledge Engineer. Analyze this sample text from the astrology book "{book_title}". 
Your goal is to extract the structural "DNA" of the book for a RAG system.

TEXT SAMPLE:
---
{text_sample[:4000]}
---

Analyze the sample and return ONLY a JSON object with this structure:
{{
  "verse_pattern": "A python regex to capture verse numbers (e.g. '॥\\s*(\\d+)\\s*॥' or 'Shloka\\s+(\\d+)')",
  "section_pattern": "A python regex for section headers",
  "semantic_markers": ["List of 5-8 phrases the author uses to start a new logical point (e.g. 'Notes:', 'Alternatively:', 'The sage says:')"],
  "hierarchy": ["List levels like 'Chapter', 'Verse', 'Commentary'"],
  "sanskrit_present": true/false
}}

IMPORTANT: 
- Ensure the regex handles variants (spaces, dashes).
- Return ONLY the raw JSON block.
"""

        response = self.model.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean JSON response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        try:
            strategy = json.loads(content)
            
            profile = {
                "book_id": book_title.lower().replace(" ", "_"),
                "parsing_strategy": strategy,
                "technical_limits": {"max_tokens": 700, "chunk_overlap": 50}
            }
            return profile
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return None

    def save_profile(self, profile: Dict):
        """Save profile to profiles directory."""
        output_dir = Path(__file__).parent / "book_profiles"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = output_dir / f"{profile['book_id']}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Profile saved to {file_path}")
        return file_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Automated Book Profiler")
    parser.add_argument("--book", required=True, help="Book title")
    parser.add_argument("--input", required=True, help="Cleaned JSON (Phase 2) or text file")
    
    args = parser.parse_args()
    
    # Load sample text
    input_path = Path(args.input)
    if input_path.suffix == '.json':
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Take first 5 pages of content
            pages = data.get("pages", [])[:5]
            sample_text = "\n\n".join([p.get("content", "") for p in pages])
    else:
        sample_text = input_path.read_text(encoding='utf-8')[:8000]
        
    print(f"Analyzing structure of '{args.book}'...")
    profiler = BookProfiler()
    profile = profiler.discover_profile(args.book, sample_text)
    
    if profile:
        profiler.save_profile(profile)
    else:
        print("Failed to discover profile.")

if __name__ == "__main__":
    main()
