# Configuration Reference

Complete environment variable reference for Cortex.

---

## Overview

Configuration uses Pydantic Settings with `.env` file support:

```bash
cp .env.example .env
```

Never commit `.env` to version control.

---

## Database

### DATABASE_URL

PostgreSQL connection string.

| Property | Value |
|----------|-------|
| Type | string |
| Required | Yes |
| Default | `postgresql://postgres:learning123@localhost:5432/notion_learning_sync` |

Format: `postgresql://[user]:[password]@[host]:[port]/[database]`

---

## Notion API

### NOTION_API_KEY

| Property | Value |
|----------|-------|
| Type | string |
| Required | Yes |

Get from [notion.so/my-integrations](https://www.notion.so/my-integrations).

### NOTION_VERSION

| Property | Value |
|----------|-------|
| Type | string |
| Default | `2022-06-28` |

---

## Notion Database IDs

All IDs are 32-character hex strings from Notion URLs.

### Core Databases

| Variable | Description |
|----------|-------------|
| `FLASHCARDS_DB_ID` | All-Atom Master database |
| `SUPERCONCEPTS_DB_ID` | Knowledge Areas (L0/L1) |
| `SUBCONCEPTS_DB_ID` | Being merged into Flashcards |
| `PROJECTS_DB_ID` | Learning focus/goals |

### Curriculum Databases

| Variable | Description |
|----------|-------------|
| `MODULES_DB_ID` | Week/chapter units |
| `TRACKS_DB_ID` | Course sequences |
| `PROGRAMS_DB_ID` | Degree/cert paths |

### Activity Databases

| Variable | Description |
|----------|-------------|
| `ACTIVITIES_DB_ID` | Assignments/exercises |
| `SESSIONS_DB_ID` | Study session logs |

---

## Anki Integration

### ANKI_CONNECT_URL

| Property | Value |
|----------|-------|
| Type | string |
| Default | `http://127.0.0.1:8765` |

### ANKI_DECK_NAME

| Property | Value |
|----------|-------|
| Type | string |
| Default | `CCNA::ITN` |

Use `::` for nested decks (e.g., `CCNA::ITN::M01 Networking Today`).

### ANKI_NOTE_TYPE

| Property | Value |
|----------|-------|
| Type | string |
| Default | `Basic` |

Options: `Basic`, `Basic (and reversed card)`, `Cloze`, custom types.

### ANKI_QUERY

| Property | Value |
|----------|-------|
| Type | string |
| Default | Complex query filtering CCNA ITN sections |

Anki search query for filtering cards during pull. Supports section tags (e.g., `tag:section:2.1.4`).

### Anki Note Types (src/anki/config.py)

| Constant | Value | Usage |
|----------|-------|-------|
| `FLASHCARD_NOTE_TYPE` | `LearningOS-v2` | Standard flashcards |
| `CLOZE_NOTE_TYPE` | `LearningOS-v2 Cloze-NEW` | Cloze deletions |
| `BASE_DECK` | `CCNA::ITN` | Parent deck |
| `CURRICULUM_ID` | `ccna-itn` | Tag prefix |
| `SOURCE_TAG` | `cortex` | System identifier |

### Anki Deck Structure

Module decks follow pattern: `CCNA::ITN::M{NN} {Module Name}`

| Module | Deck Name |
|--------|-----------|
| 1 | `CCNA::ITN::M01 Networking Today` |
| 5 | `CCNA::ITN::M05 Number Systems` |
| 11 | `CCNA::ITN::M11 IPv4 Addressing` |
| 17 | `CCNA::ITN::M17 Build a Small Network` |

---

## AI Integration

### ANTHROPIC_API_KEY

Anthropic API key for Claude models.

### GOOGLE_API_KEY

Google API key for Gemini models. Get from [Google AI Studio](https://makersuite.google.com/app/apikey).

**Note**: The note generator accepts both `GOOGLE_API_KEY` and `GEMINI_API_KEY` for flexibility. If both are set, `GOOGLE_API_KEY` takes precedence.

### GEMINI_API_KEY

Google Gemini API key (alternative to `GOOGLE_API_KEY`). Get from [Google AI Studio](https://makersuite.google.com/app/apikey).

### VERTEX_PROJECT

Google Cloud project ID for Vertex AI.

### VERTEX_LOCATION

| Property | Value |
|----------|-------|
| Type | string |
| Default | `us-central1` |

### AI_MODEL

| Property | Value |
|----------|-------|
| Type | string |
| Default | `gemini-2.0-flash` |

---

## Atomicity Thresholds

Evidence-based thresholds from cognitive science research.

### ATOMICITY_FRONT_MAX_WORDS

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 25 |

Source: Wozniak's 20 Rules.

### ATOMICITY_BACK_OPTIMAL_WORDS

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 5 |

Source: SuperMemo retention research.

### ATOMICITY_BACK_WARNING_WORDS

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 15 |

### ATOMICITY_BACK_MAX_CHARS

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 120 |

Source: Cognitive Load Theory.

### ATOMICITY_MODE

| Property | Value |
|----------|-------|
| Type | string |
| Default | `relaxed` |
| Options | `relaxed`, `strict` |

---

## FSRS Settings

### FSRS_DEFAULT_STABILITY

Initial stability for new cards (days).

| Property | Value |
|----------|-------|
| Type | float |
| Default | 1.0 |

### FSRS_DEFAULT_DIFFICULTY

Initial difficulty (0-1).

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.3 |

### FSRS_DESIRED_RETENTION

Target retention rate.

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.9 |

---

## Sync Behavior

### SYNC_INTERVAL_MINUTES

Auto-sync interval (0 to disable).

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 120 |

### PROTECT_NOTION

Prevent writes to Notion.

| Property | Value |
|----------|-------|
| Type | boolean |
| Default | `true` |

### DRY_RUN

Log actions without making changes.

| Property | Value |
|----------|-------|
| Type | boolean |
| Default | `false` |

---

## Logging

### LOG_LEVEL

| Property | Value |
|----------|-------|
| Type | string |
| Default | `INFO` |
| Options | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### LOG_FILE

| Property | Value |
|----------|-------|
| Type | string |
| Default | `logs/notion_learning_sync.log` |

---

## API Server

### API_HOST

| Property | Value |
|----------|-------|
| Type | string |
| Default | `127.0.0.1` |

Use `0.0.0.0` for all interfaces.

### API_PORT

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 8100 |

---

## Semantic Embeddings

### EMBEDDING_MODEL

| Property | Value |
|----------|-------|
| Type | string |
| Default | `all-MiniLM-L6-v2` |

### EMBEDDING_DIMENSION

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 384 |

### SEMANTIC_DUPLICATE_THRESHOLD

Cosine similarity threshold for duplicates.

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.85 |

---

## Prerequisites

### PREREQUISITE_FOUNDATION_THRESHOLD

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.40 |

### PREREQUISITE_INTEGRATION_THRESHOLD

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.65 |

### PREREQUISITE_MASTERY_THRESHOLD

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.85 |

---

## Quiz Quality

### QUIZ_MCQ_OPTIMAL_OPTIONS

| Property | Value |
|----------|-------|
| Type | integer |
| Default | 4 |

### QUIZ_DEFAULT_PASSING_THRESHOLD

| Property | Value |
|----------|-------|
| Type | float |
| Default | 0.70 |

---

## Z-Score Algorithm

Cortex 2.0 prioritization weights.

| Variable | Default | Description |
|----------|---------|-------------|
| `ZSCORE_WEIGHT_DECAY` | 0.30 | Time-decay signal |
| `ZSCORE_WEIGHT_CENTRALITY` | 0.25 | Graph centrality |
| `ZSCORE_WEIGHT_PROJECT` | 0.25 | Project relevance |
| `ZSCORE_WEIGHT_NOVELTY` | 0.20 | Novelty |
| `ZSCORE_ACTIVATION_THRESHOLD` | 0.5 | Focus Stream activation |

---

## CCNA Content Generation

### CCNA_MODULES_PATH

| Property | Value |
|----------|-------|
| Type | string |
| Default | `docs/source-materials/CCNA` |

Path to CCNA module TXT files.

### CCNA_MIN_QUALITY_GRADE

| Property | Value |
|----------|-------|
| Type | string |
| Default | `B` |
| Options | `A`, `B`, `C`, `D` |

Minimum grade to accept without flagging.

### CCNA Atom Type Distribution

Target percentages for generated content:

| Type | Default | Description |
|------|---------|-------------|
| `CCNA_FLASHCARD_PERCENTAGE` | 0.50 | Basic Q&A (50%) |
| `CCNA_MCQ_PERCENTAGE` | 0.20 | Multiple choice (20%) |
| `CCNA_CLOZE_PERCENTAGE` | 0.10 | Fill-in-blank (10%) |
| `CCNA_PARSONS_PERCENTAGE` | 0.10 | Code ordering (10%) |
| `CCNA_OTHER_PERCENTAGE` | 0.10 | Matching, etc. (10%) |

---

## Socratic Tutoring

The Socratic dialogue system uses the Gemini API for LLM-powered tutoring.

### Configuration (src/cortex/socratic.py)

| Setting | Value | Description |
|---------|-------|-------------|
| Model | `gemini-2.0-flash` | Fast responses for interactive dialogue |
| Stuck Threshold | 3 | Consecutive "don't know" before escalating |
| Max Scaffold | 4 | Levels before full reveal |

### Scaffold Level Progression

Learner confusion/stuck signals trigger automatic scaffold escalation:

1. Pure Socratic (questions only)
2. Conceptual nudge
3. Partial reveal
4. Worked example
5. Full answer with explanation

---

## Struggle Weights

### Default Struggle Areas (015_struggle_weights.sql)

Pre-configured struggles based on common CCNA weak areas:

| Module | Severity | Failure Modes | Notes |
|--------|----------|---------------|-------|
| 5 | Critical | FM3 | Binary/Decimal/Hex conversions |
| 11 | Critical | FM3, FM4 | Subnetting, VLSM calculations |
| 12 | Critical | FM1, FM3 | IPv6 addressing, EUI-64 |
| 3 | High | FM1, FM6 | OSI vs TCP-IP mapping |

### Severity Weights

| Severity | Weight |
|----------|--------|
| `critical` | 1.0 |
| `high` | 0.75 |
| `medium` | 0.5 |
| `low` | 0.25 |

---

## Example Configurations

### Development

```bash
DATABASE_URL=postgresql://postgres:dev@localhost:5432/notion_learning_sync
NOTION_API_KEY=secret_dev_key
FLASHCARDS_DB_ID=your_test_db_id

ATOMICITY_MODE=relaxed
PROTECT_NOTION=true
DRY_RUN=false
LOG_LEVEL=DEBUG
```

### Production

```bash
DATABASE_URL=postgresql://user:secure_pass@prod-db:5432/learning
NOTION_API_KEY=secret_prod_key

ATOMICITY_MODE=strict
PROTECT_NOTION=true
LOG_LEVEL=INFO
SYNC_INTERVAL_MINUTES=120

GEMINI_API_KEY=prod_api_key
```

---

## See Also

- [Getting Started Tutorial](../tutorials/getting-started.md)
- [Database Schema](database-schema.md)
