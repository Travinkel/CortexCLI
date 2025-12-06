# Notion Learning Sync Documentation

Welcome to the documentation for **notion-learning-sync**, a content synchronization and cleaning service for learning systems.

## Overview

Notion Learning Sync is a Python service that creates a clean, canonical data pipeline from Notion to your learning tools. It syncs content from Notion databases (flashcards, concepts, modules, tracks, programs), cleans it through a quality pipeline, and manages bidirectional sync with Anki.

## Key Features

- **Notion Sync**: Pull content from multiple Notion databases
- **Quality Pipeline**: Validate atomicity, detect duplicates, normalize content
- **AI Rewriting**: Automatically improve verbose flashcards using Gemini/Vertex AI
- **Review Queue**: Manual approval workflow for AI-generated content
- **Anki Integration**: Bidirectional sync (push cards, pull review stats)
- **Clean Output**: Canonical tables for personal use and future right-learning ETL

## Architecture Philosophy

The service follows a **staging -> cleaning -> canonical** pattern:

```
Notion (Source of Truth)
    | sync
+----------------------------------+
|  Staging Tables (stg_*)          |  <- Raw JSONB from Notion API
+----------------+-----------------+
                 |
+----------------v-----------------+
|  Cleaning Pipeline               |
|  - Atomicity validation          |
|  - Duplicate detection           |
|  - Prefix normalization          |
|  - AI rewriting (optional)       |
+----------------+-----------------+
                 |
+----------------v-----------------+
|  Canonical Tables                |  <- Trusted output
|  (learning_atoms, concepts)      |
+----------------+-----------------+
                 |
          +------+------+
          |             |
          v             v
        Anki         NLS CLI
   (flashcard,      (mcq, parsons,
    cloze)          true_false)
```

---

## Documentation Guide

### Getting Started

| Guide | Description |
|-------|-------------|
| [Quickstart](getting-started/quickstart.md) | Get up and running in 10 minutes |
| [Configuration](getting-started/configuration.md) | All settings explained |
| [Notion Setup](getting-started/notion-setup.md) | How to configure Notion databases |

### Architecture

| Guide | Description |
|-------|-------------|
| [Overview](architecture/overview.md) | System design and data flow |
| [Database Schema](architecture/database-schema.md) | Tables, relationships, and views |
| [Cleaning Pipeline](architecture/cleaning-pipeline.md) | Content quality processing |
| [Services Reference](architecture/services-reference.md) | Service layer documentation |

### Features

| Guide | Description |
|-------|-------------|
| [Anki Integration](features/anki-integration.md) | Bidirectional sync details |
| [Anki Card Structure](features/anki-card-structure.md) | Note vs card terminology, field specs |
| [CLI Quiz Compatibility](features/cli-quiz-compatibility.md) | CLI vs UI requirements matrix |
| [API Reference](features/api-reference.md) | REST endpoints |

### Courses

| Guide | Description |
|-------|-------------|
| [Course Overview](courses/index.md) | Processing pipeline and status |
| [CCNA ITN](courses/ccna-itn.md) | Gold standard course (4,924 atoms) |
| [CDS.Networking](courses/cds-networking.md) | Queued - CCNA aligned |
| [CDS.Security](courses/cds-security.md) | Queued - DevOps/Security |
| [PROGII](courses/progii.md) | Queued - Advanced programming |
| [SDE2](courses/sde2.md) | Queued - Full-stack development |
| [SDE2Testing](courses/sde2-testing.md) | Queued - Software testing |

### Operations

| Guide | Description |
|-------|-------------|
| [Deployment Guide](operations/deployment-guide.md) | Production setup |
| [Testing Guide](operations/testing-guide.md) | Test suite documentation |
| [Status](operations/status.md) | Current system status |

### Reference

| Guide | Description |
|-------|-------------|
| [Notion Database Structure](reference/notion-database-structure.md) | Notion schema reference |
| [Phase 4.6 CCNA Generation](reference/phase-4.6-ccna-generation.md) | Historical generation results |
| [Struggle Schema](reference/struggle-schema.md) | Struggle tracking schema |

### Epics

| Guide | Description |
|-------|-------------|
| [CCNA Study Path](epics/ccna-study-path.md) | Daily study sessions, learning path |
| [Learning Atom Enhancement](epics/learning-atom-enhancement.md) | Prerequisite linking, metadata enrichment |

---

## Current Status

### Data Pipeline Status (December 2025)

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Atoms** | 4,924 | CCNA ITN complete curriculum |
| **Atoms Linked to Sections** | 4,574 (93%) | Via keyword matching |
| **Unmatched Atoms** | 350 | Pending keyword expansion |
| **CCNA Sections** | 530 | Modules 1-16 |
| **Unique Parent Sections with Atoms** | 63 | e.g., "14.6", "11.5" |

### Anki Sync

- **4,238 notes** synced to Anki (3,408 flashcards + 830 cloze)
- **571 atoms** remain in NLS (533 MCQ + 38 Parsons)
- Deck structure: `CCNA::ITN::M{XX} {Module Name}`

### Test Suite

| Test Type | Tests | Status |
|-----------|-------|--------|
| Unit Tests | 35 | All passing |
| Integration Tests | 16 | All passing |
| Smoke Tests | ~20 | Ready to run |
| E2E Tests | ~25 | Require API server |

### Course Queue

| Course | Status | Atoms |
|--------|--------|-------|
| CCNA ITN | **Complete** | 4,924 |
| CDS.Networking | Queued | ~1,500 |
| CDS.Security | Queued | ~2,000 |
| PROGII | Queued | ~1,800 |
| SDE2 | Queued | ~2,500 |
| SDE2Testing | Queued | ~1,200 |

---

## Project Structure

```
notion-learning-sync/
├── src/
│   ├── sync/           # Notion sync engine
│   ├── cleaning/       # Content quality pipeline
│   ├── anki/           # Anki integration
│   ├── db/             # Database layer
│   │   ├── models/     # SQLAlchemy models
│   │   └── migrations/ # SQL migrations
│   ├── api/            # FastAPI endpoints
│   └── cli/            # Typer CLI
├── scripts/            # Utility scripts
├── docs/               # This documentation
│   ├── getting-started/
│   ├── architecture/
│   ├── features/
│   ├── courses/
│   ├── operations/
│   ├── reference/
│   ├── epics/
│   └── source-materials/
│       ├── CCNA/       # CCNA module sources
│       └── EASV/       # EASV course sources
├── config.py           # Pydantic settings
├── main.py             # Entry point
└── requirements.txt    # Dependencies
```

---

## Quick Links

- [Notion API Docs](https://developers.notion.com/)
- [AnkiConnect Plugin](https://foosoft.net/projects/anki-connect/)
- [FSRS Algorithm](https://github.com/open-spaced-repetition/fsrs4anki)

## Support

This is an internal project for Project Astartes. For issues or questions, contact the development team.

## License

Internal use only - Project Astartes
