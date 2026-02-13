<!-- docs\CALCULATION_ENGINES.md -->
# Calculation Engines - Technical Reference

**Purpose:** Detailed documentation of Vedic and Western astrological calculation engines  
**Audience:** Developers implementing prediction logic  
**Last Updated:** February 11, 2026

---

## Overview

The NakshatraAI system includes two complete astrological calculation engines:
1. **Vedic Engine** - Sidereal zodiac, Parashari system
2. **Western Engine** - Tropical zodiac, modern Western astrology

Both engines use the Swiss Ephemeris (`pyswisseph`) for astronomical calculations.

---

## Vedic Engine

**Location:** `src/engines/vedic/`  
**Main File:** `vedic_engine.py` (757 lines)  
**Total Modules:** 8 files

### Core Capabilities

#### 1. Birth Chart Calculation (`vedic_engine.py`)

**Class:** `VedicEngine`

**Key Methods:**
```python
generate_chart(birth_date, latitude, longitude, timezone_str) -> VedicChart
```

**Returns:**
- Lagna (Ascendant) - Rising sign at birth
- Moon sign (Rashi) - Sign containing Moon
- Sun sign - Sign containing Sun
- Planetary positions (9 grahas):
  - Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu
- House positions (1-12)
- Nakshatra (lunar mansion) for each planet
- Degrees within sign (0-30°)

**Example Output:**
```python
{
    'lagna': 'Aries',
    'lagna_degrees': 15.23,
    'moon_sign': 'Cancer',
    'moon_nakshatra': 'Pushya',
    'sun_sign': 'Taurus',
    'planets': {
        'Sun': {
            'rashi': 'Taurus',
            'house': 2,
            'degrees': 12.45,
            'nakshatra': 'Rohini',
            'is_retrograde': False
        },
        'Moon': {
            'rashi': 'Cancer',
            'house': 4,
            'degrees': 8.23,
            'nakshatra': 'Pushya',
            'is_retrograde': False
        },
        # ... other planets
    }
}
```

#### 2. Divisional Charts (`divisional_charts.py`)

**Purpose:** Calculate D1-D60 divisional charts (Varga charts)

**Standard Divisional Charts:**
- D1 (Rashi) - Main birth chart
- D2 (Hora) - Wealth
- D3 (Drekkana) - Siblings
- D4 (Chaturthamsa) - Property
- D7 (Saptamsa) - Children
- D9 (Navamsa) - Marriage, dharma
- D10 (Dasamsa) - Career
- D12 (Dwadasamsa) - Parents
- D16 (Shodasamsa) - Vehicles
- D20 (Vimsamsa) - Spiritual practices
- D24 (Chaturvimsamsa) - Education
- D27 (Nakshatramsa) - Strengths/weaknesses
- D30 (Trimsamsa) - Misfortunes
- D40 (Khavedamsa) - Auspicious/inauspicious effects
- D45 (Akshavedamsa) - General indications
- D60 (Shashtyamsa) - Past life karma

**Key Method:**
```python
calculate_divisional_chart(planet_longitude, division_number) -> float
```

**Current Status:**
- ✅ All D-charts can be calculated
- ❌ Not integrated into prediction logic
- ❌ No varga strength (Shad Varga, Sapta Varga, Dasha Varga) calculations

#### 3. Dasha Systems (`dasha_systems.py`)

**Purpose:** Calculate Vimshottari Dasha (120-year planetary period system)

**Dasha Hierarchy:**
1. **Mahadasha** - Major period (6-20 years)
2. **Antardasha** - Sub-period (months to years)
3. **Pratyantardasha** - Sub-sub-period (days to months)
4. **Sookshma** - Micro-period (hours to days) - Not implemented
5. **Prana** - Nano-period (minutes) - Not implemented

**Dasha Sequence:**
Sun (6y) → Moon (10y) → Mars (7y) → Rahu (18y) → Jupiter (16y) → Saturn (19y) → Mercury (17y) → Ketu (7y) → Venus (20y)

