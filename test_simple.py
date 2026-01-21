"""
Simple Engine Test - Tests if imports work
"""
import sys

def test():
    print("Testing imports...")
    print()
    
    errors = []
    
    # Test core
    try:
        from src.engines.core import celestial_bodies, coordinates, datetime_utils, ephemeris, exceptions
        print("✓ Core modules")
    except Exception as e:
        print(f"✗ Core modules: {e}")
        errors.append(str(e))
    
    # Test vedic
    try:
        from src.engines.vedic import vedic_engine, vedic_constants
        print("✓ Vedic engine")
    except Exception as e:
        print(f"✗ Vedic engine: {e}")
        errors.append(str(e))
    
    # Test western
    try:
        from src.engines.western import western_engine, western_constants
        print("✓ Western engine")
    except Exception as e:
        print(f"✗ Western engine: {e}")
        errors.append(str(e))
    
    # Test utils
    try:
        from src.utils import schemas, serializers, validators
        print("✓ Utils")
    except Exception as e:
        print(f"✗ Utils: {e}")
        errors.append(str(e))
    
    # Test tools
    try:
        from src.tools import tools
        print("✓ Tools")
    except Exception as e:
        print(f"✗ Tools: {e}")
        errors.append(str(e))
    
    print()
    if not errors:
        print("✅ ALL IMPORTS SUCCESSFUL")
        
        # Try a basic calculation
        try:
            from src.engines.vedic.vedic_engine import generate_vedic_chart
            from datetime import datetime
            
            print("\nTesting calculation...")
            chart = generate_vedic_chart(
                birth_date=datetime(1995, 10, 1, 7, 30),
                latitude=27.5530,
                longitude=76.6346,
                timezone_str="Asia/Kolkata"
            )
            print(f"✓ Chart calculated")
            print(f"  Lagna: {chart.lagna.rashi_name}")
            print(f"  Moon: {chart.rashi_name}")
            print("\n✅ ENGINE WORKING!")
            return 0
        except Exception as e:
            print(f"✗ Calculation failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
    else:
        print(f"❌ {len(errors)} ERRORS")
        for err in errors:
            print(f"  - {err}")
        return 1

if __name__ == "__main__":
    sys.exit(test())
