# src/engines/vedic/__init__.py
# src\engines\vedic\__init__.py
"""
Vedic Astrology Engine
=======================

Complete Jyotish (Vedic) astrology calculation engine.
"""

from src.engines.core.ephemeris import HouseSystem

from src.engines.vedic.vedic_engine import (
    VedicEngine,
    VedicChart,
    BirthData,
    generate_vedic_chart,
)

from src.engines.vedic.vedic_constants import (
    Rashi,
    Nakshatra,
    VargaChart,
    Ayanamsa
)

from src.engines.vedic.rashi_nakshatra import (
    VedicMapping,
    RashiPosition,
    NakshatraPosition,
    DignityStatus,
    BhavaPlacement,
    LagnaData,
)

from src.engines.vedic.dasha_systems import (
    VimshottariDasha,
    DashaPeriod,
    DashaBalance,
    compute_vimshottari_dasha,
)

from src.engines.vedic.aspects_yogas import (
    AspectGrid,
    YogaAnalysis,
    YogaDetection,
    Aspect,
)

from src.engines.vedic.divisional_charts import (
    VargaPosition,
    AllVargaPositions,
    compute_varga_position,
    compute_all_vargas,
)

from src.engines.vedic.graha_stats import (
    AllGrahaStats,
    GrahaMotion,
    CombustionData,
    PlanetaryWar,
)

__all__ = [
    # Main Engine
    "VedicEngine",
    "VedicChart",
    "BirthData",
    "generate_vedic_chart",
    
    # Constants
    "Rashi",
    "Nakshatra",
    "VargaChart",
    "Ayanamsa",
    "HouseSystem",
    
    # Rashi & Nakshatra
    "VedicMapping",
    "RashiPosition",
    "NakshatraPosition",
    "DignityStatus",
    "BhavaPlacement",
    "LagnaData",
    
    # Dasha
    "VimshottariDasha",
    "DashaPeriod",
    "DashaBalance",
    "compute_vimshottari_dasha",
    
    # Aspects & Yogas
    "AspectGrid",
    "YogaAnalysis",
    "YogaDetection",
    "Aspect",
    
    # Divisional Charts
    "VargaPosition",
    "AllVargaPositions",
    "compute_varga_position",
    "compute_all_vargas",
    
    # Graha Stats
    "AllGrahaStats",
    "GrahaMotion",
    "CombustionData",
    "PlanetaryWar",
]