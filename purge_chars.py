import os
import re

def purge_non_ascii(directory):
    replacements = {
        '✓': '[OK]',
        '✗': '[FAIL]',
        '✅': '[DONE]',
        '→': '->',
        '👉': '->',
        '🚀': '[START]',
        '♈': 'Aries',
        '♉': 'Taurus',
        '♊': 'Gemini',
        '♋': 'Cancer',
        '♌': 'Leo',
        '♍': 'Virgo',
        '♎': 'Libra',
        '♏': 'Scorpio',
        '♐': 'Sagittarius',
        '♑': 'Capricorn',
        '♒': 'Aquarius',
        '♓': 'Pisces',
        '☌': 'Conjunction',
        '☍': 'Opposition',
        '△': 'Trine',
        '□': 'Square',
        '⚹': 'Sextile'
    }
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    for char, replacement in replacements.items():
                        content = content.replace(char, replacement)
                    
                    if content != original_content:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Purged non-ASCII from {path}")
                except Exception as e:
                    print(f"Error processing {path}: {e}")

if __name__ == "__main__":
    purge_non_ascii('src')
