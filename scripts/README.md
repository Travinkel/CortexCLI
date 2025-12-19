# Scripts Directory

Utility scripts organized by function.

## Directory Structure

```
scripts/
├── atoms/      # Atom generation and regeneration
├── anki/       # Anki synchronization and management
├── analysis/   # Quality audits and progress reports
├── setup/      # Database population and linking
└── legacy/     # Deprecated utilities (for reference)
```

## atoms/ - Atom Generation

| Script | Purpose |
|--------|---------|
| `generate_all_atoms.py` | Full atom generation from CCNA content |
| `ccna_generate.py` | CCNA-specific generation pipeline |
| `batch_regenerate.py` | Regenerate atoms in batches |
| `regenerate_atoms_gemini.py` | Use Gemini for atom regeneration |
| `regenerate_mcqs.py` | Regenerate MCQ-type atoms |
| `rebalance_tf.py` | Rebalance True/False answer distribution |
| `compute_optimal_atoms.py` | Calculate optimal atom counts per section |

## anki/ - Anki Integration

| Script | Purpose |
|--------|---------|
| `anki_full_sync.py` | Full bidirectional Anki sync |
| `anki_pull_reviews.py` | Pull FSRS review data from Anki |
| `check_anki_types.py` | Verify Anki card types |
| `find_byod_cards.py` | Find user-created cards |
| `fix_cloze_template.py` | Repair cloze deletion templates |

## analysis/ - Quality & Progress

| Script | Purpose |
|--------|---------|
| `quality_audit.py` | Full quality audit of all atoms |
| `ccna_assessment.py` | CCNA mastery assessment |
| `reading_progress.py` | Track reading/review progress |
| `analyze_atom_quality.py` | Atom quality metrics |
| `audit_flashcard_quality.py` | Flashcard-specific quality check |
| `audit_tf_quality.py` | True/False quality validation |

## setup/ - Database Setup

| Script | Purpose |
|--------|---------|
| `hydrate_db.py` | Populate database from source content |
| `populate_ccna_sections.py` | Create CCNA section hierarchy |
| `populate_prerequisites.py` | Set up prerequisite relationships |
| `link_atoms_to_sections.py` | Link atoms to their sections |
| `fix_atom_section_links.py` | Repair broken section links |

## Usage

Most scripts can be run directly:

```bash
# Generate atoms
python scripts/atoms/generate_all_atoms.py --module 5

# Sync with Anki
python scripts/anki/anki_full_sync.py

# Run quality audit
python scripts/analysis/quality_audit.py

# Setup database
python scripts/setup/hydrate_db.py
```

## Environment

Scripts require:
- PostgreSQL connection (via `DATABASE_URL`)
- Gemini API key (for generation scripts)
- Anki running with AnkiConnect (for sync scripts)
