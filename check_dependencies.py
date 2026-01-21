"""
Detailed Import Diagnostic - Shows EXACTLY what's missing
"""

import sys
import importlib

def check_package(package_name, import_name=None):
    """Check if a package can be imported and show detailed error"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        return True, "✓ Installed"
    except ImportError as e:
        return False, f"✗ Missing: {str(e)}"

print("=" * 70)
print("DEPENDENCY CHECK - What's Missing?")
print("=" * 70)
print()

# Critical dependencies
critical_deps = [
    ("pytz", "pytz"),
    ("python-dateutil", "dateutil"),
    ("pydantic", "pydantic"),
    ("langchain", "langchain"),
    ("langchain-core", "langchain_core"),
    ("langchain-openai", "langchain_openai"),
    ("langchain-community", "langchain_community"),
    ("chromadb", "chromadb"),
    ("langgraph", "langgraph"),
    ("fastapi", "fastapi"),
    ("python-dotenv", "dotenv"),
    ("pyyaml", "yaml"),
    ("pyswisseph", "swisseph"),
]

print("Checking Critical Dependencies:")
print("-" * 70)

missing_count = 0
for package, import_name in critical_deps:
    success, message = check_package(package, import_name)
    status = "✓" if success else "✗"
    print(f"{status} {package:25s} {message}")
    if not success:
        missing_count += 1

print()
print("=" * 70)
print(f"SUMMARY: {len(critical_deps) - missing_count}/{len(critical_deps)} dependencies installed")
print("=" * 70)
print()

if missing_count > 0:
    print("⚠️  MISSING DEPENDENCIES DETECTED")
    print()
    print("To fix, run:")
    print("  pip install -r requirements.txt")
    print()
    print("Or install missing packages individually:")
    print("  pip install pytz python-dateutil pydantic langchain langchain-core")
    print()
else:
    print("✅ All critical dependencies are installed!")
    print()
    print("You can now run:")
    print("  python test_all_engines.py")
    print()

# Now check if our project modules can import
print()
print("=" * 70)
print("PROJECT MODULE CHECK")
print("=" * 70)
print()

if missing_count == 0:
    print("Attempting to import project modules...")
    print("-" * 70)
    
    project_modules = [
        "src.engines.core.exceptions",
        "src.engines.core.celestial_bodies",
        "src.engines.vedic.vedic_engine",
        "src.engines.western.western_engine",
        "src.utils.schemas",
        "src.tools.tools",
    ]
    
    for module in project_modules:
        success, message = check_package(module, module)
        status = "✓" if success else "✗"
        print(f"{status} {module:40s} {message}")
else:
    print("⏭️  Skipping project module check (install dependencies first)")

print()
print("=" * 70)