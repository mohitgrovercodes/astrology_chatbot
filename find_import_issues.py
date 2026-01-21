"""
Find Import Issues - Scans all Python files for problematic imports
"""

import os
import re
from pathlib import Path

def scan_file_for_imports(filepath):
    """Scan a Python file for import statements"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all import statements
    import_patterns = [
        r'from\s+([\w.]+)\s+import',
        r'import\s+([\w.]+)',
    ]
    
    imports = []
    for pattern in import_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            imports.append(match.group(1))
    
    return imports

def find_problematic_imports(base_path='src'):
    """Find all imports that reference non-existent modules"""
    
    print("=" * 70)
    print("IMPORT ISSUE DETECTOR")
    print("=" * 70)
    print()
    
    # Known issues based on error messages
    known_issues = {
        'src.engines.vedic.constants': 'src.engines.vedic.vedic_constants',
        'src.engines.western.engine': 'src.engines.western.western_engine',
    }
    
    print("Known Import Issues:")
    print("-" * 70)
    for wrong, correct in known_issues.items():
        print(f"❌ WRONG: {wrong}")
        print(f"✅ RIGHT: {correct}")
        print()
    
    # Scan all Python files
    issues_found = []
    
    if os.path.exists(base_path):
        print("Scanning files for these issues...")
        print("-" * 70)
        
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    imports = scan_file_for_imports(filepath)
                    
                    # Check for known problematic imports
                    for imp in imports:
                        for wrong, correct in known_issues.items():
                            if wrong in imp:
                                issues_found.append({
                                    'file': filepath,
                                    'wrong_import': imp,
                                    'suggested_fix': imp.replace(wrong, correct)
                                })
                                print(f"❌ {filepath}")
                                print(f"   Found: {imp}")
                                print(f"   Fix to: {imp.replace(wrong, correct)}")
                                print()
    
    print("=" * 70)
    print(f"SUMMARY: Found {len(issues_found)} problematic imports")
    print("=" * 70)
    print()
    
    if issues_found:
        print("Files that need fixing:")
        unique_files = set(issue['file'] for issue in issues_found)
        for file in sorted(unique_files):
            print(f"  • {file}")
        print()
        print("Action needed:")
        print("  1. I can provide automated fixes for these files")
        print("  2. Or you can manually search/replace in each file:")
        print("     - vedic.constants → vedic.vedic_constants")
        print("     - western.engine → western.western_engine")
    else:
        print("✅ No obvious import issues found!")
        print()
        print("The errors might be in files outside 'src/' directory.")
        print("Check if you have duplicate files or old imports.")
    
    return issues_found

if __name__ == "__main__":
    issues = find_problematic_imports()
