# Course Processing Overview

**Version**: 1.0
**Last Updated**: December 5, 2025

---

## Overview

This section documents the course content processing pipeline. Each course goes through a standardized flow: source material ingestion, concept extraction, atom generation, quality validation, and integration.

---

## Current Status

| Course | Status | Atoms | Notes |
|--------|--------|-------|-------|
| [CCNA ITN](ccna-itn.md) | **Complete** | 4,924 | Gold standard, fully synced |
| [CDS.Networking](cds-networking.md) | Queued | ~1,500 est. | CCNA overlap expected |
| [CDS.Security](cds-security.md) | Queued | ~2,000 est. | DevOps/Security focus |
| [PROGII](progii.md) | Queued | ~1,800 est. | Advanced programming |
| [SDE2](sde2.md) | Queued | ~2,500 est. | Full-stack development |
| [SDE2Testing](sde2-testing.md) | Queued | ~1,200 est. | Software testing |

---

## Processing Pipeline

```
Source Material (docs/source-materials/)
         |
         | 1. Parse & Extract
         v
+------------------+
| Concept Mapping  |  <- Link to existing or create new
+--------+---------+
         |
         | 2. Generate Atoms
         v
+------------------+
| Atom Generation  |  <- Gemini API (flashcard, cloze, mcq)
| (per concept)    |
+--------+---------+
         |
         | 3. Quality Check
         v
+------------------+
| 11-Point Rubric  |  <- Grade A/B threshold
+--------+---------+
         |
         | 4. Deduplication
         v
+------------------+
| Cross-Course     |  <- Similarity > 0.85 = review
| Duplicate Check  |
+--------+---------+
         |
         | 5. Integration
         v
+------------------+
| learning_atoms   |  <- Canonical table
| concepts         |
+------------------+
```

---

## Atom Distribution

After processing, atoms are routed based on type:

| Atom Type | Destination | Purpose |
|-----------|-------------|---------|
| `flashcard` | Anki | FSRS spaced repetition |
| `cloze` | Anki | Fill-in-the-blank review |
| `mcq` | NLS CLI | Multiple choice quizzes |
| `true_false` | NLS CLI | Binary answer quizzes |
| `parsons` | NLS CLI | Code ordering problems |
| `matching` | NLS CLI | Pair matching |

---

## Source Materials

Raw course content is stored in `docs/source-materials/`:

```
source-materials/
├── CCNA/           # 17 CCNA ITN modules (txt)
│   ├── CCNA Module 1.txt
│   ├── CCNA Module 2.txt
│   └── ... (Module 3-17)
│
└── EASV/           # EASV course exports
    ├── CDS.Networking.txt
    ├── CDS.Security.txt
    ├── PROGII.txt
    ├── SDE2.txt
    └── SDE2Testing.txt
```

---

## Processing Commands

### Generate Atoms for a Course

```bash
# CCNA module generation
python scripts/ccna_generate.py --modules 1,2,3

# All CCNA modules
python scripts/ccna_generate.py --all
```

### Check Generation Status

```bash
# View atom distribution
python scripts/anki_full_sync.py --summary

# Database stats
python -c "from src.db.database import engine; ..."
```

### Sync to Anki

```bash
# Push flashcard/cloze atoms to Anki
python scripts/anki_full_sync.py
```

---

## Quality Targets

| Metric | Target | Current (CCNA) |
|--------|--------|----------------|
| Grade A/B atoms | >= 90% | 97% |
| Atomicity pass rate | >= 95% | 99% |
| Concept coverage | 100% | 100% |
| Duplication rate | < 5% | 2% |

---

## Related Documentation

- [Future Course Processing](future-course-processing.md) - Detailed roadmap and timeline
- [Phase 4.6 CCNA Generation](../reference/phase-4.6-ccna-generation.md) - CCNA generation results
- [Cleaning Pipeline](../architecture/cleaning-pipeline.md) - Quality validation details
