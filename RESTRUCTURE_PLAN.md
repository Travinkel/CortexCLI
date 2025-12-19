# Package-by-Feature Restructure Plan

## Overview

This plan consolidates the fragmented Anki code and restructures the codebase following **package-by-feature** principles. The goal is to have each feature be a vertically-sliced package containing everything it needs.

## Current Problems

1. **Anki code in 3 places**: `src/anki/`, `scripts/anki/`, `scripts/archive/anki/`
2. **3 different push implementations** with different feature sets
3. **Missing features in refactored code**: tags, cloze routing, 6-field metadata
4. **Duplicate atom handling**: `src/cortex/atoms/` vs `src/study/quiz_engine.py`

## Current Structure Analysis

The codebase already has a pattern emerging:

```
src/
├── cortex/                     # NEW: Study session runner
│   ├── session.py              # Main study session logic
│   ├── session_store.py        # Session persistence
│   └── atoms/                  # Modular atom type handlers
│       ├── base.py             # AtomHandler protocol
│       ├── flashcard.py        # Flashcard handler
│       ├── cloze.py            # Cloze handler (→ Anki)
│       ├── mcq.py              # MCQ handler (→ CLI only)
│       ├── true_false.py       # T/F handler (→ CLI only)
│       ├── matching.py         # Matching handler (→ CLI only)
│       ├── parsons.py          # Parsons handler (→ CLI only)
│       └── numeric.py          # Numeric handler (→ CLI only)
│
├── delivery/                   # Presentation layer
│   ├── atom_deck.py            # Atom loading
│   ├── scheduler.py            # SM2/FSRS scheduling
│   ├── state_store.py          # SQLite state persistence
│   ├── cortex_visuals.py       # TUI rendering
│   ├── tutor.py                # LLM tutoring
│   └── telemetry.py            # Session tracking
│
├── study/                      # OLDER: Study services (being superseded by cortex/)
│   ├── quiz_engine.py          # Monolithic quiz engine (→ use cortex/atoms/ instead)
│   ├── mastery_calculator.py
│   ├── interleaver.py
│   ├── retention_engine.py
│   └── study_service.py
│
├── anki/                       # Anki integration (FRAGMENTED)
│   ├── anki_client.py          # HTTP wrapper - GOOD
│   ├── import_service.py       # Import from Anki - GOOD
│   └── push_service.py         # Push to Anki - BROKEN (missing features)
```

## Key Insight

**`src/cortex/`** is the new study system with modular atom handlers.
**`src/study/`** contains older services, some superseded by cortex.
**`src/anki/`** should be the external integration, not duplicated elsewhere.

## Target Structure

Keep Anki as a separate integration package, but fix and consolidate it:

```
src/
├── cortex/                     # Study session (KEEP AS-IS)
│   ├── session.py
│   ├── session_store.py
│   └── atoms/                  # Modular handlers (KEEP AS-IS)
│
├── delivery/                   # Presentation layer (KEEP AS-IS)
│
├── study/                      # Study services
│   ├── mastery_calculator.py   # KEEP
│   ├── interleaver.py          # KEEP
│   ├── retention_engine.py     # KEEP
│   ├── study_service.py        # KEEP
│   ├── pomodoro_engine.py      # KEEP
│   └── quiz_engine.py          # DEPRECATE (use cortex/atoms/ instead)
│
├── anki/                       # Anki integration (CONSOLIDATE)
│   ├── __init__.py
│   ├── client.py               # ← renamed from anki_client.py
│   ├── sync_service.py         # ← merged push + pull + all features
│   ├── import_service.py       # KEEP
│   └── config.py               # NEW: note types, deck names, tags
│
├── content/                    # Content creation (NEW PACKAGE)
│   ├── cleaning/               # ← from src/cleaning/
│   └── generation/             # ← from src/generation/
│
├── quiz/                       # Quiz pool management (KEEP SEPARATE)
│   ├── pool_manager.py
│   └── quality_analyzer.py
│
├── ccna/                       # CCNA curriculum (KEEP AS-IS)
├── db/                         # Database (KEEP AS-IS)
├── api/                        # API routing (KEEP AS-IS)
└── cli/                        # CLI routing (KEEP AS-IS)

scripts/
├── archive/
│   └── anki/                   # ← ALL scripts/anki/*.py moved here
└── ...
```

## Migration Phases

### Phase 1: Archive Legacy Scripts (5 min) - DONE

**Goal**: Clean up scripts/ without affecting src/

```bash
# Delete obsolete archive files
rm scripts/archive/anki/fast_anki_push.py
rm scripts/archive/anki/complete_anki_push.py

# Move legacy scripts to archive (keep as reference)
mv scripts/anki/* scripts/archive/anki/
rmdir scripts/anki
```

### Phase 2: Create Anki Config Module (15 min) - DONE

