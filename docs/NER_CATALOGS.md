# NER Catalogs — Planets & Yogas

> **Module reference for `src/rag/preprocessing/planet_catalog.py` and `yoga_catalog.py`.**
> These are the structured, dependency-free named-entity recognisers that populate `metadata.entities.planets` and `metadata.entities.yogas` on every chunk in `data/raw/*.json` and (after ingestion) in the ChromaDB collection. The metadata is what downstream filters like `planets=Saturn` rely on.

---

## Why these catalogs exist

The corpus is multilingual and inflected:

- **English** (`Saturn`, `Moon`, `Mars`).
- **Latin transliteration / IAST** (`Sūrya`, `Śani`, `Bṛhaspati`, `Mangaḷa`).
- **Devanagari** in three flavours — bare roots (`सूर्य`), case-inflected forms (`सूर्यस्य`, `शनेः`), and compounds (`सूर्यवर्गस्थ`, `राजयोगकारकः`).

The original enricher used a substring match against a flat alias list. Two failure modes followed: (a) chunks that wrote `Shani` and chunks that wrote `Saturn` were tagged as *different* strings, so a filter like `planets="Saturn"` skipped half the corpus; (b) author names like `Suryanarain Rao` matched the alias `Surya` and produced false-positive `Sun` tags. The catalogs fix both by mapping every alias back to a single English canonical *and* by using word-boundary regex matching.

---

## Catalog shape

Both catalogs share the same dataclass pattern:

```python
@dataclass
class PlanetEntry / YogaEntry:
    canonical: str                  # English name written to metadata
    aliases: List[str]              # Latin-script surface forms (English + IAST)
    devanagari_roots: List[str]     # Devanagari word stems (optional)
    # YogaEntry only:
    category: str                   # raja | dhana | dosha | nabhasa | ...
    requires_qualifier: bool        # If True, ' yoga' must follow
    subsumes: List[str]             # Canonicals to suppress when this one matches
```

Each entry is `compile()`-d once at module load. `search(text)` runs both the Latin regexes and the Devanagari regexes in turn.

### Latin / IAST path

```python
re.compile(rf"\b{flexible_alias}\b", re.IGNORECASE)
```

Hyphen and whitespace inside aliases are flexible — `Deva-Guru`, `Deva Guru`, `DevaGuru` all match the same pattern via `[\s\-]+`. The `\b` boundary is what stops `Surya` firing inside `Suryanarain`.

### Devanagari path

Python's `\b` does not work in pure Devanagari text — every Devanagari character is a "non-word" character under the default regex word-character set, so the boundary never triggers between two of them. Instead each Devanagari root compiles to:

```python
re.compile(rf"(?<![ऀ-ॿ]){re.escape(root)}[ऀ-ॿ]*")
```

- The Unicode-range lookbehind `(?<![ऀ-ॿ])` enforces a left word boundary — the match must be preceded by a non-Devanagari character (space, punctuation, Latin) or the start of the string.
- The trailing `[ऀ-ॿ]*` greedily accepts any Sanskrit case ending, so a single root `सूर्य` matches every inflected form: `सूर्य`, `सूर्यः`, `सूर्यस्य`, `सूर्यवर्गस्थ`, …
- `बहुसूर्य` is correctly rejected (the `ह` before `सूर्य` is Devanagari, so the lookbehind fails).

---

## Planet catalog

11 canonicals, listed in stable display order:

| Canonical | Latin aliases (sample) | Devanagari roots |
|---|---|---|
| **Sun** | Sun, Surya, Soorya, Sūrya, Ravi, Aditya, Bhanu, Arka | सूर्य, रवि, आदित्य, भानु, अर्क |
| **Moon** | Moon, Chandra, Candra, Soma, Indu, Shashi, Shashanka | चन्द्र, चंद्र, सोम, शशि, इन्दु, इंदु |
| **Mars** | Mars, Mangal, Mangaḷa, Kuja, Bhauma, Angaraka, Kshitija | मंगल, मङ्गल, कुज, भौम, अंगारक, अङ्गारक |
| **Mercury** | Mercury, Budh, Budha, Budhaḥ, Soumya | बुध |
| **Jupiter** | Jupiter, Guru, Brihaspati, Bṛhaspati, Devaguru | बृहस्पति, देवगुरु |
| **Venus** | Venus, Shukra, Sukra, Śukra, Bhargava, Daityaguru | शुक्र, भार्गव, दैत्यगुरु |
| **Saturn** | Saturn, Shani, Sani, Śani | शनि, शनैश्चर |
| **Rahu** | Rahu, Rāhu | राहु |
| **Ketu** | Ketu, Kethu, Ketuḥ | केतु |
| **Gulika** | Gulika, Gulikā | गुलिक |
| **Mandi** | Mandi, Mānḍī | मान्दि, माण्डि |

### Deliberately excluded

Some aliases are *too* ambiguous for safe substring NER and were left out by design:

- `Manda` — Saturn alias, also a generic adjective ("slow / dull").
- `Yama` — death deity / sub-planet in BPHS, not always Saturn.
- `Saumya` — means "benefic" generically, not only Mercury.
- bare Devanagari `गुरु` — too often means "teacher" / "heavy" in non-astrology contexts. We require `बृहस्पति` / `देवगुरु` for unambiguous Jupiter mentions.

---

## Yoga catalog

94 canonical yogas across 9 categories:

