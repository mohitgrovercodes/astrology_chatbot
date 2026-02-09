"""
Example: Using Third-Party Astrology API
=========================================

This script demonstrates how to use the AstrologyAPIClient
to fetch birth chart data and other calculations from external APIs.
"""

from src.api.astrology_api_client import get_astrology_api_client, AstrologyAPIClient
import json


def example_birth_chart():
    """Example: Get birth chart from API."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Birth Chart Calculation")
    print("="*60)
    
    # Get client from environment variables
    client = get_astrology_api_client()
    
    if not client:
        print("❌ API not configured. Set ASTRO_API_BASE_URL in .env")
        return
    
    try:
        # Birth data
        birth_data = {
            "date": "1990-05-15",
            "time": "14:30:00",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata",
            "system": "vedic"
        }
        
        print(f"\n📅 Birth Data:")
        print(f"  Date: {birth_data['date']}")
        print(f"  Time: {birth_data['time']}")
        print(f"  Place: New Delhi, India")
        print(f"  System: {birth_data['system'].title()}")
        
        # Get birth chart
        print("\n🔄 Fetching birth chart from API...")
        chart = client.get_birth_chart(**birth_data)
        
        print("\n✅ Birth Chart Received:")
        print(json.dumps(chart, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()


def example_planetary_positions():
    """Example: Get current planetary positions."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Planetary Positions")
    print("="*60)
    
    client = get_astrology_api_client()
    
    if not client:
        print("❌ API not configured")
        return
    
    try:
        from datetime import datetime
        
        now = datetime.now()
        
        print(f"\n🌍 Location: New Delhi, India")
        print(f"📅 Date: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get planetary positions
        print("\n🔄 Fetching planetary positions...")
        positions = client.get_planetary_positions(
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
            latitude=28.6139,
            longitude=77.2090,
            timezone="Asia/Kolkata"
        )
        
        print("\n✅ Planetary Positions:")
        print(json.dumps(positions, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()


def example_vimshottari_dasha():
    """Example: Get Vimshottari Dasha."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Vimshottari Dasha")
    print("="*60)
    
    client = get_astrology_api_client()
    
    if not client:
        print("❌ API not configured")
        return
    
    try:
        # Birth data
        print("\n📅 Birth: May 15, 1990, 14:30, New Delhi")
        
        # Get dasha
        print("\n🔄 Calculating Vimshottari Dasha...")
        dasha = client.get_vimshottari_dasha(
            date="1990-05-15",
            time="14:30:00",
            latitude=28.6139,
            longitude=77.2090,
            timezone="Asia/Kolkata"
        )
        
        print("\n✅ Current Dasha:")
        print(json.dumps(dasha, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()


def example_transits():
    """Example: Get current transits."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Current Transits")
    print("="*60)
    
    client = get_astrology_api_client()
    
    if not client:
        print("❌ API not configured")
        return
    
    try:
        from datetime import datetime
        
        print(f"\n📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
        print("🌍 Location: New Delhi, India")
        
        # Get transits
        print("\n🔄 Fetching current transits...")
        transits = client.get_transits(
            latitude=28.6139,
            longitude=77.2090
        )
        
        print("\n✅ Current Transits:")
        print(json.dumps(transits, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()


def example_compatibility():
    """Example: Get compatibility analysis."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Compatibility Analysis")
    print("="*60)
    
    client = get_astrology_api_client()
    
    if not client:
        print("❌ API not configured")
        return
    
    try:
        # Person 1
        person1 = {
            "date": "1990-05-15",
            "time": "14:30:00",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata"
        }
        
        # Person 2
        person2 = {
            "date": "1995-08-22",
            "time": "09:15:00",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "timezone": "Asia/Kolkata"
        }
        
        print("\n👤 Person 1: May 15, 1990, New Delhi")
        print("👤 Person 2: Aug 22, 1995, Mumbai")
        
        # Get compatibility
        print("\n🔄 Analyzing compatibility...")
        compatibility = client.get_compatibility(
            person1=person1,
            person2=person2,
            system="vedic"
        )
        
        print("\n✅ Compatibility Analysis:")
        print(json.dumps(compatibility, indent=2))
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()


def example_with_caching():
    """Example: Demonstrate caching."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Caching Demonstration")
    print("="*60)
    
    client = get_astrology_api_client()
    
    if not client:
        print("❌ API not configured")
        return
    
    try:
        import time
        
        params = {
            "date": "1990-05-15",
            "time": "14:30:00",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "timezone": "Asia/Kolkata"
        }
        
        # First request (will hit API)
        print("\n🔄 First request (will fetch from API)...")
        start = time.time()
        positions1 = client.get_planetary_positions(**params)
        time1 = time.time() - start
        print(f"⏱️  Time: {time1:.3f}s")
        
        # Second request (will use cache)
        print("\n🔄 Second request (will use cache)...")
        start = time.time()
        positions2 = client.get_planetary_positions(**params)
        time2 = time.time() - start
        print(f"⏱️  Time: {time2:.3f}s")
        
        print(f"\n📊 Speed improvement: {time1/time2:.1f}x faster")
        
        # Clear cache
        print("\n🗑️  Clearing cache...")
        client.clear_cache()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.close()


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Third-Party Astrology API Examples")
    print("="*60)
    
    print("\n⚙️  Configuration:")
    print("  Set ASTRO_API_BASE_URL and ASTRO_API_KEY in .env")
    print("  Example: ASTRO_API_BASE_URL=https://api.example.com/v1")
    
    # Run examples
    example_birth_chart()
    example_planetary_positions()
    example_vimshottari_dasha()
    example_transits()
    example_compatibility()
    example_with_caching()
    
    print("\n" + "="*60)
    print("✅ Examples completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
