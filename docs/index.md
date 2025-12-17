# Cortex Documentation

Cortex is an adaptive learning system that synchronizes learning content from Notion databases, generates flashcards and quiz questions using LLM, integrates with Anki for spaced repetition, and provides a CLI for interactive study sessions with cognitive diagnosis and Socratic tutoring.

---

## What's New

**Visual Engine**: 3D ASCII art animation system using asciimatics. Volumetric depth shading with gradient characters for terminal-based cyberbrain boot sequences.

**Socratic Tutoring**: LLM-powered interactive dialogue system that guides learners through questions instead of revealing answers directly. Progressive scaffolding from pure Socratic to worked examples.

**Dynamic Struggle Tracking**: Real-time NCDE-driven weight updates with complete audit trail in `struggle_weight_history` table.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with DATABASE_URL and NOTION_API_KEY

# Initialize database
nls db migrate --migration 001

# Sync from Notion
nls sync notion

# Start studying
nls cortex start
```

---

## Documentation Structure

This documentation follows the [Diataxis](https://diataxis.fr/) framework:

| Category | Purpose | When to Use |
|----------|---------|-------------|
| **Tutorials** | Learning-oriented | First-time setup, getting started |
| **How-To Guides** | Task-oriented | Accomplish specific goals |
| **Reference** | Information-oriented | Look up commands, settings, schemas |
| **Explanation** | Understanding-oriented | Understand system design and theory |

---

## Tutorials

Step-by-step guides for learning by doing.

| Document | Description |
|----------|-------------|
| [Getting Started](tutorials/getting-started.md) | Install, configure, and run your first sync |
| [First Study Session](tutorials/first-study-session.md) | Run your first adaptive study session |

---

## How-To Guides

Task-focused instructions for specific goals.

| Document | Description |
|----------|-------------|
| [Configure Anki Sync](how-to/configure-anki-sync.md) | Set up bidirectional Anki synchronization |
| [Generate Atoms](how-to/generate-atoms.md) | Create learning atoms (flashcards, MCQs, cloze) |
| [Run Quality Audit](how-to/run-quality-audit.md) | Audit and improve content quality |
| [Maximize Retention](how-to/maximize-retention.md) | Evidence-based strategies for optimal learning |
| [Use Study Notes](how-to/use-study-notes.md) | Browse, generate, and rate remediation notes |
| [Use Signals Dashboard](how-to/use-signals-dashboard.md) | View transfer testing and memorization detection |
| [Configure Type Quotas](how-to/configure-type-quotas.md) | Balance question types in study sessions |

---

## Reference

Technical specifications for precise lookup.

| Document | Description |
|----------|-------------|
| [CLI Commands](reference/cli-commands.md) | Complete command reference for `nls` |
| [Configuration](reference/configuration.md) | Environment variables and settings |
| [Database Schema](reference/database-schema.md) | PostgreSQL tables and relationships |
| [API Endpoints](reference/api-endpoints.md) | REST API specification |
| [JIT Generation](reference/jit-generation.md) | On-demand content generation |
| [ML Personalization](reference/ml-personalization.md) | Signals and models for adaptive learning |

---

## Explanation

Conceptual explanations of system design.

| Document | Description |
|----------|-------------|
| [Architecture Overview](explanation/architecture.md) | System components and data flow |
| [FSRS Algorithm](explanation/fsrs-algorithm.md) | Spaced repetition scheduling |
| [Adaptive Learning](explanation/adaptive-learning.md) | Content selection and prioritization |
| [Cognitive Diagnosis](explanation/cognitive-diagnosis.md) | NCDE error analysis and remediation |
| [Session Remediation](explanation/session-remediation.md) | Hints, retry logic, and study notes |
| [Struggle-Aware System](explanation/struggle-aware-system.md) | Targeted weakness identification |
| [Transfer Testing](explanation/transfer-testing.md) | Memorization detection via format consistency |

---

## Core Concepts

### Learning Atom

A **learning atom** is the fundamental unit of content in Cortex. Each atom represents a single, atomic piece of knowledge that can be tested.

**Atom Types:**

| Type | Description | Example |
|------|-------------|---------|
| `flashcard` | Question/answer pair | "What does TCP stand for?" / "Transmission Control Protocol" |
| `cloze` | Fill-in-the-blank | "TCP provides {{c1::reliable}} data delivery" |
| `mcq` | Multiple choice question | Four options, one correct |
| `true_false` | Binary true/false | Statement verification |
| `parsons` | Code ordering problem | Arrange Cisco commands in sequence |
| `matching` | Term-definition pairs | Match protocols to port numbers |

### Anki Integration

Cortex integrates with Anki via [AnkiConnect](https://foosoft.net/projects/anki-connect/):

- **Push**: Learning atoms are pushed to Anki as cards
- **Pull**: FSRS review statistics are pulled back to update mastery state
- **Sync**: Bidirectional sync keeps both systems aligned

### FSRS (Free Spaced Repetition Scheduler)

Cortex uses FSRS-4 for spaced repetition scheduling:

| Metric | Description |
|--------|-------------|
| **Stability** | Days until memory decays to 90% retention |
| **Difficulty** | Intrinsic difficulty of the atom (0-1) |
| **Retrievability** | Current probability of successful recall |

---

## CLI Quick Reference

### Study Commands

| Command | Description |
|---------|-------------|
| `nls cortex start` | Start adaptive study session |
| `nls cortex optimize` | FSRS-optimized session |
| `nls cortex start --mode war` | Intensive cramming mode |
| `nls cortex resume` | Resume saved session |
| `nls cortex suggest` | Get study suggestions |
| `nls cortex stats` | View study statistics |
| `nls cortex today` | Daily session summary |
| `nls cortex path` | Show learning path progress |

### Reading Commands

| Command | Description |
|---------|-------------|
| `nls cortex read <N>` | Read module N content |
| `nls cortex read <N> --toc` | Show table of contents |
| `nls cortex read <N> --section X.Y` | Read specific section |

### Sync Commands

| Command | Description |
|---------|-------------|
| `nls sync notion` | Pull content from Notion |
| `nls sync anki-push` | Push learning atoms to Anki |
| `nls sync anki-pull` | Pull FSRS stats from Anki |
| `nls sync all` | Full sync pipeline |

### Content Generation Commands

| Command | Description |
|---------|-------------|
| `nls generate concept <uuid>` | Generate atoms for a concept |
| `nls generate gaps` | Find and fill content gaps |
| `nls generate stats` | Show JIT generation statistics |

### Session Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Reveal answer |
| `1-4` | Rate recall quality |
| `A-D` | Answer MCQ |
| `?` / `idk` | "I don't know" (honest path) |
| `h` | Show hint |
| `q` | Quit session |
| `Ctrl+C` | Save and quit |

---

## System Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.11+ | Required |
| PostgreSQL | 15+ | Required |
| Anki | 2.1.54+ | Optional, for spaced repetition |
| AnkiConnect | 6+ | Required if using Anki |

---

## Key Features

### Spaced Repetition

- FSRS-4 algorithm for optimal scheduling
- Memory stability and retrievability tracking
- Bidirectional Anki sync for mobile study

### Adaptive Learning

- Z-Score prioritization balances time-decay, centrality, project relevance, and novelty
- Prerequisite ordering ensures proper sequencing
- Struggle-aware targeting focuses on weak areas
- Question type quotas (35% MCQ, 25% T/F, 25% Parsons, 15% Matching)

### Cognitive Diagnosis (NCDE)

- Identifies failure modes: encoding, retrieval, discrimination, integration, executive, fatigue
- Targeted remediation based on error type
- Response time and pattern analysis
- **Real-time struggle weight updates** via `update_struggle_from_ncde()` called after each interaction

### Dynamic Struggle Tracking

- **Static Configuration**: User-declared struggles from `struggles.yaml` (one-time import)
- **Dynamic Updates**: NCDE-diagnosed patterns update weights in real-time during study sessions
- **Session Integration**: `CortexSession._update_struggle_weight()` triggers PostgreSQL updates after each NCDE diagnosis
- **Audit Trail**: Complete history in `struggle_weight_history` table
- **Trend Analysis**: 7-day trend tracking (improving/declining/stable)
- **Prerequisite Chains**: Layer 2, Layer 3, Upper Layers, Lab Skills

### JIT Content Generation

- On-demand atom generation when remediation content is exhausted
- Fills coverage gaps automatically
- Maps failure modes to appropriate content types
- **Struggle-targeted generation**: Atom types selected based on failure modes

### Content Generation (241 New Atoms)

- **NUMERIC atoms**: 89 atoms for subnetting calculations (Module 8)
- **MATCHING atoms**: Discrimination training for Ethernet concepts (Module 5)
- **PARSONS atoms**: CLI command sequence problems for lab skills
- **Fidelity tracking**: `is_hydrated`, `fidelity_type`, `source_fact_basis`

### Quality Control

- Evidence-based atomicity thresholds (Wozniak/Gwern research)
- Quality grading (A-F) based on word counts and structure
- AI-assisted content rewriting

### Remediation Learning Loop

- **"I Don't Know"**: Honest learning path for unfamiliar content
- **Pre-Session Notes**: Review relevant study notes before drilling
- **Micro-Notes**: Quick review triggered by consecutive errors
- **Post-Session Notes**: Generate LLM notes for struggled sections
- **Quality Tracking**: Automatic effectiveness measurement

### Socratic Tutoring

When learners indicate "I don't know", instead of revealing the answer immediately:

- **Progressive scaffolding**: Five levels from pure Socratic questions to full reveal
- **Dialogue tracking**: All sessions recorded in `socratic_dialogues` table
- **Gap detection**: Identifies prerequisite knowledge gaps during dialogue
- **Resolution outcomes**: Tracks whether learner self-solved, needed guidance, or gave up

| Scaffold Level | Behavior |
|----------------|----------|
| 0 | Pure Socratic (questions only) |
| 1 | Conceptual nudge |
| 2 | Partial reveal |
| 3 | Worked example with gaps |
| 4 | Full answer reveal |

### 3D Visual Engine

Terminal-based volumetric ASCII art system:

- **Depth shading**: Gradient characters `░▒▓█` create 3D perception
- **Animated brain**: Pulsing cyberbrain boot sequence with neural activation effects
- **Adaptive sizing**: Three frame sets for large, medium, and small terminals
- **3D panels**: Isometric panels with shadow effects for menus and status cards
- **Holographic headers**: Circuit/neural pattern decorations

**Implementation**: `src/delivery/cortex_visuals.py` (3D panel engine) and `src/delivery/animated_brain.py` (animation effects)

### Session Persistence

- Auto-saves every 5 questions
- Resume sessions within 24 hours
- Full telemetry logging

---

## Architecture Overview

```
Notion Databases
      |
      v
  [Sync Service] --> PostgreSQL (staging + canonical)
      |                    |
      v                    v
  [Quality Pipeline]  [Learning Engine]
      |                    |
      v                    v
  Anki (cards) <-----> [CLI Study Interface]
                           |
              +------------+------------+
              |            |            |
              v            v            v
       [3D Visual    [NCDE       [Socratic
        Engine]      Diagnosis]   Tutor]
              |            |            |
              +------------+------------+
                           |
                           v
                    [JIT Generation]
