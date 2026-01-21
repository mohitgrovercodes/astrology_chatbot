"""
Detailed Import Error Analyzer - Shows exactly what's wrong and where
"""

import os
import re
import ast
from pathlib import Path

def analyze_python_file(filepath):
    """Extract all imports and definitions from a Python file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        imports = []
        definitions = []
        
        for node in ast.walk(tree):
            # Collect imports
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append({
                        'type': 'from',
                        'module': module,
                        'name': alias.name,
                        'line': node.lineno
                    })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'type': 'import',
                        'module': alias.name,
                        'line': node.lineno
                    })
            
            # Collect definitions (classes, functions, variables)
            if isinstance(node, ast.ClassDef):
                definitions.append({'type': 'class', 'name': node.name, 'line': node.lineno})
            elif isinstance(node, ast.FunctionDef):
                definitions.append({'type': 'function', 'name': node.name, 'line': node.lineno})
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions.append({'type': 'variable', 'name': target.id, 'line': node.lineno})
        
        return {'imports': imports, 'definitions': definitions}
    except Exception as e:
        return {'error': str(e)}

def find_files_importing(search_term, base_path='src'):
    """Find all files that import a specific term"""
    files_with_import = []
    
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if search_term in content:
                        # Find line numbers
                        lines = content.split('\n')
                        line_numbers = []
                        for i, line in enumerate(lines, 1):
                            if search_term in line:
                                line_numbers.append((i, line.strip()))
                        
                        files_with_import.append({
                            'file': filepath,
                            'lines': line_numbers
                        })
                except:
                    pass
    
    return files_with_import

def main():
    print("=" * 80)
    print("DETAILED IMPORT ERROR ANALYZER")
    print("=" * 80)
    print()
    
    # Check vedic_constants.py
    print("1. ANALYZING: src/engines/vedic/vedic_constants.py")
    print("-" * 80)
    vedic_constants_path = "src/engines/vedic/vedic_constants.py"
    
    if os.path.exists(vedic_constants_path):
        result = analyze_python_file(vedic_constants_path)
        
        if 'error' in result:
            print(f"❌ ERROR: {result['error']}")
        else:
            print(f"✓ File exists and can be parsed")
            print()
            print("Definitions found in vedic_constants.py:")
            for defn in result['definitions']:
                print(f"  • {defn['type']:10s} {defn['name']:30s} (line {defn['line']})")
            
            # Check if Ayanamsa is defined
            ayanamsa_found = any(d['name'] == 'Ayanamsa' for d in result['definitions'])
            if not ayanamsa_found:
                print()
                print("❌ ISSUE: 'Ayanamsa' is NOT defined in this file!")
                print("   But other files are trying to import it.")
    else:
        print(f"❌ ERROR: File not found: {vedic_constants_path}")
    
    print()
    print()
    
    # Find who's trying to import Ayanamsa
    print("2. WHO'S IMPORTING 'Ayanamsa'?")
    print("-" * 80)
    importers = find_files_importing("Ayanamsa", "src")
    
    if importers:
        for item in importers:
            print(f"\n📄 {item['file']}")
            for line_num, line_content in item['lines']:
                print(f"   Line {line_num}: {line_content}")
    else:
        print("✓ No files are importing 'Ayanamsa'")
    
    print()
    print()
    
    # Find remaining western.constants imports
    print("3. CHECKING: western.constants imports")
    print("-" * 80)
    western_importers = find_files_importing("western.constants", "src")
    
    if western_importers:
        print("❌ Found files still using 'western.constants':")
        for item in western_importers:
            print(f"\n📄 {item['file']}")
            for line_num, line_content in item['lines']:
                print(f"   Line {line_num}: {line_content}")
    else:
        print("✓ No files are importing 'western.constants' (old path)")
    
    print()
    print()
    
    # Check western_constants.py
    print("4. ANALYZING: src/engines/western/western_constants.py")
    print("-" * 80)
    western_constants_path = "src/engines/western/western_constants.py"
    
    if os.path.exists(western_constants_path):
        result = analyze_python_file(western_constants_path)
        if 'error' not in result:
            print(f"✓ File exists")
            print(f"  Contains {len(result['definitions'])} definitions")
    else:
        print(f"❌ ERROR: File not found: {western_constants_path}")
    
    print()
    print("=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    # Provide specific fixes
    if not ayanamsa_found and importers:
        print("❌ CRITICAL ISSUE: 'Ayanamsa' import error")
        print()
        print("Files are trying to import 'Ayanamsa' but it doesn't exist.")
        print("Two possible solutions:")
        print()
        print("Option 1: Remove 'Ayanamsa' from imports (if not needed)")
        print("Option 2: Define 'Ayanamsa' in vedic_constants.py")
        print()
    
    if western_importers:
        print("❌ ISSUE: Old 'western.constants' imports still exist")
        print()
        print("Need to replace:")
        print("  western.constants → western.western_constants")
        print()
    
    print("Next step: Run 'python fix_imports_v2.py' to automatically fix these issues")
    print()

if __name__ == "__main__":
    main()
