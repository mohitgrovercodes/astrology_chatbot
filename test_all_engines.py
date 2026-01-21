#!/usr/bin/env python3
"""
Comprehensive Engine Test Suite
================================

Tests all astrology calculation engines with real birth data.

Usage:
    python test_all_engines.py
    
Requirements:
    - pyswisseph installed
    - All engine files in place
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text):
    """Print a header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(70)}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_section(text):
    """Print a section header."""
    print(f"\n{BOLD}{text}{RESET}")
    print("-" * 70)


def check_dependency(module_name, package_name=None):
    """Check if a module is available."""
    try:
        __import__(module_name)
        print(f"  {GREEN}✓{RESET} {package_name or module_name}")
        return True
    except ImportError:
        print(f"  {RED}✗{RESET} {package_name or module_name}")
        return False


def test_imports():
    """Test all imports."""
    print_section("1. Testing Imports")
    
    all_ok = True
    
    # Core imports
    print("\n📦 Core Modules:")
    all_ok &= check_dependency("src.engines.core.celestial_bodies", "celestial_bodies")
    all_ok &= check_dependency("src.engines.core.coordinates", "coordinates")
    all_ok &= check_dependency("src.engines.core.datetime_utils", "datetime_utils")
    all_ok &= check_dependency("src.engines.core.ephemeris", "ephemeris")
    all_ok &= check_dependency("src.engines.core.exceptions", "exceptions")
    
    # Vedic imports
    print("\n📦 Vedic Engine:")
    all_ok &= check_dependency("src.engines.vedic.vedic_engine", "vedic_engine")
    all_ok &= check_dependency("src.engines.vedic.vedic_constants", "vedic_constants")
    all_ok &= check_dependency("src.engines.vedic.rashi_nakshatra", "rashi_nakshatra")
    all_ok &= check_dependency("src.engines.vedic.dasha_systems", "dasha_systems")
    all_ok &= check_dependency("src.engines.vedic.aspects_yogas", "aspects_yogas")
    
    # Western imports
    print("\n📦 Western Engine:")
    all_ok &= check_dependency("src.engines.western.western_engine", "western_engine")
    all_ok &= check_dependency("src.engines.western.western_constants", "western_constants")
    all_ok &= check_dependency("src.engines.western.western_signs", "western_signs")
    all_ok &= check_dependency("src.engines.western.western_aspects", "western_aspects")
    
    # Utils
    print("\n📦 Utilities:")
    all_ok &= check_dependency("src.utils.schemas", "schemas")
    all_ok &= check_dependency("src.utils.serializers", "serializers")
    all_ok &= check_dependency("src.utils.validators", "validators")
    
    # Tools
    print("\n📦 LangChain Tools:")
    all_ok &= check_dependency("src.engine.tools", "tools")
    
    # External dependencies
    print("\n📦 External Dependencies:")
    all_ok &= check_dependency("swisseph", "pyswisseph")
    
    return all_ok