```

---

## Glossary

| Term | Definition |
|------|------------|
| **Atom** | Short for "learning atom"; a single testable unit of knowledge |
| **FSRS** | Free Spaced Repetition Scheduler; the scheduling algorithm |
| **NCDE** | Neuro-Cognitive Diagnostic Engine; identifies error types |
| **JIT** | Just-In-Time; on-demand content generation |
| **Mastery** | Combined score from review performance and quiz results |
| **Stability** | FSRS metric: days until memory decays to 90% retention |
| **Retrievability** | FSRS metric: current recall probability |
| **War Mode** | Intensive study mode focusing on struggling content |
| **Struggle Weight** | Combined static (YAML) and dynamic (NCDE) priority score |
| **ncde_weight** | Dynamic component of struggle weight; updated per-interaction |
| **PSI** | Pattern Separation Index; measures concept discrimination ability |
| **Failure Mode** | Cognitive error type (encoding, retrieval, discrimination, etc.) |
| **Prerequisite Chain** | Ordered sequence of modules that must be studied in order |
| **Fidelity Type** | Tracks atom content origin: verbatim, rephrased, or AI-enriched |
| **Hydration** | Process of enriching abstract facts with concrete scenarios |
| **Socratic Dialogue** | Interactive tutoring session using guiding questions |
| **Scaffold Level** | Progressive hint intensity in Socratic tutoring (0-4) |
| **Depth Shading** | ASCII gradient technique using `░▒▓█` for 3D visual effects |

---

## External Resources

- [FSRS Algorithm](https://github.com/open-spaced-repetition/fsrs4anki) - Spaced repetition scheduler
- [AnkiConnect](https://foosoft.net/projects/anki-connect/) - Anki API plugin
- [Diataxis Framework](https://diataxis.fr/) - Documentation methodology
- [Notion API](https://developers.notion.com/) - Notion integration

---

## See Also

- [CHANGELOG](../CHANGELOG.md) - Version history and recent changes
- [README](../README.md) - Project overview