**Goal**: Centralize Anki configuration in one place

**New file**: `src/anki/config.py`

```python
"""Anki configuration constants and note type definitions."""

# Note types - must match your Anki note type names exactly
FLASHCARD_NOTE_TYPE = "LearningOS-v2"
CLOZE_NOTE_TYPE = "LearningOS-v2 Cloze"

# Deck structure
CERT_DECK = "CCNA"
COURSE_DECK = "ITN"
BASE_DECK = f"{CERT_DECK}::{COURSE_DECK}"

# Curriculum identifier for globally unique tags
CURRICULUM_ID = "ccna-itn"

# Atom types that go to Anki (others stay in NLS for CLI quizzes)
ANKI_ATOM_TYPES = ("flashcard", "cloze")

# CCNA ITN Module names for deck organization
CCNA_ITN_MODULE_NAMES = {
    1: "Networking Today",
    2: "Basic Switch and End Device Configuration",
    3: "Protocols and Models",
    4: "Physical Layer",
    5: "Number Systems",
    6: "Data Link Layer",
    7: "Ethernet Switching",
    8: "Network Layer",
    9: "Address Resolution",
    10: "Basic Router Configuration",
    11: "IPv4 Addressing",
    12: "IPv6 Addressing",
    13: "ICMP",
    14: "Transport Layer",
    15: "Application Layer",
    16: "Network Security Fundamentals",
    17: "Build a Small Network",
}


def get_note_type(atom_type: str) -> str:
    """Get Anki note type for atom type."""
    return CLOZE_NOTE_TYPE if atom_type == "cloze" else FLASHCARD_NOTE_TYPE


def get_module_deck_name(module_num: int) -> str:
    """Get full deck path for module number."""
    name = CCNA_ITN_MODULE_NAMES.get(module_num, f"Module {module_num}")
    return f"{BASE_DECK}::M{module_num:02d} {name}"
```

### Phase 3: Fix Push Service (30 min) - DONE

**Goal**: Fix the immediate bugs (missing tags, wrong note types)

**File**: `src/anki/push_service.py`

Changes needed:
1. Import from new config module
2. Fix `_build_tags()` to generate proper tags
3. Fix note type routing for cloze
4. Add atom type filtering
5. Add 6-field metadata_json support

See implementation details below.

### Phase 4: Add Pull Service (1 hour) - DONE

**Goal**: Port pull functionality from `scripts/archive/anki/anki_full_sync.py`

**New file**: `src/anki/pull_service.py`

```python
"""Pull FSRS stats from Anki into PostgreSQL."""

def pull_review_stats(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Pull FSRS stats FROM Anki INTO PostgreSQL."""
    ...
```

### Phase 5: Create Content Package (30 min) - DONE

**Goal**: Group cleaning + generation under content/

```bash
mkdir -p src/content
mv src/cleaning src/content/cleaning
mv src/generation src/content/generation
touch src/content/__init__.py
```

Update imports in:
- `src/api/routers/cleaning_router.py`
- `src/ccna/*.py`
- Any scripts using cleaning/generation

### Phase 6: Deprecate quiz_engine.py (15 min)

**Goal**: Mark `src/study/quiz_engine.py` as deprecated

Add deprecation notice pointing to `src/cortex/atoms/` handlers.
Don't delete yet - just document that cortex/atoms/ is the new way.

### Phase 7: Update Documentation (30 min)

- Update `docs/architecture/overview.md`
- Update this plan with "DONE" markers

## Testing Strategy

After each phase:
1. Run `pytest tests/` to verify no breaks
2. Run `ruff check src/` for import errors
3. Run `mypy src/` for type errors
4. Manual test: `python -m src.cli.main --help`

## Rollback Plan

Each phase creates commits that can be reverted:
```bash
git revert <phase-commit>
```

Keep the old `scripts/archive/anki/` as reference implementations.

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Anki under `study/` | Anki is a delivery mechanism for the Study feature, not a feature itself |
| Quiz under `study/` | Quiz is part of the study/review workflow |
| Cleaning under `content/` | Quality analysis is part of content creation |
| Keep `db/` separate | Database models are shared across all features |
| Keep `api/` and `cli/` | These are thin routing layers, not features |

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Archive scripts | 5 min | Low |
| Phase 2: Fix push bugs | 30 min | Low |
| Phase 3: Create config | 15 min | Low |
| Phase 4: Consolidate sync | 1 hour | Medium |
| Phase 5: Move files | 30 min | Medium |
| Phase 6: Update imports | 1-2 hours | High |
| Phase 7: Cleanup | 5 min | Low |
| Phase 8: Docs | 30 min | Low |

**Total**: ~4-5 hours

## Next Steps

1. Review this plan
2. Decide if we want to do all phases or stop at Phase 4 (consolidated sync)
3. Start with Phase 1 (no-risk archive)