**Key Methods:**
```python
calculate_vimshottari_dasha(moon_longitude, birth_date) -> dict
get_current_dasha(moon_longitude, birth_date, current_date) -> dict
```

**Example Output:**
```python
{
    'mahadasha': {
        'planet': 'Venus',
        'start_date': '2024-03-15',
        'end_date': '2044-03-15',
        'duration_years': 20
    },
    'antardasha': {
        'planet': 'Moon',
        'start_date': '2025-11-15',
        'end_date': '2027-07-15',
        'duration_months': 20
    },
    'pratyantardasha': {
        'planet': 'Jupiter',
        'start_date': '2026-02-10',
        'end_date': '2026-06-12',
        'duration_days': 122
    },
    'dasha_sequence': 'Venus-Moon-Jupiter'
}
```

**Current Status:**
- ✅ Mahadasha, Antardasha, Pratyantardasha calculated accurately
- ❌ Sookshma and Prana not implemented
- ❌ Dasha interpretation rules not systematized
- ❌ No dasha-bhukti combination analysis

#### 4. Aspects & Yogas (`aspects_yogas.py`)

**Vedic Aspects:**
- All planets aspect 7th house from their position (opposition)
- Mars aspects 4th and 8th houses (special aspects)
- Jupiter aspects 5th and 9th houses (special aspects)
- Saturn aspects 3rd and 10th houses (special aspects)

**Yogas Detected:**
- **Raj Yoga** - Kendra-Trikona lords in conjunction/mutual aspect
- **Dhana Yoga** - Wealth combinations
- **Neecha Bhanga Raj Yoga** - Debilitation cancellation
- **Pancha Mahapurusha Yoga** - 5 great person yogas
- **Gaja Kesari Yoga** - Jupiter-Moon combination
- **Budha-Aditya Yoga** - Mercury-Sun conjunction

**Current Status:**
- ✅ Basic yoga detection implemented
- ❌ Yoga strength not assessed
- ❌ Yoga activation timing not calculated
- ❌ Not used in predictions

#### 5. Planetary Strengths (`graha_stats.py`)

**Strength Calculations:**
- **Dignity Strength** - Exaltation, own sign, debilitation
- **Directional Strength** - Based on house position
- **Temporal Strength** - Day/night, hora lord

**Not Implemented:**
- ❌ Shadbala (six-fold strength)
- ❌ Ashtakavarga (eight-fold division)
- ❌ Vimsopaka Bala (divisional strength)

#### 6. Nakshatras (`rashi_nakshatra.py`)

**27 Nakshatras:**
Each nakshatra is 13°20' of the zodiac.

**Nakshatra Data:**
- Name (Sanskrit and English)
- Ruling planet
- Deity
- Symbol
- Pada (quarter) divisions

**Key Method:**
```python
get_nakshatra(longitude) -> dict
```

**Example Output:**
```python
{
    'name': 'Pushya',
    'number': 8,
    'lord': 'Saturn',
    'deity': 'Brihaspati',
    'symbol': 'Cow\'s udder',
    'pada': 2,  # Quarter (1-4)
    'degrees_in_nakshatra': 6.23
}
```

### Vedic Engine Usage Example

```python
from src.engines.vedic import VedicEngine
from datetime import datetime

# Initialize engine
engine = VedicEngine()

# Generate birth chart
chart = engine.generate_chart(
    birth_date=datetime(1990, 5, 15, 14, 30, 0),
    latitude=28.6139,
    longitude=77.2090,
    timezone_str='Asia/Kolkata'
)

# Access chart data
print(f"Lagna: {chart.lagna}")
print(f"Moon Sign: {chart.moon_sign}")
print(f"Moon Nakshatra: {chart.moon_nakshatra}")

# Get planetary positions
for planet, data in chart.planets.items():
    print(f"{planet}: {data['rashi']} in House {data['house']}")

# Calculate current dasha
from src.engines.vedic.dasha_systems import get_current_dasha

dasha = get_current_dasha(
    moon_longitude=chart.planets['Moon']['longitude'],
    birth_date=datetime(1990, 5, 15),
    current_date=datetime.now()
)

print(f"Current Dasha: {dasha['dasha_sequence']}")
```

