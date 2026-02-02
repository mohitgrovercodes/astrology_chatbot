
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath("."))

from src.engines.western.western_engine import WesternAstroEngine
from src.engines.core.celestial_bodies import CelestialBody

def main():
    engine = WesternAstroEngine()
    
    # Sample data
    birth_date = datetime(1995, 3, 15, 14, 30)
    lat = 26.9124
    lon = 75.7873
    tz = "Asia/Kolkata"
    
    try:
        from src.engines.core.datetime_utils import datetime_to_julian_day
        from src.engines.core.ephemeris import get_house_cusps, HouseSystem
        jd = datetime_to_julian_day(birth_date, latitude=lat, longitude=lon)
        cusps = get_house_cusps(jd, lat, lon, ord('P'))
        print(f"Cusp count: {len(cusps.cusps)}")
        
        print("Generating chart...")
        chart = engine.generate_chart(
            birth_datetime=birth_date,
            latitude=lat,
            longitude=lon,
            timezone=tz
        )
        print("Chart generated successfully!")
        print(f"Sun Sign: {chart.sun_sign_name}")
        print(f"Dignity Score: {chart.dignity_score}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
