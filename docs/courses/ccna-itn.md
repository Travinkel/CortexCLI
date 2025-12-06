# CCNA ITN - Introduction to Networks

**Status**: Complete
**Last Updated**: December 5, 2025

---

## Overview

CCNA Introduction to Networks (ITN) is the first of three courses in the Cisco CCNA certification path. This is the **gold standard** course for the NLS system - fully processed with hardcoded module names and complete Anki integration.

---

## Statistics

| Metric | Value |
|--------|-------|
| Total Atoms | 4,924 |
| Flashcards | 3,408 |
| Cloze | 945 |
| MCQ | 533 |
| Parsons | 38 |
| Anki Synced | 4,238 notes |
| Quality Grade A/B | 97% |

---

## Module Structure

| Module | Name | Atoms |
|--------|------|-------|
| M01 | Networking Today | ~290 |
| M02 | Basic Switch and End Device Configuration | ~285 |
| M03 | Protocols and Models | ~310 |
| M04 | Physical Layer | ~295 |
| M05 | Number Systems | ~180 |
| M06 | Data Link Layer | ~320 |
| M07 | Ethernet Switching | ~285 |
| M08 | Network Layer | ~340 |
| M09 | Address Resolution | ~275 |
| M10 | Basic Router Configuration | ~290 |
| M11 | IPv4 Addressing | ~395 |
| M12 | IPv6 Addressing | ~350 |
| M13 | ICMP | ~280 |
| M14 | Transport Layer | ~310 |
| M15 | Application Layer | ~295 |
| M16 | Network Security Fundamentals | ~305 |
| M17 | Build a Small Network | ~120 |

---

## Anki Deck Structure

```
CCNA
└── ITN
    ├── M01 Networking Today
    ├── M02 Basic Switch and End Device Configuration
    ├── M03 Protocols and Models
    ├── M04 Physical Layer
    ├── M05 Number Systems
    ├── M06 Data Link Layer
    ├── M07 Ethernet Switching
    ├── M08 Network Layer
    ├── M09 Address Resolution
    ├── M10 Basic Router Configuration
    ├── M11 IPv4 Addressing
    ├── M12 IPv6 Addressing
    ├── M13 ICMP
    ├── M14 Transport Layer
    ├── M15 Application Layer
    ├── M16 Network Security Fundamentals
    └── M17 Build a Small Network
```

---

## Source Materials

Located in `docs/source-materials/CCNA/`:

- `CCNA Module 1.txt` through `CCNA Module 17.txt`
- Exported from Cisco NetAcad curriculum
- Contains section headers, learning objectives, and content

---

## Generation Details

### Script

```bash
python scripts/ccna_generate.py --all
```

### Hardcoded Module Names

Module names are hardcoded in `scripts/anki_full_sync.py` for consistency:

```python
CCNA_ITN_MODULE_NAMES = {
    1: "Networking Today",
    2: "Basic Switch and End Device Configuration",
    3: "Protocols and Models",
    # ... etc
}
```

### Quality Filters

Atoms pass through quality filters before Anki sync:

- Quality score >= 0.5
- Front length >= 20 characters
- Back length >= 5 characters
- Excludes malformed patterns

---

## Tags

Each Anki note includes tags:

```
ccna-itn           # Curriculum root
ccna-itn:m{N}      # Module (e.g., ccna-itn:m1)
type:{type}        # Atom type (flashcard, cloze)
concept:{slug}     # Concept slug (if linked)
```

---

## Related Documentation

- [Course Processing Overview](index.md)
- [Anki Integration](../features/anki-integration.md)
- [Phase 4.6 Generation Results](../reference/phase-4.6-ccna-generation.md)
