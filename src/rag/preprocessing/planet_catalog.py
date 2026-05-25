# src/rag/preprocessing/planet_catalog.py
# src\rag\preprocessing\planet_catalog.py
"""
Planet NER + canonicalization.

The corpus mixes English ("Sun", "Saturn"), IAST ("Sūrya", "Śani"), and
Devanagari ("सूर्य", "शनि"). The old enricher matched the Latin forms into
the entities list as *separate* strings, so a filter like `planets="Saturn"`
would skip every chunk that only said "Shani". And the Devanagari-only
books (e.g. Varahmihira Horasastram Vol 1) were missed entirely because
\\b<alias>\\b cannot match in pure Devanagari text — every character is a
"non-word" character in Python's default regex word-boundary definition.

This module collapses every alias back to a single English canonical
(Sun / Moon / Mars / Mercury / Jupiter / Venus / Saturn / Rahu / Ketu /
Gulika / Mandi) using two complementary scanners:

  * Latin scanner — `\\b<alias>\\b`, hyphen/space-flexible, case-insensitive.
  * Devanagari scanner — Unicode-range lookbehind + trailing-Devanagari
    suffix, so a single root "सूर्य" matches सूर्य, सूर्यः, सूर्यस्य,
    सूर्यवर्गस्थ, ... but rejects बहुसूर्य (preceded by Devanagari).

Some Sanskrit aliases are too ambiguous to use safely — "Manda" is also a
generic adjective ("slow"), "Yama" is a death deity / sub-planet rather
than Saturn in most BPHS chapters, and bare "गुरु" means "teacher" / "heavy"
as often as it means Jupiter. Those are deliberately omitted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Pattern, Set


@dataclass
class PlanetEntry:
    """One canonical planet + every safe surface form for it."""

    canonical: str
    aliases: List[str]
    devanagari_roots: List[str] = field(default_factory=list)
    _compiled: List[Pattern] = field(default_factory=list, repr=False)
    _compiled_dev: List[Pattern] = field(default_factory=list, repr=False)

    def compile(self) -> None:
        compiled: List[Pattern] = []
        for alias in self.aliases:
            parts = [re.escape(p) for p in re.split(r"[\s\-]+", alias) if p]
            flexible = r"[\s\-]+".join(parts)
            compiled.append(re.compile(rf"\b{flexible}\b", re.IGNORECASE))
        self._compiled = compiled

        compiled_dev: List[Pattern] = []
        for root in self.devanagari_roots:
            compiled_dev.append(
                re.compile(rf"(?<![ऀ-ॿ]){re.escape(root)}[ऀ-ॿ]*")
            )
        self._compiled_dev = compiled_dev

    def search(self, text: str) -> bool:
        if any(p.search(text) for p in self._compiled):
            return True
        if self._compiled_dev and any(p.search(text) for p in self._compiled_dev):
            return True
        return False


_ENTRIES: List[PlanetEntry] = [
    PlanetEntry(
        "Sun",
        aliases=["Sun", "Surya", "Soorya", "Sūrya", "Ravi", "Aditya", "Āditya", "Bhanu", "Bhānu", "Arka"],
        devanagari_roots=["सूर्य", "रवि", "आदित्य", "भानु", "अर्क"],
    ),
    PlanetEntry(
        "Moon",
        aliases=["Moon", "Chandra", "Chandrama", "Candra", "Soma", "Indu", "Shashi", "Shashanka", "Shashank"],
        devanagari_roots=["चन्द्र", "चंद्र", "सोम", "शशि", "इन्दु", "इंदु"],
    ),
    PlanetEntry(
        "Mars",
        aliases=["Mars", "Mangal", "Mangala", "Mangaḷa", "Kuja", "Bhauma", "Bhaum", "Angaraka", "Angarak", "Kshitija", "Kshitisuta"],
        devanagari_roots=["मंगल", "मङ्गल", "कुज", "भौम", "अंगारक", "अङ्गारक"],
    ),
    PlanetEntry(
        "Mercury",
        aliases=["Mercury", "Budh", "Budha", "Budhaḥ", "Soumya"],
        devanagari_roots=["बुध"],
    ),
    PlanetEntry(
        "Jupiter",
        aliases=["Jupiter", "Guru", "Brihaspati", "Bṛhaspati", "Brhaspati", "Devaguru", "Deva Guru", "Deva-Guru"],
        devanagari_roots=["बृहस्पति", "देवगुरु"],
    ),
    PlanetEntry(
        "Venus",
        aliases=["Venus", "Shukra", "Sukra", "Śukra", "Bhargava", "Bhārgava", "Daityaguru", "Daitya Guru"],
        devanagari_roots=["शुक्र", "भार्गव", "दैत्यगुरु"],
    ),
    PlanetEntry(
        "Saturn",
        aliases=["Saturn", "Shani", "Sani", "Śani", "Shaani"],
        devanagari_roots=["शनि", "शनैश्चर"],
    ),
    PlanetEntry(
        "Rahu",
        aliases=["Rahu", "Rāhu"],
        devanagari_roots=["राहु"],
    ),
    PlanetEntry(
        "Ketu",
        aliases=["Ketu", "Kethu", "Ketuḥ"],
        devanagari_roots=["केतु"],
    ),
    PlanetEntry(
        "Gulika",
        aliases=["Gulika", "Gulikā"],
        devanagari_roots=["गुलिक"],
    ),
    PlanetEntry(
        "Mandi",
        aliases=["Mandi", "Mānḍī"],
        devanagari_roots=["मान्दि", "माण्डि"],
    ),
]


for _e in _ENTRIES:
    _e.compile()


_FAST_TRIGGERS = (
    "sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn",
    "rahu", "ketu", "kethu", "gulika", "mandi",
    "surya", "chandra", "mangal", "kuja", "budh", "guru", "brihaspati",
    "shukra", "sukra", "shani", "sani", "ravi", "soma", "indu", "shashi",
    "aditya", "bhanu", "arka", "bhauma", "angarak", "bhargava",
)


def get_catalog() -> List[PlanetEntry]:
    return _ENTRIES


def list_canonical_names() -> List[str]:
    return [e.canonical for e in _ENTRIES]


def extract_planets(text: str) -> List[str]:
    """
    Return the canonical names of every planet mentioned in `text`.
    Devanagari-only text bypasses the fast prefilter (triggers are Latin).
    """
    if not text:
        return []

    text_lower = text.lower()
    if not any(tok in text_lower for tok in _FAST_TRIGGERS):
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
    Given arbitrary planet surface forms (Latin or Devanagari), return the
    deduplicated English canonicals. Unknown strings are dropped.
    """
    alias_to_canon: Dict[str, str] = {}
    for entry in _ENTRIES:
        for alias in entry.aliases:
            alias_to_canon[alias.lower()] = entry.canonical
        for root in entry.devanagari_roots:
            alias_to_canon[root] = entry.canonical

    out: List[str] = []
    seen: Set[str] = set()
    for s in raw:
        key = (s or "").strip()
        canon = alias_to_canon.get(key.lower()) or alias_to_canon.get(key)
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