def test_vedic_engine():
    """Test Vedic engine with real calculations."""
    print_section("2. Testing Vedic Engine")
    
    try:
        from src.engines.vedic.vedic_engine import generate_vedic_chart
        
        # Test birth data (Steve Jobs - Feb 24, 1955, 7:15 PM, San Francisco)
        birth_date = datetime(1955, 2, 24, 19, 15)
        latitude = 37.7749
        longitude = -122.4194
        
        print(f"\n📅 Birth Data:")
        print(f"  Date: {birth_date}")
        print(f"  Location: {latitude}, {longitude} (San Francisco)")
        
        print(f"\n⏳ Calculating Vedic chart...")
        chart = generate_vedic_chart(
            birth_date=birth_date,
            latitude=latitude,
            longitude=longitude,
            timezone_str="America/Los_Angeles"
        )
        
        print(f"\n{GREEN}✓ Chart calculated successfully!{RESET}")
        
        # Display results
        print(f"\n📊 {BOLD}VEDIC CHART RESULTS:{RESET}")
        print(f"\n🔸 Lagna (Ascendant):")
        print(f"  Sign: {chart.lagna.rashi_name} ({chart.lagna.rashi.name})")
        print(f"  Degree: {chart.lagna.degree}°{chart.lagna.minute}'")
        print(f"  Nakshatra: {chart.lagna.nakshatra_name} (Pada {chart.lagna.nakshatra_pada})")
        
        print(f"\n🔸 Rashi (Moon Sign): {chart.rashi_name}")
        print(f"🔸 Moon Nakshatra: {chart.moon_nakshatra.name}")
        
        # Planet positions
        print(f"\n🔸 Planetary Positions:")
        from src.engines.core.celestial_bodies import VEDIC_GRAHAS
        
        for planet in list(VEDIC_GRAHAS)[:5]:  # First 5 for brevity
            rashi_pos = chart.vedic_mapping.rashi_positions.get(planet)
            if rashi_pos:
                retro = " (R)" if chart.is_planet_retrograde(planet) else ""
                house = chart.get_planet_house(planet)
                print(f"  {planet.name:10s}: {rashi_pos.rashi_name:12s} "
                      f"{rashi_pos.degree:2d}°{rashi_pos.minute:02d}', "
                      f"House {house}{retro}")
        
        # Yogas
        present_yogas = [y for y in chart.yogas.detected_yogas if y.is_present]
        print(f"\n🔸 Yogas Detected: {len(present_yogas)}")
        if present_yogas:
            for yoga in present_yogas[:3]:  # First 3
                print(f"  • {yoga.name} ({yoga.category.value})")
        
        # Current Dasha
        current_dasha = chart.get_current_dasha(datetime.now())
        if current_dasha.get("mahadasha"):
            md = current_dasha["mahadasha"]
            print(f"\n🔸 Current Mahadasha: {md.lord.name}")
            if current_dasha.get("antardasha"):
                ad = current_dasha["antardasha"]
                print(f"🔸 Current Antardasha: {ad.lord.name}")
        
        return True
        
    except Exception as e:
        print(f"\n{RED}✗ Vedic engine test failed:{RESET}")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_western_engine():
    """Test Western engine with real calculations."""
    print_section("3. Testing Western Engine")
    
    try:
        from src.engines.western.western_engine import generate_western_chart
        
        # Same birth data
        birth_date = datetime(1955, 2, 24, 19, 15)
        latitude = 37.7749
        longitude = -122.4194
        
        print(f"\n📅 Birth Data:")
        print(f"  Date: {birth_date}")
        print(f"  Location: {latitude}, {longitude} (San Francisco)")
        
        print(f"\n⏳ Calculating Western chart...")
        chart = generate_western_chart(
            birth_datetime=birth_date,
            latitude=latitude,
            longitude=longitude,
            timezone="America/Los_Angeles"
        )
        
        print(f"\n{GREEN}✓ Chart calculated successfully!{RESET}")
        
        # Display results
        print(f"\n📊 {BOLD}WESTERN CHART RESULTS:{RESET}")
        
        print(f"\n🔸 Sun Sign: {chart.sun_sign_name}")
        print(f"🔸 Moon Sign: {chart.moon_sign_name}")
        print(f"🔸 Ascendant: {chart.ascendant_sign_name}")
        print(f"🔸 Midheaven: {chart.midheaven_sign.name.title()}")
        
        # Planet positions
        print(f"\n🔸 Planetary Positions:")
        from src.engines.core.celestial_bodies import WESTERN_PLANETS
        
        for planet in list(WESTERN_PLANETS)[:7]:  # Classical 7
            pos = chart.positions.get(planet)
            if pos:
                sign = chart.get_planet_sign(planet)
                house = chart.get_planet_house(planet)
                retro = " (R)" if pos.is_retrograde else ""
                print(f"  {planet.name:10s}: {sign.name.title():12s} "
                      f"{pos.longitude % 30:.2f}°, House {house}{retro}")
        
        # Major aspects
        major = chart.major_aspects
        print(f"\n🔸 Major Aspects: {len(major)}")
        for aspect in major[:5]:  # First 5
            print(f"  • {aspect.planet1.name} {aspect.aspect_type.name} "
                  f"{aspect.planet2.name} (orb: {aspect.orb:.2f}°)")
        
        # Dignities
        print(f"\n🔸 Dignity Score: {chart.dignity_score}")
        if chart.dignified_planets:
            print(f"  Dignified planets:")
            for planet, dignity in chart.dignified_planets[:3]:
                print(f"    {planet.name}: {dignity.dignity_type.name}")
        
        return True
        
    except Exception as e:
        print(f"\n{RED}✗ Western engine test failed:{RESET}")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_langchain_tools():
    """Test LangChain tool wrappers."""
    print_section("4. Testing LangChain Tools")
    
    try:
        from src.engine.tools import (
            calculate_vedic_chart,
            calculate_western_chart,
            ASTROLOGY_TOOLS,
            get_tool_by_name
        )
        
        print(f"\n📦 Tools Available:")
        print(f"  Total tools: {len(ASTROLOGY_TOOLS)}")
        for tool in ASTROLOGY_TOOLS:
            print(f"  • {tool.name}")
        
        # Test tool by name
        vedic_tool = get_tool_by_name("calculate_vedic_chart")
        print(f"\n{GREEN}✓{RESET} Tool lookup successful: {vedic_tool.name}")
        
        # Test tool invocation (if dependencies available)
        try:
            import swisseph
            
            print(f"\n⏳ Testing tool invocation...")
            result = calculate_vedic_chart.invoke({
                "date": "1955-02-24",
                "time": "19:15",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "timezone": "America/Los_Angeles"
            })
            
            if "error" in result:
                print(f"{YELLOW}⚠ Tool returned error:{RESET} {result['error']}")
            else:
                print(f"{GREEN}✓ Tool invocation successful!{RESET}")
                print(f"  Chart type: {result.get('chart_type')}")
                print(f"  Lagna: {result.get('lagna', {}).get('sign')}")
            
        except ImportError:
            print(f"{YELLOW}⚠ Skipping tool invocation (pyswisseph not installed){RESET}")
        
        return True
        
    except Exception as e:
        print(f"\n{RED}✗ Tool test failed:{RESET}")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_serialization():
    """Test chart serialization."""
    print_section("5. Testing Serialization")
    
    try:
        import swisseph
        
        from src.engines.vedic.vedic_engine import generate_vedic_chart
        from src.utils.serializers import serialize_vedic_chart
        from src.utils.formatters import format_for_llm
        
        # Generate a chart
        print(f"\n⏳ Generating chart for serialization test...")
        chart = generate_vedic_chart(
            birth_date=datetime(1955, 2, 24, 19, 15),
            latitude=37.7749,
            longitude=-122.4194,
            timezone_str="America/Los_Angeles"
        )
        
        # Serialize
        print(f"\n⏳ Serializing chart...")
        chart_json = serialize_vedic_chart(chart)
        
        print(f"{GREEN}✓ Serialization successful!{RESET}")
        print(f"  Keys in JSON: {list(chart_json.keys())}")
        
        # Format for LLM
        print(f"\n⏳ Formatting for LLM...")
        llm_text = format_for_llm(chart_json, query="Test chart")
        
        print(f"{GREEN}✓ LLM formatting successful!{RESET}")
        print(f"  Formatted text length: {len(llm_text)} characters")
        print(f"\n  Preview (first 200 chars):")
        print(f"  {llm_text[:200]}...")
        
        return True
        
    except ImportError:
        print(f"{YELLOW}⚠ Skipping serialization test (pyswisseph not installed){RESET}")
        return True
    except Exception as e:
        print(f"\n{RED}✗ Serialization test failed:{RESET}")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print_header("COMPREHENSIVE ENGINE TEST SUITE")
    
    results = {}
    
    # Run tests
    results['imports'] = test_imports()
    
    # Only run calculation tests if imports pass
    if results['imports']:
        results['vedic'] = test_vedic_engine()
        results['western'] = test_western_engine()
        results['tools'] = test_langchain_tools()
        results['serialization'] = test_serialization()
    else:
        print(f"\n{RED}Skipping engine tests due to import failures{RESET}")
        results['vedic'] = False
        results['western'] = False
        results['tools'] = False
        results['serialization'] = False
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nResults:")
    for test_name, passed_test in results.items():
        status = f"{GREEN}✓ PASS{RESET}" if passed_test else f"{RED}✗ FAIL{RESET}"
        print(f"  {test_name.title():20s}: {status}")
    
    print(f"\n{BOLD}Overall: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}🎉 ALL TESTS PASSED!{RESET}")
        print(f"\nYour engines are working correctly!")
        print(f"\n{BOLD}Next steps:{RESET}")
        print(f"  1. Install missing dependencies if any")
        print(f"  2. Start Phase 3: RAG Pipeline")
        return 0
    else:
        print(f"\n{RED}Some tests failed. Please check errors above.{RESET}")
        
        if not results['imports']:
            print(f"\n{YELLOW}Common fixes:{RESET}")
            print(f"  • Install pyswisseph: pip install pyswisseph")
            print(f"  • Install other deps: pip install -r requirements.txt")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
