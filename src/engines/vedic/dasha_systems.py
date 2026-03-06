# src/engines/vedic/dasha_systems.py
# src\engines\vedic\dasha_systems.py
"""
Layer 3B: Dasha Systems (Planetary Period Calculations)
========================================================

Dashas are the predictive timing system unique to Vedic astrology. They 
divide life into periods ruled by different planets. The Vimshottari Dasha
(120-year cycle) is the most widely used.

How Dasha Works:
---------------
1. The starting point is determined by the Moon's Nakshatra at birth
2. Each Nakshatra has a planetary lord in a fixed sequence
3. The balance of the first Dasha is calculated based on how much of
   the Nakshatra the Moon has traversed
4. From there, Mahadashas (main periods) follow in fixed sequence

The hierarchy of periods:
- Mahadasha: Main period (6-20 years depending on planet)
- Antardasha (Bhukti): Sub-period within Mahadasha
- Pratyantardasha: Sub-sub-period
- Sookshma: Sub-sub-sub-period (rarely used)

This module computes timeline facts only - not interpretation.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.engines.core.celestial_bodies import CelestialBody
from src.engines.vedic.vedic_constants import (
    Nakshatra, NAKSHATRA_LORDS, NAKSHATRA_SPAN,
    VIMSHOTTARI_PERIODS, VIMSHOTTARI_SEQUENCE, VIMSHOTTARI_TOTAL_YEARS,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class DashaPeriod:
    """
    Represents a single Dasha period (Maha, Antar, or Pratyanta).

    Attributes:
        lord: The planet ruling this period
        start_date: When this period begins
        end_date: When this period ends
        duration_years: Length of period in years
        level: "mahadasha", "antardasha", or "pratyantardasha"
        parent_lord: The lord of the parent period (None for Mahadasha).
            Stored as a lightweight CelestialBody rather than a full
            DashaPeriod reference to avoid circular serialization issues.
    """
    lord: CelestialBody
    start_date: datetime
    end_date: datetime
    duration_years: float
    level: str
    parent_lord: Optional[CelestialBody] = None
    
    @property
    def duration_days(self) -> float:
        """Duration in days."""
        return (self.end_date - self.start_date).days
    
    def is_active(self, date: datetime) -> bool:
        """Check if this period is active at a given date."""
        return self.start_date <= date < self.end_date
    
    def format_period(self) -> str:
        """Format as 'Sun-Moon-Mars' etc."""
        from src.engines.core.celestial_bodies import get_planet_info
        name = get_planet_info(self.lord).sanskrit_name
        return name


@dataclass
class DashaBalance:
    """
    Balance of the first Mahadasha at birth.
    
    Calculated from Moon's position within its birth Nakshatra.
    """
    first_lord: CelestialBody
    elapsed_years: float    # How much has already passed
    remaining_years: float  # How much remains from birth
    total_years: float      # Full Mahadasha length
    
    @property
    def elapsed_percentage(self) -> float:
        """Percentage of first Dasha already elapsed at birth."""
        return (self.elapsed_years / self.total_years) * 100


@dataclass
class VimshottariDasha:
    """
    Complete Vimshottari Dasha timeline for a chart.
    
    Contains all Mahadashas from birth to 120 years.
    """
    birth_date: datetime
    moon_nakshatra: Nakshatra
    moon_longitude: float
    dasha_balance: DashaBalance
    mahadashas: List[DashaPeriod]
    
    def get_current_mahadasha(self, date: datetime) -> Optional[DashaPeriod]:
        """Get the Mahadasha active at a specific date."""
        for md in self.mahadashas:
            if md.is_active(date):
                return md
        return None
    
    def get_antardashas(self, mahadasha: DashaPeriod) -> List[DashaPeriod]:
        """Calculate Antardashas within a Mahadasha."""
        return compute_antardashas(mahadasha)
    
    def get_current_periods(self, date: datetime) -> Dict[str, DashaPeriod]:
        """Get all active periods (Maha, Antar, Pratyantar) at a date."""
        result = {}
        
        md = self.get_current_mahadasha(date)
        if md:
            result["mahadasha"] = md
            
            antardashas = self.get_antardashas(md)
            for ad in antardashas:
                if ad.is_active(date):
                    result["antardasha"] = ad
                    
                    pratyantar = compute_pratyantardashas(ad)
                    for pd in pratyantar:
                        if pd.is_active(date):
                            result["pratyantardasha"] = pd
                            break
                    break
        
        return result


# =============================================================================
# VIMSHOTTARI DASHA CALCULATIONS
# =============================================================================

def compute_dasha_balance(
    moon_longitude: float,
    birth_date: datetime
) -> DashaBalance:
    """
    Calculate the balance of the first Mahadasha at birth.
    
    This is determined by how far the Moon has traveled through its
    birth Nakshatra. If the Moon is at the start of the Nakshatra,
    almost the full Mahadasha remains. If at the end, very little remains.
    
    Args:
        moon_longitude: Moon's sidereal longitude at birth
        birth_date: Birth date and time
        
    Returns:
        DashaBalance with first Dasha details
    """
    # Determine Moon's Nakshatra
    nakshatra_index = int(moon_longitude / NAKSHATRA_SPAN) % 27
    nakshatra = Nakshatra(nakshatra_index)
    
    # Get the lord of this Nakshatra
    first_lord = NAKSHATRA_LORDS[nakshatra_index]
    
    # How far through the Nakshatra is the Moon?
    nakshatra_start = nakshatra_index * NAKSHATRA_SPAN
    traversed = moon_longitude - nakshatra_start
    traversed_fraction = traversed / NAKSHATRA_SPAN
    
    # Get the total period for this lord
    total_years = VIMSHOTTARI_PERIODS[first_lord]
    
    # Calculate elapsed and remaining portions
    elapsed_years = traversed_fraction * total_years
    remaining_years = total_years - elapsed_years
    
    return DashaBalance(
        first_lord=first_lord,
        elapsed_years=elapsed_years,
        remaining_years=remaining_years,
        total_years=total_years
    )


def compute_mahadashas(
    birth_date: datetime,
    dasha_balance: DashaBalance,
    num_cycles: int = 1
) -> List[DashaPeriod]:
    """
    Compute the sequence of Mahadashas from birth.
    
    Args:
        birth_date: Birth date and time
        dasha_balance: Balance of first Mahadasha
        num_cycles: Number of 120-year cycles (default: 1)
        
    Returns:
        List of DashaPeriod objects for all Mahadashas
    """
    mahadashas = []
    current_date = birth_date
    
    # Find starting position in the sequence
    first_lord = dasha_balance.first_lord
    start_index = VIMSHOTTARI_SEQUENCE.index(first_lord)
    
    # Total periods to calculate
    total_periods = 9 * num_cycles
    
    for i in range(total_periods):
        # Get the lord for this period
        sequence_index = (start_index + i) % 9
        lord = VIMSHOTTARI_SEQUENCE[sequence_index]
        total_period = VIMSHOTTARI_PERIODS[lord]
        
        # First period uses the balance
        if i == 0:
            years = dasha_balance.remaining_years
        else:
            years = total_period
        
        # Calculate end date
        days = years * 365.25
        end_date = current_date + timedelta(days=days)
        
        mahadashas.append(DashaPeriod(
            lord=lord,
            start_date=current_date,
            end_date=end_date,
            duration_years=years,
            level="mahadasha",
            parent_lord=None
        ))
        
        current_date = end_date
    
    return mahadashas


def compute_antardashas(mahadasha: DashaPeriod) -> List[DashaPeriod]:
    """
    Compute Antardashas (sub-periods) within a Mahadasha.
    
    The sequence of Antardashas starts from the Mahadasha lord itself,
    then follows the Vimshottari sequence.
    
    Args:
        mahadasha: The parent Mahadasha period
        
    Returns:
        List of DashaPeriod objects for all Antardashas
    """
    antardashas = []
    current_date = mahadasha.start_date
    
    # Find starting position (Antardasha starts from Mahadasha lord)
    md_lord = mahadasha.lord
    start_index = VIMSHOTTARI_SEQUENCE.index(md_lord)
    
    # Calculate proportion factor
    md_total = VIMSHOTTARI_PERIODS[md_lord]
    
    for i in range(9):
        sequence_index = (start_index + i) % 9
        ad_lord = VIMSHOTTARI_SEQUENCE[sequence_index]
        ad_total = VIMSHOTTARI_PERIODS[ad_lord]
        
        # Antardasha duration = (AD lord years * MD lord years) / 120
        proportion = (ad_total * md_total) / VIMSHOTTARI_TOTAL_YEARS
        
        # Actual duration is this proportion of the actual Mahadasha duration
        actual_years = proportion * (mahadasha.duration_years / md_total)
        
        days = actual_years * 365.25
        end_date = current_date + timedelta(days=days)
        
        antardashas.append(DashaPeriod(
            lord=ad_lord,
            start_date=current_date,
            end_date=end_date,
            duration_years=actual_years,
            level="antardasha",
            parent_lord=mahadasha.lord
        ))
        
        current_date = end_date
    
    return antardashas


def compute_pratyantardashas(antardasha: DashaPeriod) -> List[DashaPeriod]:
    """
    Compute Pratyantardashas (sub-sub-periods) within an Antardasha.
    
    Same logic as Antardashas, but one level deeper.
    
    Args:
        antardasha: The parent Antardasha period
        
    Returns:
        List of DashaPeriod objects for all Pratyantardashas
    """
    pratyantars = []
    current_date = antardasha.start_date
    
    ad_lord = antardasha.lord
    start_index = VIMSHOTTARI_SEQUENCE.index(ad_lord)
    ad_total = VIMSHOTTARI_PERIODS[ad_lord]
    
    for i in range(9):
        sequence_index = (start_index + i) % 9
        pd_lord = VIMSHOTTARI_SEQUENCE[sequence_index]
        pd_total = VIMSHOTTARI_PERIODS[pd_lord]
        
        # Same proportion logic
        proportion = (pd_total * ad_total) / VIMSHOTTARI_TOTAL_YEARS
        actual_years = proportion * (antardasha.duration_years / ad_total)
        
        days = actual_years * 365.25
        end_date = current_date + timedelta(days=days)
        
        pratyantars.append(DashaPeriod(
            lord=pd_lord,
            start_date=current_date,
            end_date=end_date,
            duration_years=actual_years,
            level="pratyantardasha",
            parent_lord=antardasha.lord
        ))
        
        current_date = end_date
    
    return pratyantars


def compute_vimshottari_dasha(
    birth_date: datetime,
    moon_longitude: float
) -> VimshottariDasha:
    """
    Compute the complete Vimshottari Dasha timeline.
    
    This is the main entry point for Dasha calculations.
    
    Args:
        birth_date: Birth date and time
        moon_longitude: Moon's sidereal longitude at birth
        
    Returns:
        VimshottariDasha with complete timeline
        
    Example:
        >>> from datetime import datetime
        >>> birth = datetime(1990, 3, 15, 15, 30)
        >>> moon_long = 45.5  # Moon at 15Â°30' Taurus (Rohini)
        >>> dasha = compute_vimshottari_dasha(birth, moon_long)
        >>> print(f"First Dasha: {dasha.dasha_balance.first_lord.name}")
        >>> print(f"Balance: {dasha.dasha_balance.remaining_years:.2f} years")
    """
    # Get Moon's Nakshatra
    nakshatra_index = int(moon_longitude / NAKSHATRA_SPAN) % 27
    moon_nakshatra = Nakshatra(nakshatra_index)
    
    # Calculate balance
    balance = compute_dasha_balance(moon_longitude, birth_date)
    
    # Compute all Mahadashas
    mahadashas = compute_mahadashas(birth_date, balance)
    
    return VimshottariDasha(
        birth_date=birth_date,
        moon_nakshatra=moon_nakshatra,
        moon_longitude=moon_longitude,
        dasha_balance=balance,
        mahadashas=mahadashas
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def find_dasha_at_date(
    dasha: VimshottariDasha,
    target_date: datetime
) -> Dict[str, DashaPeriod]:
    """
    Find all active Dasha periods at a specific date.
    
    Args:
        dasha: The VimshottariDasha object
        target_date: Date to check
        
    Returns:
        Dictionary with "mahadasha", "antardasha", "pratyantardasha" keys
    """
    return dasha.get_current_periods(target_date)


def format_dasha_string(periods: Dict[str, DashaPeriod]) -> str:
    """
    Format current Dasha periods as a string like "Sun-Moon-Mars".
    
    Args:
        periods: Dictionary from get_current_periods()
        
    Returns:
        Formatted string
    """
    from src.engines.core.celestial_bodies import get_planet_info
    
    parts = []
    for level in ["mahadasha", "antardasha", "pratyantardasha"]:
        if level in periods:
            name = get_planet_info(periods[level].lord).sanskrit_name
            parts.append(name)
    
    return "-".join(parts)