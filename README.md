# notion-learning-sync

CCNA Learning Path CLI - A comprehensive study system combining Anki spaced repetition with in-app interactive quizzes.

## Architecture

```
+-----------------------------------------------------------------------+
|                          ANKI (External)                               |
|  Handles: flashcard + cloze (6,014 cards)                             |
|  FSRS scheduling, spaced repetition                                    |
+-----------------------------------------------------------------------+
                              ^
                              | Sync (pull FSRS stats, push new cards)
                              v
+-----------------------------------------------------------------------+
|                       NLS Interactive CLI                              |
|  Handles: MCQ, True/False, Matching, Parsons (5,508 questions)        |
|  In-app quizzes, Pomodoro sessions, progress tracking                 |
+-----------------------------------------------------------------------+
```

## Features

- **11,500+ Learning Atoms** - Distributed across two systems:
  - **Anki**: 6,014 flashcards + cloze (FSRS scheduling)
  - **NLS**: 5,508 MCQ, T/F, matching, parsons (in-app quizzes)
- **530 Curriculum Sections** - Complete CCNA ITN coverage
- **Mastery Tracking** - FSRS for Anki cards, streak-based for quizzes
- **Pomodoro Sessions** - Interleaved Anki reviews + in-app quizzes
- **CLI Study Commands** - Daily planning, progress tracking, remediation

## Quick Start

### 1. Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Anki with AnkiConnect plugin (optional, for sync)

### 2. Installation

```bash
cd notion-learning-sync

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Create PostgreSQL database
createdb notion_learning_sync

# Or on Windows with psql:
psql -U postgres -c "CREATE DATABASE notion_learning_sync;"
```

### 4. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required settings in `.env`:
```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/notion_learning_sync
NOTION_API_KEY=your_notion_api_key  # Optional if not syncing from Notion
```

### 5. Run Migrations

```bash
# Run all database migrations
python -m src.cli.main db migrate

# Or run specific migration:
python -m src.cli.main db migrate --migration 008
```

### 6. Populate CCNA Sections

```bash
# Extract sections from CCNA module files
python scripts/populate_ccna_sections.py
```

### 7. Generate Learning Atoms

```bash
# Generate all 11,500+ atoms (dry-run first)
python scripts/generate_all_atoms.py --all --dry-run

# Actually save to database
python scripts/generate_all_atoms.py --all
```

### 8. Start Studying!

```bash
# Launch interactive CLI (recommended)
python -m src.cli.main

# Or use the batch file (Windows)
nls.bat
```

This launches an **interactive session** with:
- Continuous Anki sync (every 60 seconds)
- Dynamic learning job generation
- Session planning for variable study hours

---

## Interactive CLI

Launch with `python -m src.cli.main` or `nls.bat`:

```
+------------------------------------ NLS ------------------------------------+
| CCNA Learning Path                                                          |
| Interactive Study Session                                                   |
+-----------------------------------------------------------------------------+

[nls] > help

In-App Quizzes (MCQ, T/F, Matching, Parsons):
  quiz [n] [type]  - Start a quiz (e.g., quiz 10 mcq)
  mcq [n]          - Quick MCQ quiz
  tf [n]           - Quick True/False quiz
  matching [n]     - Quick Matching quiz
  parsons [n]      - Quick Parsons ordering quiz
  session [hrs]    - Full Pomodoro session (Anki + quizzes)

Anki Integration (flashcard + cloze only):
  sync        - Sync FSRS stats from Anki
  jobs        - Generate filtered deck queries for Anki
  plan <hrs>  - Plan a study session with time breakdown

Progress Tracking:
  today       - Today's study session summary
  path        - Full learning path with progress
  module <n>  - Detailed view of module n (1-16)
  stats       - Comprehensive statistics
  remediation - Sections needing remediation
```

### Example Session

```bash
[nls] > plan 8

Study Plan: 8 hours
==================================================

Time Breakdown:
  Total time: 8 hours (480 minutes)
  Pomodoro sessions: 16 x 25 min
  Break time: 80 min total

Card Targets:
  Due reviews first: ~200 cards
  New content: ~160 cards
  Remediation interleaved: ~80 cards

[nls] > jobs

Generated Learning Jobs:

# | Job                  | Type        | Cards | Priority | Query
--|----------------------|-------------|-------|----------|------------------
1 | Stability Repair     | weakness    | 40    | HIGH     | (rated:7:1 OR ...)
2 | Due Reviews          | maintenance | 50    | HIGH     | is:due
3 | New Content          | acquisition | 30    | MEDIUM   | is:new tag:ccna
4 | Apply-Level Practice | application | 20    | MEDIUM   | (tag:bloom:apply...)
5 | Concept Integration  | integration | 25    | LOW      | tag:module:3
```

## Filtered Decks Philosophy

**Filtered decks are ephemeral jobs, NOT permanent structure.**

```
WRONG: Using filtered decks as categories
  - CCNA-Module-1 (filtered)
  - React-Hooks (filtered)
  - etc.

RIGHT: Using filtered decks as dynamic queries
  - Stability Repair Session (temp)
  - Bloom Apply Practice (temp)
  - Exam Cram Week 38 (temp)
```

The `jobs` command generates these queries automatically based on:
- FSRS stability curves
- Prerequisite dependencies
- Cognitive load balancing
- Mastery map state

### Standard Filtered Deck Queries

| Purpose | Anki Query |
|---------|------------|
| Weakest 40 | `prop:due is:review rated:30:1` |
| Due Today | `prop:due<=0` |
| New Learning | `is:new` |
| High Lapses | `prop:lapses>2` |
| Bloom Apply | `tag:bloom:apply OR tag:mcq` |
| Module Focus | `tag:module:N` |
| Stability <7 | `prop:ivl<7` |

