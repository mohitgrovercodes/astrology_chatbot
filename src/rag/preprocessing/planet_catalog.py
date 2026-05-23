# src/rag/preprocessing/planet_catalog.py
# src\rag\preprocessing\planet_catalog.py
"""
Planet NER + canonicalization.

The corpus mixes English ("Sun", "Saturn") and Sanskrit ("Surya", "Shani")
planet names. The old enricher matched both into the entities list, but as
*separate* strings, so a filter like `planets="Saturn"` would skip every
chunk that only said "Shani". This module collapses every alias back to a
single English canonical (Sun / Moon / Mars / Mercury / Jupiter / Venus /
Saturn / Rahu / Ketu / Gulika / Mandi), with word-boundary regex matching
so that author names like "Suryanarain Rao" or words like "Mandakini" don't
get confused for the planet.

Some Sanskrit aliases are too ambiguous to use safely — "Manda" is also a
generic adjective ("slow"), and "Yama" is a death deity / sub-planet rather
than Saturn in most BPHS chapters. Those are deliberately omitted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Pattern, Set


@dataclass
class PlanetEntry:
    """One canonical planet + every safe surface form for it."""

    canonical: str            # English name written into metadata
    aliases: List[str]        # Surface forms to recognise, English + Sanskrit
    _compiled: List[Pattern] = field(default_factory=list, repr=False)

    def compile(self) -> None:
        """Build a word-boundary regex per alias, hyphen/space flexible."""
        compiled: List[Pattern] = []
        for alias in self.aliases:
            # Split on whitespace/hyphen so re.escape doesn't ossify the
            # separator. Joining with [\s\-]+ lets "Deva-Guru" == "Deva Guru".
            parts = [re.escape(p) for p in re.split(r"[\s\-]+", alias) if p]
            flexible = r"[\s\-]+".join(parts)
            compiled.append(re.compile(rf"\b{flexible}\b", re.IGNORECASE))
        self._compiled = compiled

    def search(self, text: str) -> bool:
        return any(p.search(text) for p in self._compiled)


# ---------------------------------------------------------------------------
# Catalog
#
# Conservative aliases only. Each is chosen so a `\b<alias>\b` match in the
# real corpus is overwhelmingly likely to refer to the planet, not to a
# similar-sounding common noun or proper name.
#
# Excluded by design (would cause false positives in this corpus):
#   - "Manda"   : Saturn alias but also adjective ("slow / dull")
#   - "Yama"    : a sub-planet / death deity in BPHS, not always Saturn
#   - "Saumya"  : means "benefic" generically, not only Mercury
# ---------------------------------------------------------------------------

_ENTRIES: List[PlanetEntry] = [
    PlanetEntry("Sun", [
        "Sun", "Surya", "Soorya", "Sūrya",
        "Ravi", "Aditya", "Āditya", "Bhanu", "Bhānu", "Arka",
    ]),
    PlanetEntry("Moon", [
        "Moon", "Chandra", "Chandrama", "Candra",
        "Soma", "Indu", "Shashi", "Shashanka", "Shashank",
    ]),
    PlanetEntry("Mars", [
        "Mars", "Mangal", "Mangala", "Mangaḷa",
        "Kuja", "Bhauma", "Bhaum", "Angaraka", "Angarak",
        "Kshitija", "Kshitisuta",
    ]),
    PlanetEntry("Mercury", [
        "Mercury", "Budh", "Budha", "Budhaḥ",
        "Soumya",  # rarer but unambiguous when spelled this way
    ]),
    PlanetEntry("Jupiter", [
        "Jupiter", "Guru", "Brihaspati", "Bṛhaspati", "Brhaspati",
        "Devaguru", "Deva Guru", "Deva-Guru",
    ]),
    PlanetEntry("Venus", [
        "Venus", "Shukra", "Sukra", "Śukra",
        "Bhargava", "Bhārgava", "Daityaguru", "Daitya Guru",
    ]),
    PlanetEntry("Saturn", [
        "Saturn", "Shani", "Sani", "Śani", "Shaani",
    ]),
    PlanetEntry("Rahu", [
        "Rahu", "Rāhu",
    ]),
    PlanetEntry("Ketu", [
        "Ketu", "Kethu", "Ketuḥ",
    ]),
    PlanetEntry("Gulika", [
        "Gulika", "Gulikā",
    ]),
    PlanetEntry("Mandi", [
        # Kept distinct from Gulika because BPHS (and Sharma's edition)
        # treat them as separate shadow points. If your tradition merges
        # them, switch the canonical to "Gulika" here.
        "Mandi", "Mānḍī",
    ]),
]


for _e in _ENTRIES:
    _e.compile()


# Fast pre-filter. Almost every astrology chunk contains at least one of
# these substrings; chunks that don't (e.g. pure Sanskrit shlokas with no
# transliteration) can safely skip the full regex sweep.
_FAST_TRIGGERS = (
    "sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn",
    "rahu", "ketu", "kethu", "gulika", "mandi",
    "surya", "chandra", "mangal", "kuja", "budh", "guru", "brihaspati",
    "shukra", "sukra", "shani", "sani", "ravi", "soma", "indu", "shashi",
    "aditya", "bhanu", "arka", "bhauma", "angarak", "bhargava",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_catalog() -> List[PlanetEntry]:
    """Return the compiled catalog (stable order, do not mutate)."""
    return _ENTRIES


def list_canonical_names() -> List[str]:
    """All canonical planet names."""
    return [e.canonical for e in _ENTRIES]


def extract_planets(text: str) -> List[str]:
    """
    Return the canonical names of every planet mentioned in `text`.

    Deduplicated and stable-ordered. Word-boundary regex matching keeps
    "Surya" from inflating on "Suryanarain", "Shashi" off "Shashira", and
    so on. Multiple aliases for the same planet collapse into one canonical.
    """
    if not text:
        return []

    text_lower = text.lower()
    if not any(tok in text_lower for tok in _FAST_TRIGGERS):
        # The triggers are ASCII; texts with diacritics (Mangaḷa, Bṛhaspati,
        # Śukra, etc.) may legitimately miss the prefilter. Only skip the
        # full scan when the text is pure ASCII — that covers ~95% of the
        # corpus and keeps the fast path cheap.
        if text.isascii():
            return []

    found: List[str] = []
    seen: Set[str] = set()
    for entry in _ENTRIES:
        if entry.canonical in seen:
            continue
        if entry.search(text):
            found.append(entry.canonical)
            seen.add(entry.canonical)
    return found


def canonicalize_planet_list(raw: List[str]) -> List[str]:
    """
    Given a list of arbitrary planet surface forms (from older metadata),
    return the deduplicated English canonicals. Unknown strings are dropped.

    Useful when migrating existing metadata that already contains Sanskrit
    names — pass the existing list through this instead of re-scanning text.
    """
    alias_to_canon: Dict[str, str] = {}
    for entry in _ENTRIES:
        for alias in entry.aliases:
            alias_to_canon[alias.lower()] = entry.canonical

    out: List[str] = []
    seen: Set[str] = set()
    for s in raw:
        canon = alias_to_canon.get((s or "").strip().lower())
        if canon and canon not in seen:
            out.append(canon)
            seen.add(canon)
    return out


__all__ = [
    "PlanetEntry",
    "get_catalog",
    "list_canonical_names",
    "extract_planets",
    "canonicalize_planet_list",
]