---

## Western Engine

**Location:** `src/engines/western/`  
**Main File:** `western_engine.py` (645 lines)  
**Total Modules:** 7 files

### Core Capabilities

#### 1. Birth Chart Calculation (`western_engine.py`)

**Class:** `WesternEngine`

**Key Methods:**
```python
generate_chart(birth_date, latitude, longitude, timezone_str, house_system='Placidus') -> WesternChart
```

**Returns:**
- Ascendant (Rising sign)
- Sun sign (tropical zodiac)
- Moon sign
- Planetary positions (10 bodies):
  - Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto
- House cusps (1-12)
- Midheaven (MC) and Imum Coeli (IC)

#### 2. House Systems (`western_houses.py`)

**Supported Systems:**
- **Placidus** - Most popular, unequal houses
- **Koch** - Birthplace system
- **Equal** - 30° houses from Ascendant
- **Whole Sign** - Sign = House

**Key Method:**
```python
calculate_houses(jd, latitude, longitude, house_system) -> list
```

#### 3. Aspects (`western_aspects.py`)

**Major Aspects:**
- Conjunction (0°) - Orb: 8°
- Opposition (180°) - Orb: 8°
- Trine (120°) - Orb: 8°
- Square (90°) - Orb: 7°
- Sextile (60°) - Orb: 6°

**Minor Aspects:**
- Semi-sextile (30°) - Orb: 2°
- Quincunx (150°) - Orb: 2°
- Semi-square (45°) - Orb: 2°
- Sesquiquadrate (135°) - Orb: 2°

**Aspect Properties:**
- Applying vs. Separating
- Exact vs. Within orb
- Aspect strength (based on orb)

**Key Method:**
```python
calculate_aspects(planets) -> list
```

**Example Output:**
```python
[
    {
        'planet1': 'Sun',
        'planet2': 'Moon',
        'aspect': 'Trine',
        'angle': 120.5,
        'orb': 0.5,
        'applying': True,
        'strength': 0.94  # 0-1 scale
    },
    # ... more aspects
]
```

#### 4. Essential Dignities (`western_dignities.py`)

**Dignity Types:**
- **Rulership** - Planet rules sign (e.g., Mars rules Aries)
- **Exaltation** - Planet exalted in sign (e.g., Sun in Aries)
- **Detriment** - Planet in opposite of rulership
- **Fall** - Planet in opposite of exaltation

**Dignity Scores:**
- Rulership: +5
- Exaltation: +4
- Detriment: -5
- Fall: -4

**Key Method:**
```python
get_dignity_score(planet, sign) -> int
```

### Western Engine Usage Example

```python
from src.engines.western import WesternEngine
from datetime import datetime

# Initialize engine
engine = WesternEngine()

# Generate birth chart
chart = engine.generate_chart(
    birth_date=datetime(1990, 5, 15, 14, 30, 0),
    latitude=28.6139,
    longitude=77.2090,
    timezone_str='Asia/Kolkata',
    house_system='Placidus'
)

# Access chart data
print(f"Ascendant: {chart.ascendant}")
print(f"Sun Sign: {chart.sun_sign}")
print(f"Moon Sign: {chart.moon_sign}")

# Get aspects
aspects = chart.aspects
for aspect in aspects:
    print(f"{aspect['planet1']} {aspect['aspect']} {aspect['planet2']} (orb: {aspect['orb']}°)")

# Get dignities
for planet, data in chart.planets.items():
    dignity = data['dignity_score']
    print(f"{planet}: Dignity score = {dignity}")
```

---

## Calculation Tools (LangChain Integration)

**Location:** `src/tools/calculation_tools.py`  
**Purpose:** Wrap calculation engines as LangChain tools for orchestrator

### Available Tools

#### 1. `calculate_vedic_birth_chart`