| Category | Examples |
|---|---|
| `pancha_mahapurusha` | Ruchaka, Bhadra, Hamsa, Malavya, Shasha |
| `raja` | Raja Yoga, Viparita Raja Yoga, Neecha Bhanga, Dharma-Karmadhipati |
| `dhana` | Dhana Yoga, Lakshmi, Chandra-Mangal, Vasumati |
| `lunar` | Gajakesari, Anapha, Sunapha, Durudhura, Kemadruma |
| `solar` | Vesi, Vasi, Ubhayachari, Budha-Aditya |
| `nabhasa` | 21 distributional patterns (Rajju, Musala, Nala, Mala, Sarpa, …) |
| `dosha` | Kala Sarpa, Mangal Dosha (Manglik / Kuja Dosha), Pitra Dosha, Sade Sati |
| `parivartana` | Parivartana, Maha-, Khala-, Dainya- |
| `special` | Saraswati, Parijata, Pushkala, Sankha, Bheri |

### Two precision tricks

1. **`requires_qualifier=True`** for ambiguous Sanskrit single-words (`Raja`, `Dhana`, `Mala`, `Gada`, `Sakata`, …). The compiled regex demands an adjacent `yog(a|as|am|āḥ|ah)` token before recording a hit, so `Raja Yoga is formed when…` matches but a stray `raja` in an unrelated sentence does not.
2. **`subsumes`** for hierarchical names. When `Kala Sarpa` matches, generic `Sarpa Yoga` is dropped from the output rather than recorded alongside. When `Viparita Raja Yoga` matches, plain `Raja Yoga` is dropped. Lets us keep both names in the catalog without polluting the metadata.

### Devanagari-extended yogas

15 high-volume yogas have Devanagari roots populated (chosen by counting Devanagari occurrences across the corpus):

| Canonical | Devanagari root(s) |
|---|---|
| Parijata | पारिजात |
| Raja Yoga | राजयोग |
| Pancha Mahapurusha | पञ्चमहापुरुष, पंचमहापुरुष, महापुरुष |
| Ruchaka / Bhadra / Hamsa / Malavya / Shasha | रुचक, भद्रयोग, हंसयोग, मालव्य, शशयोग |
| Gajakesari | गजकेसरी, गजकेसरि |
| Anapha / Sunapha / Durudhura / Kemadruma | अनफा, सुनफा, दुरुधर, केमद्रुम |
| Dhana Yoga | धनयोग |
| Kala Sarpa | कालसर्प, कालसर्पयोग |
| Mangal Dosha | मंगलदोष, कुजदोष, मांगलिक |
| Neecha Bhanga | नीचभंग, नीचभङ्ग |

For the rare nabhasa yogas and the long tail of special yogas, the Devanagari forms barely appear in the corpus — adding them would inflate the catalog without measurable recall gain.

---

## Public API

Both modules export the same shape:

```python
from planet_catalog import extract_planets, canonicalize_planet_list
from yoga_catalog import extract_yogas, extract_yogas_with_categories

# Word-boundary aware extraction
extract_planets("शनिः शनैश्चरः जातकः")   # → ['Saturn']
extract_planets("Surya in 7th house")    # → ['Sun']
extract_planets("Suryanarain Rao")       # → []   (author name, not the planet)

# Canonicalisation of mixed-script lists already on disk
canonicalize_planet_list(["Sani", "Shani", "शनि", "Saturn"])  # → ['Saturn']

# Subsumption-aware yoga extraction
extract_yogas("Viparita Raja Yoga formed in this chart")
# → ['Viparita Raja Yoga']    (plain 'Raja Yoga' is suppressed)

extract_yogas_with_categories("Kala Sarpa and Gajakesari Yoga")
# → {'dosha': ['Kala Sarpa'], 'lunar': ['Gajakesari']}
```

---

## How to extend the catalog

Adding a new planet alias or yoga is a three-step loop. Re-embedding the corpus is **not** required for metadata-only changes.

1. **Edit the catalog** — add the alias to the relevant `aliases=[…]` or `devanagari_roots=[…]` list in `planet_catalog.py` / `yoga_catalog.py`.
2. **Backfill the JSONs** — re-run the on-disk pass so every enriched JSON's `metadata.entities` reflects the new alias. The scripts are idempotent and report set/clear/unchanged counts.
   ```bash
   python scripts/backfill_planets.py     # writes updated *.json in place
   python scripts/backfill_yogas.py
   ```
3. **Push to ChromaDB** — metadata-only update, no re-embedding. Existing metadata fields are preserved.
   ```bash
   python scripts/update_chroma_planets.py
   python scripts/update_chroma_yogas.py
   ```

The Chroma update scripts post-verify by sampling 20 chunks and comparing on-disk vs in-DB values. Run them after every catalog change.

---

## Current corpus coverage

After the latest backfill (Devanagari aliases included, Phaladeepika duplicate removed):

| Metric | Value |
|---|---|
| Total chunks | 14,475 |
| Chunks with `planets` set | 7,918 (54.7%) |
| Chunks with `yogas` set | 708 (4.9%) |
| Distinct canonical planets | 11 / 11 |
| Distinct canonical yogas | 76 / 94 |

The yoga coverage is intentionally narrow — yogas are named combinations, not every chunk discusses one. The planet coverage is broad because almost every astrology paragraph names at least one planet.

Per-book and per-entity counts are persisted in `data/raw/planet_backfill_report.json` and `data/raw/yoga_backfill_report.json`.
