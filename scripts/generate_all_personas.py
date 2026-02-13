# scripts\generate_all_personas.py
"""
Batch generate personas for all target languages.

This script pre-generates personas for major Indian and foreign languages
instead of generating them on-demand. Allows for quality review and
ensures consistency.

Languages covered:
- 22 Indian languages (scheduled languages of India)
- 10 popular foreign languages
"""

import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()  # Load .env file for API keys

from src.ai.persona_generator import PersonaGenerator
from src.llm.factory import create_llm
from src.utils.localization import LocalizationManager
import json
from pathlib import Path


# Target languages
INDIAN_LANGUAGES = {
    # Major languages (already manual)
    # 'en': 'English',  # Skip - already manual
    # 'hi': 'Hindi',    # Skip - already manual
    # 'ta': 'Tamil',    # Skip - already manual
    
    # Generate for rest of 22 scheduled languages
    'bn': 'Bengali',
    'te': 'Telugu',
    'mr': 'Marathi',
    'gu': 'Gujarati',
    'kn': 'Kannada',
    'ml': 'Malayalam',
    'pa': 'Punjabi',
    'or': 'Odia',
    'as': 'Assamese',
    'ur': 'Urdu',
    'sa': 'Sanskrit',
    'ks': 'Kashmiri',
    'sd': 'Sindhi',
    'ne': 'Nepali',
    'ko': 'Konkani',
    'mi': 'Maithili',
    'do': 'Dogri',
    'sa': 'Santali',
    'bo': 'Bodo',
    'ma': 'Manipuri',
    
    # Romanized versions (important!)
    'bn-lat': 'Bengali (Romanized)',
    'te-lat': 'Telugu (Romanized)',
    'mr-lat': 'Marathi (Romanized)',
    'gu-lat': 'Gujarati (Romanized)',
    'kn-lat': 'Kannada (Romanized)',
    'ml-lat': 'Malayalam (Romanized)',
    'pa-lat': 'Punjabi (Romanized)',
}

FOREIGN_LANGUAGES = {
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
}


def load_english_template():
    """Load English locale as template."""
    locale_path = Path(__file__).parent.parent / 'src' / 'locales' / 'en.json'
    with open(locale_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_all_personas(language_dict, category_name, llm):
    """Generate personas for a dictionary of languages."""
    print(f"\n{'='*70}")
    print(f"Generating {category_name} Personas")
    print(f"{'='*70}\n")
    
    english_template = load_english_template()
    generator = PersonaGenerator(llm, english_template)
    localization = LocalizationManager()
    
    generated_count = 0
    skipped_count = 0
    error_count = 0
    
    for lang_code, lang_name in language_dict.items():
        print(f"\n[{lang_code}] {lang_name}")
        print("-" * 50)
        
        # Check if already exists
        existing = localization.get_persona_data(lang_code, 'vedic', llm=None)
        if existing and existing.get('identity'):
            # Check if it's from cache or manual
            locale_file = Path(__file__).parent.parent / 'src' / 'locales' / f'{lang_code}.json'
            
            if locale_file.exists():
                print(f"  [SKIP] Locale file already exists")
                skipped_count += 1
                continue
        
        # Generate
        try:
            print(f"  [GENERATING...] {lang_name}")
            locale_data = generator.generate_full_locale(lang_code, lang_name)
            
            # Save to locales directory (same as manual ones)
            output_dir = Path(__file__).parent.parent / 'src' / 'locales'
            output_dir.mkdir(exist_ok=True)
            
            output_file = output_dir / f'{lang_code}.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(locale_data, f, ensure_ascii=False, indent=2)
            
            print(f"  [SUCCESS] Saved to {output_file.name}")
            generated_count += 1
            
        except Exception as e:
            print(f"  [ERROR] {e}")
            error_count += 1
    
    print(f"\n{'='*70}")
    print(f"{category_name} Summary:")
    print(f"  Generated: {generated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"{'='*70}")
    
    return generated_count, skipped_count, error_count


def main():
    """Main generation function."""
    print("\n" + "="*70)
    print("BATCH PERSONA GENERATION")
    print("="*70)
    print("\nThis will generate personas for:")
    print(f"  - {len(INDIAN_LANGUAGES)} Indian languages")
    print(f"  - {len(FOREIGN_LANGUAGES)} foreign languages")
    print(f"  - Total: {len(INDIAN_LANGUAGES) + len(FOREIGN_LANGUAGES)} languages")
    print("\nEstimated cost: ~${(len(INDIAN_LANGUAGES) + len(FOREIGN_LANGUAGES)) * 0.01:.2f}")
    print("Estimated time: ~{} minutes".format((len(INDIAN_LANGUAGES) + len(FOREIGN_LANGUAGES)) * 2))
    
    # Confirm
    response = input("\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Initialize LLM
    print("\nInitializing LLM...")
    llm = create_llm(
        provider='openai',
        model='gpt-4o-mini',  # Fast and cheap for generation
        temperature=0.7
    )
    print("[OK] LLM ready")
    
    # Generate Indian languages
    indian_gen, indian_skip, indian_err = generate_all_personas(
        INDIAN_LANGUAGES,
        "Indian Languages",
        llm
    )
    
    # Generate foreign languages
    foreign_gen, foreign_skip, foreign_err = generate_all_personas(
        FOREIGN_LANGUAGES,
        "Foreign Languages",
        llm
    )
    
    # Final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    print(f"\nTotal Generated: {indian_gen + foreign_gen}")
    print(f"Total Skipped: {indian_skip + foreign_skip}")
    print(f"Total Errors: {indian_err + foreign_err}")
    print(f"\nAll personas saved to: src/locales/")
    print("\nNext steps:")
    print("  1. Review generated personas for quality")
    print("  2. Manually edit any that need improvement")
    print("  3. Commit to version control")
    print("="*70)


if __name__ == "__main__":
    main()