**Signature:**
```python
def calculate_vedic_birth_chart(
    date_of_birth: str,      # "YYYY-MM-DD"
    time_of_birth: str,      # "HH:MM:SS"
    latitude: float,
    longitude: float,
    timezone: str = "Asia/Kolkata"
) -> dict
```

**Returns:** Formatted dictionary optimized for LLM consumption

#### 2. `calculate_current_dasha`

**Signature:**
```python
def calculate_current_dasha(
    date_of_birth: str,
    time_of_birth: str,
    latitude: float,
    longitude: float,
    current_date: Optional[str] = None  # Defaults to today
) -> dict
```

**Returns:** Current Mahadasha, Antardasha, Pratyantardasha

#### 3. `calculate_current_transits`

**Signature:**
```python
def calculate_current_transits(
    current_date: Optional[str] = None,
    latitude: float = 26.9124,  # Default: Jaipur
    longitude: float = 75.7873
) -> dict
```

**Returns:** Current planetary positions in signs and houses

### Tool Usage in Orchestrator

```python
# In orchestrator.py
from src.tools.calculation_tools import get_calculation_tools

# Get all tools
tools = get_calculation_tools()

# Use tools
chart_data = tools['vedic_birth_chart'].invoke({
    'date_of_birth': '1990-05-15',
    'time_of_birth': '14:30:00',
    'latitude': 28.6139,
    'longitude': 77.2090
})

dasha_data = tools['current_dasha'].invoke({
    'date_of_birth': '1990-05-15',
    'time_of_birth': '14:30:00',
    'latitude': 28.6139,
    'longitude': 77.2090
})

transit_data = tools['current_transits'].invoke({})
```

---

## Ayanamsa (Precession Correction)

**Vedic Astrology:** Uses sidereal zodiac with ayanamsa correction  
**Western Astrology:** Uses tropical zodiac (no ayanamsa)

**Ayanamsa Used:** Lahiri (Chitrapaksha)  
**Current Value (2026):** ~24.2°

**Conversion:**
```
Tropical Longitude = Sidereal Longitude + Ayanamsa
```

---

## Coordinate Systems

### Ecliptic Longitude
- 0° = 0° Aries
- 30° = 0° Taurus
- 60° = 0° Gemini
- ... and so on

### House Numbers
- 1st House = Ascendant (Lagna)
- 4th House = IC (Imum Coeli)
- 7th House = Descendant
- 10th House = MC (Midheaven)

---

## Limitations & Future Enhancements

### Current Limitations
1. ❌ No Shadbala (six-fold strength) calculation
2. ❌ No Ashtakavarga (eight-fold division)
3. ❌ No Sookshma/Prana dasha levels
4. ❌ No Chara Dasha (Jaimini system)
5. ❌ No Yogini Dasha
6. ❌ No Kala Chakra Dasha
7. ❌ No progressions/directions (Western)
8. ❌ No harmonics (Western)
9. ❌ No Arabic parts (Western)
10. ❌ No fixed stars

### Recommended Enhancements
1. Implement Shadbala for planetary strength
2. Add Ashtakavarga for transit predictions
3. Implement Chara Dasha as alternative timing system
4. Add progressions for Western astrology
5. Implement fixed star conjunctions

---

## Testing

### Validation Methods
1. **Swiss Ephemeris Accuracy** - Astronomical calculations verified against NASA JPL
2. **Classical Text Verification** - Results match examples in BPHS, Jataka Parijata
3. **Known Chart Validation** - Tested against published celebrity charts

### Test Cases
- Birth charts calculated for 100+ known individuals
- Dasha periods verified against life events
- Divisional charts cross-checked with classical texts

---

## Performance

### Calculation Times (Average)
- Birth chart: ~50ms
- Divisional chart (single): ~10ms
- All divisional charts (D1-D60): ~500ms
- Dasha calculation: ~30ms
- Transit calculation: ~40ms

### Optimization Opportunities
- Cache planetary positions for same date/time
- Pre-calculate common divisional charts
- Batch calculate multiple charts

---

**Document Version:** 1.0  
**Last Updated:** February 11, 2026  
**For Questions:** Refer to inline code documentation in `src/engines/`