**Always delete filtered decks after use!**

---

## CCNA Content Structure

The system covers all 16 modules of CCNA ITN:

| Module | Title | Atoms |
|--------|-------|-------|
| 1 | Networking Today | 766 |
| 2 | Basic Switch and End Device Configuration | 680 |
| 3 | Protocols and Models | 1,337 |
| 4 | Physical Layer | 1,092 |
| 5 | Number Systems | 222 |
| 6 | Data Link Layer | 999 |
| 7 | Ethernet Switching | 463 |
| 8 | Network Layer | 501 |
| 9 | Address Resolution | 291 |
| 10 | Basic Router Configuration | 403 |
| 11 | IPv4 Addressing | 1,725 |
| 12 | IPv6 Addressing | 1,182 |
| 13 | ICMP | 508 |
| 14 | Transport Layer | 542 |
| 15 | Application Layer | 509 |
| 16 | Network Security Fundamentals | 301 |

### Atom Types

| Type | Count | Description |
|------|-------|-------------|
| flashcard | 4,017 | Basic Q&A cards |
| true_false | 4,119 | True/false statements |
| cloze | 2,004 | Fill-in-the-blank |
| mcq | 1,213 | Multiple choice questions |
| matching | 92 | Term-definition matching |
| parsons | 86 | Procedure ordering |

---

## Study Workflow

### Daily Session

1. Run `nls study today` to see:
   - Due reviews count
   - New content available
   - Remediation needs
   - Current focus section
   - Overall mastery percentage

2. Open Anki and review due cards

3. Run `nls study sync` to update mastery scores

### Weekly Review

1. Run `nls study path` to see module progress
2. Identify modules needing attention
3. Run `nls study remediation` for struggling sections
4. Focus on red-flagged areas

### Mastery Criteria

A section is considered **mastered** when:
- Retrievability >= 90% (FSRS metric)
- Average lapses < 2
- All atoms reviewed at least once

---

## Database Schema

### Key Tables

| Table | Description |
|-------|-------------|
| `ccna_sections` | 530 curriculum sections with hierarchy |
| `clean_atoms` | 11,531 learning atoms |
| `section_mastery` | Per-section mastery tracking |
| `study_sessions` | Session history and stats |

### Section Hierarchy

- **Level 2** (X.Y): 94 main sections
- **Level 3** (X.Y.Z): 436 subsections

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `NOTION_API_KEY` | (optional) | For Notion sync |
| `ANKI_CONNECT_URL` | `http://127.0.0.1:8765` | AnkiConnect URL |
| `MASTERY_THRESHOLD` | `0.9` | 90% retrievability target |
| `REMEDIATION_RATIO` | `0.3` | 30% remediation in sessions |

### FSRS Settings

The system uses FSRS (Free Spaced Repetition Scheduler) metrics:
- **Retrievability**: Probability of correct recall
- **Stability**: Memory strength in days
- **Difficulty**: Card complexity (0-10)

---

## Scripts

### Atom Generation

```bash
# Generate for specific module
python scripts/generate_all_atoms.py --module 5

# Generate for specific section
python scripts/generate_all_atoms.py --section 11.5.1

# Dry run (preview without saving)
python scripts/generate_all_atoms.py --all --dry-run
```

### Section Population

```bash
# Populate sections from CCNA module files
python scripts/populate_ccna_sections.py

# Dry run
python scripts/populate_ccna_sections.py --dry-run
```

### Link Existing Atoms

```bash
# Link atoms to sections based on content
python scripts/link_atoms_to_sections.py

# Dry run
python scripts/link_atoms_to_sections.py --dry-run
```

---

## Project Structure

```
notion-learning-sync/
├── src/
│   ├── cli/
│   │   ├── main.py           # CLI entry point
│   │   └── study_commands.py # Study subcommands
│   ├── study/
│   │   ├── mastery_calculator.py  # FSRS-based mastery
│   │   ├── interleaver.py         # Adaptive interleaving
│   │   └── study_service.py       # High-level service
│   ├── db/
│   │   ├── database.py       # SQLAlchemy engine
│   │   └── migrations/       # SQL migrations
│   ├── sync/                 # Notion sync
│   ├── anki/                 # Anki integration
│   └── cleaning/             # Content quality
├── scripts/
│   ├── generate_all_atoms.py      # Atom generation
│   ├── populate_ccna_sections.py  # Section extraction
│   └── link_atoms_to_sections.py  # Atom linking
├── docs/
│   ├── CCNA/                 # Module content files
│   └── status.md             # Project status
├── config.py                 # Pydantic settings
├── requirements.txt
└── README.md
```

---

## Troubleshooting

### Common Issues

**"No sections found"**
```bash
# Run section population
python scripts/populate_ccna_sections.py
```

**"Error: relation does not exist"**
```bash
# Run migrations
python -m src.cli.main db migrate
```

**Unicode errors on Windows**
- The CLI uses ASCII-safe output for Windows compatibility
- If issues persist, set `PYTHONIOENCODING=utf-8`

**Anki connection failed**
- Ensure Anki is running
- Verify AnkiConnect plugin is installed
- Check `ANKI_CONNECT_URL` in `.env`

---

## Development

### Running Tests

```bash
pytest tests/
```

### API Server (optional)

```bash
# Start FastAPI server
uvicorn main:app --reload --port 8100

# View API docs
open http://localhost:8100/docs
```

---

## License

Internal use only - Project Astartes
