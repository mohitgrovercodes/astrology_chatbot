# src/rag/preprocessing/yoga_catalog.py
# src\rag\preprocessing\yoga_catalog.py
"""
Vedic Yoga Catalog for Named-Entity Recognition

A curated list of yogas drawn from the corpus traditions (BPHS, Phaladeepika,
Saravali, Jataka Parijata, Uttarakalamritam, etc.). Each entry maps any of its
surface forms (case-insensitive, hyphen/space-flexible) back to a single
canonical name that is what we store in chunk metadata. This is what lets a
metadata filter `yogas=Gajakesari` match chunks that originally wrote
"Gaja-Kesari", "Gaja Kesari Yoga", or "Gajakesari yog".

False-positive guarding:
    Ambiguous Sanskrit single-words (e.g. Mala, Gada, Sakata) require an
    adjacent "Yoga"/"Yog"/"Yogas" token. Unambiguous proper names
    (Gajakesari, Kemadruma, Kalsarpa, etc.) match standalone.

This module is intentionally dependency-free so it can be unit-tested and
imported anywhere in the pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Pattern, Set


# ---------------------------------------------------------------------------
# Catalog entry
# ---------------------------------------------------------------------------

@dataclass
class YogaEntry:
    """One yoga + every surface form we want to recognise for it."""

    canonical: str                  # Name written to metadata.entities.yogas
    aliases: List[str]              # Latin-script surface forms (English + IAST)
    category: str                   # raja | dhana | pancha_mahapurusha | lunar |
                                    # solar | nabhasa | dosha | special | misc
    requires_qualifier: bool = False  # If True, " yoga" must appear after the name
    subsumes: List[str] = field(default_factory=list)
    # ^ canonicals to suppress from the final output when *this* one matches.
    #   Lets "Kala Sarpa" silence the generic "Sarpa Yoga" in the same text.
    devanagari_roots: List[str] = field(default_factory=list)
    # ^ Devanagari word stems. Same Unicode-range lookbehind trick as
    #   planet_catalog: a single root "पारिजात" catches all case-inflected
    #   forms (पारिजातं, पारिजाते, पारिजातस्थे, ...) but rejects
    #   "बहुपारिजात" (preceded by Devanagari). Only populated for yogas
    #   that actually appear in the corpus in Devanagari.
    _compiled: List[Pattern] = field(default_factory=list, repr=False)
    _compiled_dev: List[Pattern] = field(default_factory=list, repr=False)

    def compile(self) -> None:
        """Pre-compile every alias (Latin) and every Devanagari root."""
        # Latin / IAST path
        patterns: List[Pattern] = []
        for alias in self.aliases:
            parts = [re.escape(p) for p in re.split(r"[\s\-]+", alias) if p]
            flexible = r"[\s\-]+".join(parts)

            if self.requires_qualifier:
                pattern = rf"\b{flexible}[\s\-]+yog(?:a|as|am|āḥ|ah)?\b"
            else:
                pattern = rf"\b{flexible}(?:[\s\-]+yog(?:a|as|am|āḥ|ah)?)?\b"
            patterns.append(re.compile(pattern, re.IGNORECASE))
        self._compiled = patterns

        # Devanagari path. We don't enforce a trailing "yoga" requirement
        # here because Devanagari yoga compounds typically embed योग into
        # the root itself (राजयोग) — and Sanskrit case endings come after.
        patterns_dev: List[Pattern] = []
        for root in self.devanagari_roots:
            patterns_dev.append(
                re.compile(rf"(?<![ऀ-ॿ]){re.escape(root)}[ऀ-ॿ]*")
            )
        self._compiled_dev = patterns_dev

    def search(self, text: str) -> bool:
        if any(p.search(text) for p in self._compiled):
            return True
        if self._compiled_dev and any(p.search(text) for p in self._compiled_dev):
            return True
        return False


# ---------------------------------------------------------------------------
# The catalog
#
# Conventions:
#   - `canonical` is the stable spelling we store. Pick the one users are
#     most likely to type when filtering.
#   - `aliases` is everything else we observe in the books, including hyphen
#     variants. Word-boundary/hyphen-flexibility is handled in compile().
#   - Order does not matter for matching, but keeping similar yogas together
#     makes the catalog easier to maintain.
# ---------------------------------------------------------------------------

_ENTRIES: List[YogaEntry] = [

    # -----------------------------------------------------------------
    # Pancha Mahapurusha Yogas (the "five great person" yogas)
    # Each formed when a specific planet sits in own/exalted sign in kendra
    # -----------------------------------------------------------------
    YogaEntry("Ruchaka",  ["Ruchaka", "Rucaka"],                          "pancha_mahapurusha",
              devanagari_roots=["रुचक"]),
    YogaEntry("Bhadra",   ["Bhadra"],                                     "pancha_mahapurusha",
              devanagari_roots=["भद्रयोग"]),  # bare भद्र is too generic
    YogaEntry("Hamsa",    ["Hamsa", "Hansa"],                             "pancha_mahapurusha",
              devanagari_roots=["हंसयोग", "हंसयोगः"]),  # bare हंस means swan
    YogaEntry("Malavya",  ["Malavya", "Malavaya", "Maalavya"],            "pancha_mahapurusha",
              devanagari_roots=["मालव्य"]),
    YogaEntry("Shasha",   ["Shasha", "Sasa", "Sasha"],                    "pancha_mahapurusha",
              devanagari_roots=["शशयोग"]),  # bare शश = hare
    YogaEntry("Pancha Mahapurusha", ["Pancha Mahapurusha", "Panch Mahapurusha", "Mahapurusha"],
                                                                          "pancha_mahapurusha",
              devanagari_roots=["पञ्चमहापुरुष", "पंचमहापुरुष", "महापुरुष"]),

    # -----------------------------------------------------------------
    # Raja yogas (power/authority)
    # -----------------------------------------------------------------
    YogaEntry("Raja Yoga",            ["Raja"],                            "raja", requires_qualifier=True,
              devanagari_roots=["राजयोग"]),
    YogaEntry("Kendra Trikona",       ["Kendra Trikona", "Kendra-Kona", "Trikona Kendra"],
                                                                            "raja"),
    YogaEntry("Viparita Raja Yoga",   ["Viparita Raja", "Vipreet Raja",
                                       "Vipareet Raja", "Viparita Raj",
                                       "Vipareeta Raja"],                   "raja",
              subsumes=["Raja Yoga"]),
    YogaEntry("Harsha",               ["Harsha"],                           "raja"),
    YogaEntry("Sarala",               ["Sarala"],                           "raja"),
    YogaEntry("Vimala",               ["Vimala"],                           "raja"),
    YogaEntry("Neecha Bhanga Raja Yoga",
                                      ["Neecha Bhanga Raja", "Neechabhanga Raja",
                                       "Neecha-Bhanga Raja"],               "raja",
              subsumes=["Raja Yoga", "Neecha Bhanga"]),
    YogaEntry("Neecha Bhanga",        ["Neecha Bhanga", "Neechabhanga",
                                       "Neecha-Bhanga"],                    "raja",
              devanagari_roots=["नीचभंग", "नीचभङ्ग"]),
    YogaEntry("Dharma Karmadhipati",  ["Dharma Karmadhipati", "Dharma-Karmadhipati",
                                       "Dharmakarmadhipati"],               "raja"),

    # -----------------------------------------------------------------
    # Dhana yogas (wealth)
    # -----------------------------------------------------------------
    YogaEntry("Dhana Yoga",           ["Dhana"],                            "dhana", requires_qualifier=True,
              devanagari_roots=["धनयोग"]),
    YogaEntry("Lakshmi",              ["Lakshmi", "Laxmi"],                 "dhana", requires_qualifier=True),
    YogaEntry("Kubera",               ["Kubera"],                           "dhana", requires_qualifier=True),
    YogaEntry("Chandra Mangal",       ["Chandra Mangal", "Chandra-Mangal",
                                       "Chandra Mangala"],                  "dhana"),
    YogaEntry("Vasumati",             ["Vasumati", "Vasumathi"],            "dhana"),
    YogaEntry("Daridra",              ["Daridra"],                          "dhana", requires_qualifier=True),

    # -----------------------------------------------------------------
    # Lunar yogas (relative to Moon)
    # -----------------------------------------------------------------
    YogaEntry("Gajakesari",           ["Gajakesari", "Gaja Kesari",
                                       "Gaja-Kesari", "Gajakeshari"],       "lunar",
              devanagari_roots=["गजकेसरी", "गजकेसरि"]),
    YogaEntry("Anapha",               ["Anapha", "Anaphaa"],                "lunar",
              devanagari_roots=["अनफा", "अनाफा"]),
    YogaEntry("Sunapha",              ["Sunapha", "Sunaphaa"],              "lunar",
              devanagari_roots=["सुनफा", "सुनाफा"]),
    YogaEntry("Durudhura",            ["Durudhura", "Durdhura", "Durdhara",
                                       "Duradhara"],                        "lunar",
              devanagari_roots=["दुरुधर", "दुरुधरा", "दुरधरा"]),
    YogaEntry("Kemadruma",            ["Kemadruma", "Kema Druma",
                                       "Kemadrum"],                         "lunar",
              devanagari_roots=["केमद्रुम"]),
    YogaEntry("Adhi Yoga",            ["Adhi"],                             "lunar", requires_qualifier=True),
    YogaEntry("Shakata",              ["Shakata", "Sakata", "Shakat"],      "lunar", requires_qualifier=True),

    # -----------------------------------------------------------------
    # Solar yogas (relative to Sun)
    # -----------------------------------------------------------------
    YogaEntry("Vesi",                 ["Vesi", "Veshi"],                    "solar", requires_qualifier=True),
    YogaEntry("Vasi",                 ["Vasi", "Vaasi"],                    "solar", requires_qualifier=True),
    YogaEntry("Ubhayachari",          ["Ubhayachari", "Ubhayachara",
                                       "Ubhayachaari"],                     "solar"),
    YogaEntry("Budha Aditya",         ["Budha Aditya", "Budh Aditya",
                                       "Budha-Aditya", "Budhaditya",
                                       "Nipuna"],                           "solar"),

    # -----------------------------------------------------------------
    # Nabhasa yogas (planetary distribution patterns)
    # -----------------------------------------------------------------
    YogaEntry("Nabhasa",              ["Nabhasa", "Nabhas"],                "nabhasa"),
    YogaEntry("Rajju",                ["Rajju"],                            "nabhasa", requires_qualifier=True),
    YogaEntry("Musala",               ["Musala", "Musal"],                  "nabhasa", requires_qualifier=True),
    YogaEntry("Nala",                 ["Nala"],                             "nabhasa", requires_qualifier=True),
    YogaEntry("Mala Yoga",            ["Mala", "Srak"],                     "nabhasa", requires_qualifier=True),
    YogaEntry("Sarpa Yoga",           ["Sarpa"],                            "nabhasa", requires_qualifier=True),
    YogaEntry("Gada",                 ["Gada"],                             "nabhasa", requires_qualifier=True),
    YogaEntry("Shakti",               ["Shakti", "Sakti"],                  "nabhasa", requires_qualifier=True),
    YogaEntry("Vihaga",               ["Vihaga", "Vihag"],                  "nabhasa", requires_qualifier=True),
    YogaEntry("Vajra",                ["Vajra"],                            "nabhasa", requires_qualifier=True),
    YogaEntry("Yava",                 ["Yava"],                             "nabhasa", requires_qualifier=True),
    YogaEntry("Kamala",               ["Kamala"],                           "nabhasa", requires_qualifier=True),
    YogaEntry("Vapi",                 ["Vapi"],                             "nabhasa", requires_qualifier=True),
    YogaEntry("Yupa",                 ["Yupa", "Yoopa"],                    "nabhasa", requires_qualifier=True),
    YogaEntry("Shara",                ["Shara"],                            "nabhasa", requires_qualifier=True),
    YogaEntry("Pasha",                ["Pasha", "Pasa"],                    "nabhasa", requires_qualifier=True),
    YogaEntry("Damini",               ["Damini", "Dama"],                   "nabhasa", requires_qualifier=True),
    YogaEntry("Vallaki",              ["Vallaki", "Veena", "Vina"],         "nabhasa", requires_qualifier=True),
    YogaEntry("Kedara",               ["Kedara", "Kedar"],                  "nabhasa", requires_qualifier=True),
    YogaEntry("Shoola",               ["Shoola", "Shula", "Sula"],          "nabhasa", requires_qualifier=True),
    YogaEntry("Yuga",                 ["Yuga"],                             "nabhasa", requires_qualifier=True),
    YogaEntry("Gola",                 ["Gola"],                             "nabhasa", requires_qualifier=True),

    # -----------------------------------------------------------------
    # Inauspicious / dosha yogas
    # -----------------------------------------------------------------
    YogaEntry("Kala Sarpa",           ["Kala Sarpa", "Kaal Sarpa",
                                       "Kalsarpa", "Kala-Sarpa",
                                       "Kalasarpa", "Kalsarp"],             "dosha",
              subsumes=["Sarpa Yoga"],
              devanagari_roots=["कालसर्प", "कालसर्पयोग"]),
    YogaEntry("Kala Amrita",          ["Kala Amrita", "Kala-Amrita",
                                       "Kalamrita"],                        "dosha"),
    YogaEntry("Guru Chandala",        ["Guru Chandala", "Guru-Chandala",
                                       "Guruchandala"],                     "dosha"),
    YogaEntry("Angaraka",             ["Angaraka", "Angarak", "Angara"],    "dosha", requires_qualifier=True),
    YogaEntry("Visha",                ["Visha", "Vish"],                    "dosha", requires_qualifier=True),
    YogaEntry("Punarphoo",            ["Punarphoo", "Punarfoo",
                                       "Punarphu", "Punarvasu Dosha"],      "dosha"),
    YogaEntry("Mangal Dosha",         ["Mangal Dosha", "Mangalik",
                                       "Manglik", "Mangaldosha",
                                       "Kuja Dosha", "Kuja-Dosha",
                                       "Mars Dosha"],                       "dosha",
              devanagari_roots=["मंगलदोष", "कुजदोष", "मांगलिक"]),
    YogaEntry("Pitra Dosha",          ["Pitra Dosha", "Pitru Dosha",
                                       "Pitri Dosha", "Pitra-Dosha"],       "dosha"),
    YogaEntry("Grahan",               ["Grahan", "Grahana"],                "dosha", requires_qualifier=True),
    YogaEntry("Sade Sati",            ["Sade Sati", "Sade-Sati", "Sadesati",
                                       "Sade Saati"],                       "dosha"),
    YogaEntry("Kemadruma Dosha",      ["Kemadruma Dosha"],                  "dosha",
              subsumes=["Kemadruma"]),

    # -----------------------------------------------------------------
    # Exchange (Parivartana) yogas
    # -----------------------------------------------------------------
    YogaEntry("Parivartana",          ["Parivartana", "Parivartan",
                                       "Parivartha"],                       "parivartana", requires_qualifier=True),
    YogaEntry("Maha Parivartana",     ["Maha Parivartana", "Maha-Parivartana",
                                       "Mahaparivartana"],                  "parivartana",
              subsumes=["Parivartana"]),
    YogaEntry("Khala Parivartana",    ["Khala Parivartana", "Khala-Parivartana"],
                                                                            "parivartana",
              subsumes=["Parivartana"]),
    YogaEntry("Dainya Parivartana",   ["Dainya Parivartana", "Dainya-Parivartana"],
                                                                            "parivartana",
              subsumes=["Parivartana"]),

    # -----------------------------------------------------------------
    # Special / classical "named" yogas
    # -----------------------------------------------------------------
    YogaEntry("Saraswati",            ["Saraswati", "Sarasvati"],           "special"),
    YogaEntry("Sarada",               ["Sarada", "Saarada"],                "special", requires_qualifier=True),
    YogaEntry("Parijata",             ["Parijata", "Paarijata"],            "special",
              devanagari_roots=["पारिजात"]),
    YogaEntry("Pushkala",             ["Pushkala", "Pushkal"],              "special"),
    YogaEntry("Sankha",               ["Sankha", "Shankha"],                "special", requires_qualifier=True),
    YogaEntry("Bheri",                ["Bheri"],                            "special", requires_qualifier=True),
    YogaEntry("Mridanga",             ["Mridanga", "Mrudanga"],             "special", requires_qualifier=True),
    YogaEntry("Sreenatha",            ["Sreenatha", "Srinatha",
                                       "Shreenatha"],                       "special"),
    YogaEntry("Trilochana",           ["Trilochana", "Trilochan"],          "special"),
    YogaEntry("Bhaskara",             ["Bhaskara", "Bhaskar"],              "special", requires_qualifier=True),
    YogaEntry("Marud",                ["Marud", "Marut"],                   "special", requires_qualifier=True),
    YogaEntry("Kahala",               ["Kahala", "Kahal"],                  "special", requires_qualifier=True),
    YogaEntry("Gauri",                ["Gauri"],                            "special", requires_qualifier=True),
    YogaEntry("Indra",                ["Indra"],                            "special", requires_qualifier=True),
    YogaEntry("Ravi",                 ["Ravi"],                             "special", requires_qualifier=True),
    YogaEntry("Akriti",               ["Akriti", "Akruti"],                 "special"),
    YogaEntry("Pravrajya",            ["Pravrajya", "Pravrajyaa"],          "special"),
    YogaEntry("Sanyasa",              ["Sanyasa", "Sannyasa", "Sanyaas"],   "special"),
    YogaEntry("Sasi Mangala",         ["Sasi Mangala", "Sasi-Mangala",
                                       "Shashi Mangala"],                   "special"),

    # -----------------------------------------------------------------
    # Health/longevity yogas (broad categories)
    # -----------------------------------------------------------------
    YogaEntry("Balarishta",           ["Balarishta", "Bala Arishta",
                                       "Balaarishta"],                      "arishta"),
    YogaEntry("Arishta",              ["Arishta", "Arista"],                "arishta", requires_qualifier=True),
    YogaEntry("Maraka",               ["Maraka", "Marak"],                  "arishta", requires_qualifier=True),
    YogaEntry("Alpayu",               ["Alpayu", "Alpaayu"],                "arishta"),
    YogaEntry("Madhyayu",             ["Madhyayu", "Madhyaayu"],            "arishta"),
    YogaEntry("Purnayu",              ["Purnayu", "Poornayu", "Poorna Ayu"], "arishta"),
]


# Compile all patterns once at import time.
for _e in _ENTRIES:
    _e.compile()


# Cheap substring pre-filter. If none of these tokens appear in the lowercased
# text, the full catalog scan cannot match anything, so we skip it. This is
# the hot-path optimisation that lets us backfill the whole corpus in seconds
# instead of minutes — astrology books have many pages that discuss houses,
# planets and dashas without ever naming a yoga.
_FAST_TRIGGERS = (
    "yog",          # yoga / yog / yogas / Yogasya
    "dosh",         # Mangal Dosha / Pitra Dosha / Kuja Dosha
    "manglik",
    "sade",         # Sade Sati / Sade-Sati
    "kala",         # Kala Sarpa / Kala Amrita
    "kalsarp",
    "neech",        # Neecha Bhanga
    "parivartan",
    "mahapurush",
    "balarisht",
    "arisht",
    "alpayu",
    "madhyayu",
    "purnay",
    "poornay",
    "pravraj",
    "sanyas",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_catalog() -> List[YogaEntry]:
    """Return the live (compiled) catalog. Stable order, do not mutate."""
    return _ENTRIES


def list_canonical_names() -> List[str]:
    """All canonical yoga names known to the catalog."""
    return [e.canonical for e in _ENTRIES]


def extract_yogas(text: str) -> List[str]:
    """
    Return the canonical names of every yoga mentioned in `text`.

    The result is deduplicated and stable-ordered (catalog order). Matching is
    case-insensitive and tolerates hyphen/space variants in the alias; generic
    Sanskrit single-words (Mala, Gada, Vajra, ...) are only matched when an
    adjacent "Yoga"/"Yog"/"Yogas" token is present, to keep false positives
    down on a corpus that uses these words in non-yoga senses too.

    When a more specific yoga matches, the canonicals listed in its `subsumes`
    field are removed from the output, e.g. "Kala Sarpa" silences the generic
    "Sarpa Yoga" rather than recording both.
    """
    if not text:
        return []

    # Fast prefilter: if no Latin yoga trigger appears at all, fall back to
    # the full catalog scan only when the text contains Devanagari (the
    # Latin triggers can't fire on pure Sanskrit chunks). Pure-ASCII chunks
    # with zero triggers are safe to skip entirely.
    text_lower = text.lower()
    if not any(tok in text_lower for tok in _FAST_TRIGGERS):
        if text.isascii():
            return []

    matched: List[str] = []
    seen: Set[str] = set()
    subsumed: Set[str] = set()
    for entry in _ENTRIES:
        if entry.canonical in seen:
            continue
        if entry.search(text):
            matched.append(entry.canonical)
            seen.add(entry.canonical)
            subsumed.update(entry.subsumes)

    return [name for name in matched if name not in subsumed]


def extract_yogas_with_categories(text: str) -> Dict[str, List[str]]:
    """
    Same as `extract_yogas` but groups results by category. Useful for stats
    and for downstream filters that want e.g. "any raja yoga". Honors the
    `subsumes` field, so generic names are dropped when a more specific one
    matched.
    """
    out: Dict[str, List[str]] = {}
    if not text:
        return out
    keep = set(extract_yogas(text))
    for entry in _ENTRIES:
        if entry.canonical in keep:
            out.setdefault(entry.category, []).append(entry.canonical)
    return out


__all__ = [
    "YogaEntry",
    "get_catalog",
    "list_canonical_names",
    "extract_yogas",
    "extract_yogas_with_categories",
]


def extract_yogas_with_categories(text: str) -> Dict[str, List[str]]:
    """
    Same as `extract_yogas` but groups results by category. Useful for stats
    and for downstream filters that want e.g. "any raja yoga". Honors the
    `subsumes` field, so generic names are dropped when a more specific one
    matched.
    """
    out: Dict[str, List[str]] = {}
    if not text:
        return out
    keep = set(extract_yogas(text))
    for entry in _ENTRIES:
        if entry.canonical in keep:
            out.setdefault(entry.category, []).append(entry.canonical)
    return out


__all__ = [
    "YogaEntry",
    "get_catalog",
    "list_canonical_names",
    "extract_yogas",
    "extract_yogas_with_categories",
]
ns Devanagari (the
    # Latin triggers can't fire on pure Sanskrit chunks). Pure-ASCII chunks
    # with zero triggers are safe to skip entirely.
    text_lower = text.lower()
    if not any(tok in text_lower for tok in _FAST_TRIGGERS):
        if text.isascii():
            return []

    matched: List[str] = []
    seen: Set[str] = set()
    subsumed: Set[str] = set()
    for entry in _ENTRIES:
        if entry.canonical in seen:
            continue
        if entry.search(text):
            matched.append(entry.canonical)
            seen.add(entry.canonical)
            subsumed.update(entry.subsumes)

    return [name for name in matched if name not in subsumed]


def extract_yogas_with_categories(text: str) -> Dict[str, List[str]]:
    """
    Same as `extract_yogas` but groups results by category. Useful for stats
    and for downstream filters that want e.g. "any raja yoga". Honors the
    `subsumes` field, so generic names are dropped when a more specific one
    matched.
    """
    out: Dict[str, List[str]] = {}
    if not text:
        return out
    keep = set(extract_yogas(text))
    for entry in _ENTRIES:
        if entry.canonical in keep:
            out.setdefault(entry.category, []).append(entry.canonical)
    return out


__all__ = [
    "YogaEntry",
    "get_catalog",
    "list_canonical_names",
    "extract_yogas",
    "extract_yogas_with_categories",
]
