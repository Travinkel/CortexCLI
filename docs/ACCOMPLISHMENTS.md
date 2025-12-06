# Project Accomplishments: notion-learning-sync

**Document Version**: 1.0
**Last Updated**: December 3, 2025
**Status**: Production-Ready

---

## Executive Summary

The `notion-learning-sync` project implements an adaptive learning system for CCNA certification study. The system transforms raw course content into atomic learning units, syncs them to Anki for spaced repetition, and provides intelligent prerequisite-based learning paths with just-in-time remediation.

### Key Metrics

| Metric | Value |
|--------|-------|
| Total Learning Atoms | 3,270 |
| CCNA Modules Covered | 17 |
| Concept Clusters | 17 |
| Prerequisite Relationships | 31 (module-based, soft-gated) |
| Atoms with Prerequisites | 2,834 (87%) |
| Quality Grade A/B | 95.5% |

---

## System Architecture

### High-Level Component Diagram

```
+------------------+     +-------------------+     +------------------+
|  Content Layer   |     |  Adaptive Engine  |     |  Presentation    |
|                  |     |                   |     |                  |
| - CCNA Modules   |---->| - MasteryCalc     |---->| - Anki Decks     |
| - Atomizer       |     | - PathSequencer   |     | - CLI Interface  |
| - QA Pipeline    |     | - Remediation     |     | - API Endpoints  |
+------------------+     +-------------------+     +------------------+
         |                       |                        |
         v                       v                        v
+------------------------------------------------------------------+
|                        PostgreSQL Database                        |
| clean_atoms | clean_concepts | explicit_prerequisites | mastery   |
+------------------------------------------------------------------+
```

### Directory Structure

```
src/
  adaptive/           # Phase 5: Adaptive Learning Engine
    models.py         # Data models and constants
    mastery_calculator.py
    path_sequencer.py
    remediation_router.py
    suitability_scorer.py
    learning_engine.py
  prerequisites/      # Phase 6: Gating System
    prerequisite_service.py
    gating_service.py
  ccna/               # Content Generation
    atomizer_service.py
    generation_pipeline.py
scripts/
  ccna_generate.py
  anki_full_sync.py
  reading_progress.py
  populate_prerequisites.py
```

---

## Phase 5: Adaptive Learning Engine (Completed)

### Overview

The Adaptive Learning Engine implements Knewton-style just-in-time remediation with mastery-based content gating. It orchestrates learning sessions, tracks mastery progress, and dynamically adjusts content sequencing based on learner performance.

### Architecture Components

#### 1. MasteryCalculator

**Location**: `src/adaptive/mastery_calculator.py`

Computes learner mastery from FSRS review data and quiz performance.

**Core Algorithm**:

```python
combined_mastery = (review_mastery * 0.625) + (quiz_mastery * 0.375)
```

**Where**:
- `review_mastery` = weighted average of retrievability scores
- `retrievability` = e^(-days_since_review / stability)
- `weight` = min(review_count, 20)
- `quiz_mastery` = best score from last 3 attempts

**Mastery Levels**:

| Level | Range | Description |
|-------|-------|-------------|
| NOVICE | < 40% | Foundational gaps present |
| DEVELOPING | 40-64% | Building understanding |
| PROFICIENT | 65-84% | Solid grasp of material |
| MASTERY | >= 85% | Expert-level retention |

**Key Methods**:

| Method | Purpose |
|--------|---------|
| `compute_concept_mastery()` | Full mastery state for a concept |
| `update_mastery_state()` | Persist updated mastery |
| `get_mastery_summary()` | Aggregated stats by level |

---

#### 2. PathSequencer

**Location**: `src/adaptive/path_sequencer.py`

Determines optimal atom ordering based on prerequisite graph, mastery state, knowledge type interleaving, and spaced repetition scheduling.

**Sequencing Strategy**:

1. Topological sort of prerequisite graph
2. Prioritize unlocked concepts
3. Interleave knowledge types (declarative -> conceptual -> procedural)
4. Mix due reviews with new content

**Key Methods**:

| Method | Purpose |
|--------|---------|
| `get_learning_path()` | Generate path to master a concept |
| `get_next_atoms()` | Get next N atoms for learner |
| `check_unlock_status()` | Verify prerequisite completion |

**Learning Path Generation**:

```python
# Recursive prerequisite chain traversal
WITH RECURSIVE prereq_chain AS (
    SELECT target_concept_id, 1 as depth
    FROM explicit_prerequisites
    WHERE source_concept_id = :concept_id
    UNION ALL
    SELECT ep.target_concept_id, pc.depth + 1
    FROM explicit_prerequisites ep
    JOIN prereq_chain pc ON ep.source_concept_id = pc.concept_id
    WHERE pc.depth < 10
)
```

---

#### 3. RemediationRouter

**Location**: `src/adaptive/remediation_router.py`

Detects knowledge gaps and routes learners to prerequisite content. Implements just-in-time remediation triggered by:

- Incorrect answers
- Low confidence ratings
- Unmet prerequisite mastery

**Trigger Types**:

| Trigger | Description |
|---------|-------------|
| `INCORRECT_ANSWER` | Wrong answer submitted |
| `LOW_CONFIDENCE` | Self-reported confidence < 3/5 |
| `PREREQUISITE_GAP` | Missing foundation knowledge |
| `MANUAL` | Instructor or learner initiated |

**Remediation Priority Algorithm**:

```python
def _determine_priority(mastery: float) -> str:
    if mastery < 0.3:
        return "high"
    elif mastery < 0.5:
        return "medium"
    return "low"
```

**Key Methods**:

| Method | Purpose |
|--------|---------|
| `check_remediation_needed()` | Evaluate after answer |
| `get_knowledge_gaps()` | List all gaps for learner |
| `trigger_remediation()` | Manually start remediation |
| `complete_remediation()` | Record outcome |

---

#### 4. SuitabilityScorer

**Location**: `src/adaptive/suitability_scorer.py`

Scores content suitability for each atom type using a three-signal formula.

**Suitability Formula**:

```python
suitability = (knowledge_signal * 0.6) + (structure_signal * 0.3) + (length_signal * 0.1)
```

**Signal Components**:

| Signal | Weight | Description |
|--------|--------|-------------|
| Knowledge | 60% | Knowledge type alignment (factual/conceptual/procedural) |
| Structure | 30% | Content structure analysis (CLI commands, lists, definitions) |
| Length | 10% | Word count appropriateness for atom type |

**Knowledge Type Affinity Matrix**:

| Type | flashcard | cloze | mcq | parsons | sequence |
|------|-----------|-------|-----|---------|----------|
| factual | 1.0 | 0.9 | 0.6 | 0.2 | 0.3 |
| conceptual | 0.6 | 0.5 | 0.9 | 0.3 | 0.4 |
| procedural | 0.3 | 0.4 | 0.5 | 1.0 | 1.0 |

**Optimal Length Ranges**:

| Atom Type | Min Words | Max Words |
|-----------|-----------|-----------|
| flashcard | 5 | 25 |
| cloze | 10 | 40 |
| mcq | 15 | 50 |
| parsons | 15 | 60 |
| sequence | 15 | 50 |

---

#### 5. LearningEngine

**Location**: `src/adaptive/learning_engine.py`

Main orchestration layer coordinating session management, mastery tracking, adaptive sequencing, and remediation.

**Session Modes**:

| Mode | Description |
|------|-------------|
| `ADAPTIVE` | Full adaptive with remediation |
| `REVIEW` | Due items only |
| `QUIZ` | Assessment mode (no hints) |
| `REMEDIATION` | Focused gap remediation |

**Core Workflow**:

```
create_session() -> get_next_atom() -> submit_answer() -> [remediation?] -> repeat
```

**Key Methods**:

| Method | Purpose |
|--------|---------|
| `create_session()` | Initialize learning session |
| `submit_answer()` | Process answer, check for remediation |
| `get_next_atom()` | Fetch next item (handles remediation) |
| `get_learning_path()` | Generate path to target mastery |
| `inject_remediation()` | Insert remediation sequence |

---

### Data Models

**Location**: `src/adaptive/models.py`

#### Core Models

| Model | Description |
|-------|-------------|
| `ConceptMastery` | Complete mastery state with review/quiz breakdowns |
| `KnowledgeBreakdown` | Declarative/Procedural/Application scores (0-10 scale) |
| `LearningPath` | Ordered prerequisite chain with atom sequence |
| `RemediationPlan` | Gap concept, atoms, priority, trigger info |
| `SessionState` | Full session state with progress and current atom |

#### Enumerations

| Enum | Values |
|------|--------|
| `MasteryLevel` | NOVICE, DEVELOPING, PROFICIENT, MASTERY |
| `GatingType` | SOFT (warning), HARD (blocked) |
| `TriggerType` | INCORRECT_ANSWER, LOW_CONFIDENCE, PREREQUISITE_GAP, MANUAL |
| `SessionMode` | ADAPTIVE, REVIEW, QUIZ, REMEDIATION |
| `SessionStatus` | ACTIVE, PAUSED, COMPLETED, ABANDONED |

#### Constants

```python
MASTERY_WEIGHTS = {
    "review": 0.625,  # 62.5%
    "quiz": 0.375,    # 37.5%
}

MASTERY_THRESHOLDS = {
    "foundation": 0.40,
    "integration": 0.65,
    "mastery": 0.85,
}

ATOM_TYPE_KNOWLEDGE_MAP = {
    "flashcard": "declarative",
    "cloze": "declarative",
    "parsons": "procedural",
    "sequence": "procedural",
    "mcq": "application",
    "compare": "application",
}
```

---

## Phase 6: Flashcard Quality and Prerequisites (Completed)

### Flashcard Quality Improvements

Updated optimal word counts for explanatory answer style:

| Parameter | Previous | Current |
|-----------|----------|---------|
| BACK_WORDS_OPTIMAL | 5 | 15 |
| BACK_WORDS_WARNING | 15 | 25 |

**Answer Style Guidelines**:
- Factual cards: 8-15 words
- Conceptual cards: 15-25 words
- Format: Explanatory sentences, not single words

---

### Prerequisite System

**Location**: `src/prerequisites/gating_service.py`

Implements Knewton-style soft/hard gating for prerequisite enforcement.

#### Access Status

| Status | Description |
|--------|-------------|
| `ALLOWED` | No prerequisites or all met |
| `WARNING` | Soft-gated prerequisites not met |
| `BLOCKED` | Hard-gated prerequisites not met |
| `WAIVED` | Prerequisites waived |

#### Mastery Thresholds

| Type | Threshold | Use Case |
|------|-----------|----------|
| foundation | 40% | Basic concept familiarity |
| integration | 65% | Standard prerequisite |
| mastery | 85% | Advanced topics |

#### Waiver System

Supports instructor, challenge, external, and accelerated waivers with:
- Expiration dates
- Evidence tracking
- Revocation capability

**Challenge Waiver Eligibility**: >= 95% mastery on all prerequisites

#### Current State

- **31 module-based prerequisites** created
- **Soft gating** with 65% threshold
- **87% of atoms** (2,834/3,270) have prerequisite concepts
- **Tags added to Anki**: `prereq::ConceptName`

---

## Scripts Reference

### ccna_generate.py

**Purpose**: Generate learning atoms from CCNA modules.

```bash
# Analyze modules only
python scripts/ccna_generate.py --analyze

# Create concept hierarchy (run once)
python scripts/ccna_generate.py --create-hierarchy

# Generate priority modules (worst quality)
python scripts/ccna_generate.py --priority

# Generate specific modules
python scripts/ccna_generate.py --modules 7,9,10

# Generate all modules
python scripts/ccna_generate.py --all

# Run QA report
python scripts/ccna_generate.py --qa-report

# Dry run
python scripts/ccna_generate.py --priority --dry-run
```

---

### anki_full_sync.py

**Purpose**: Sync atoms to Anki with hierarchical deck structure.

```bash
# Preview sync
python scripts/anki_full_sync.py --dry-run

# Full sync with stale deletion
python scripts/anki_full_sync.py --delete-stale

# Create filtered study decks
python scripts/anki_full_sync.py --create-filtered

# Show recommended study order
python scripts/anki_full_sync.py --show-order
```

**Deck Hierarchy**: `CCNA::ClusterName::ConceptName`

**Tags Applied**:
- `cluster::ClusterName`
- `concept::ConceptName`
- `type::flashcard|cloze|mcq`
- `prereq::PrerequisiteConceptName`

---

### reading_progress.py

**Purpose**: Track reading progress and recommend re-reads based on mastery.

```bash
# Mark chapters as read
python scripts/reading_progress.py mark-read --chapters 1-17 --level read

# Show reading status
python scripts/reading_progress.py status

# Get re-read recommendations
python scripts/reading_progress.py recommend-reread --learner default
```

**Re-read Thresholds**:

| Priority | Mastery Range |
|----------|---------------|
| High | < 40% |
| Medium | 40-60% |
| Low | 60-75% |

**Comprehension Levels**: not_started, skimmed, read, studied, mastered

---

### populate_prerequisites.py

**Purpose**: Populate prerequisite relationships between concepts.

```bash
# Dry run
python scripts/populate_prerequisites.py --dry-run

# Create prerequisites
python scripts/populate_prerequisites.py
```

**Inference Strategy**: Concepts in later modules depend on concepts in earlier modules (1-2 modules back).

---

## Database Schema

### Key Tables

| Table | Description | Row Count |
|-------|-------------|-----------|
| `clean_atoms` | Curriculum-linked learning atoms | 3,270 |
| `clean_concepts` | Named concepts with definitions | 17 clusters |
| `clean_modules` | CCNA modules 1-17 | 17 |
| `clean_tracks` | CCNA/ITN track | 1 |
| `explicit_prerequisites` | Concept dependencies | 31 |
| `learner_mastery_state` | Per-learner mastery scores | Dynamic |
| `reading_progress` | Chapter completion tracking | Dynamic |
| `quiz_questions` | Quiz-format atoms | 497 |

### Schema Relationships

```
clean_tracks
    |
    v
clean_modules
    |
    v
clean_atoms <-----> clean_concepts
    |                    |
    |                    v
    |           explicit_prerequisites
    |                    |
    v                    v
quiz_questions    learner_mastery_state
```

---

## Current Status

### Content Statistics

| Metric | Value |
|--------|-------|
| Total Atoms | 3,270 |
| Modules | 17 |
| Concept Clusters | 17 |
| Quality A/B | 95.5% |

### Anki Integration

| Metric | Value |
|--------|-------|
| Deck Hierarchy | CCNA::Cluster::Concept |
| Chapters Read | 1-17 (all marked) |
| Prerequisite Tags | prereq::ConceptName |

### Prerequisite System

| Metric | Value |
|--------|-------|
| Total Prerequisites | 31 |
| Gating Type | Soft |
| Mastery Threshold | 65% |
| Atoms with Prerequisites | 2,834 (87%) |

---

## API Reference

### LearningEngine API

```python
from src.adaptive import LearningEngine, SessionMode

engine = LearningEngine()

# Create adaptive session
session = engine.create_session(
    learner_id="user123",
    mode=SessionMode.ADAPTIVE,
    target_cluster_id=cluster_uuid,
    atom_count=20,
)

# Get next atom
atom = engine.get_next_atom(session.session_id)

# Submit answer
result = engine.submit_answer(
    session_id=session.session_id,
    atom_id=atom.atom_id,
    answer="user answer",
    confidence=0.8,
)

# Check for remediation
if result.remediation_triggered:
    engine.inject_remediation(
        session.session_id,
        result.remediation_plan,
    )

# Get mastery
mastery_list = engine.get_learner_mastery(
    learner_id="user123",
    cluster_id=cluster_uuid,
)

# Get learning path
path = engine.get_learning_path(
    learner_id="user123",
    target_concept_id=concept_uuid,
    target_mastery=0.85,
)
```

### GatingService API

```python
from src.prerequisites.gating_service import GatingService, AccessStatus

gating = GatingService(session)

# Evaluate access
result = await gating.evaluate_access(
    concept_id=concept_uuid,
    user_mastery_data={prereq_uuid: 0.70},
)

if result.status == AccessStatus.BLOCKED:
    print(f"Blocked: {result.blocking_prerequisites}")
elif result.status == AccessStatus.WARNING:
    print(f"Warnings: {result.warnings}")

# Grant waiver
waiver = await gating.create_waiver(
    prerequisite_id=prereq_uuid,
    waiver_type="instructor",
    granted_by="admin",
)
```

---

## Future Development

### Planned Enhancements

1. **Rule-Space Cognitive Diagnosis** (Phase 7)
   - Tatsuoka's methodology
   - Incidence matrix (atoms to concepts)
   - Neurocognitive fail mode classification

2. **Additional Courses**
   - CDS.Networking (~1,500 atoms)
   - CDS.Security (~2,000 atoms)
   - PROGII (~1,800 atoms)

3. **Advanced Features**
   - Hard gating for critical prerequisites
   - Challenge exam waivers
   - Peer comparison analytics

---

## References

### Internal Documentation

- [Database Schema](database-schema.md)
- [API Reference](api-reference.md)
- [Anki Integration](anki-integration.md)
- [Phase 4.6 CCNA Generation](phase-4.6-ccna-generation.md)

### External Resources

- [FSRS Algorithm](https://github.com/open-spaced-repetition/fsrs4anki)
- [Knewton Adaptive Learning](https://www.knewton.com/)
- [AnkiConnect API](https://foosoft.net/projects/anki-connect/)

---

## Appendix A: Mastery Calculation Example

```python
# Example: Compute mastery for a concept

# Review data from Anki
stability_days = 14.0
days_since_review = 3
review_count = 8

# Calculate retrievability
retrievability = math.exp(-days_since_review / stability_days)
# = math.exp(-3 / 14) = 0.807

# Weight by review count (capped at 20)
weight = min(review_count, 20)  # = 8

# If multiple atoms, compute weighted average
# review_mastery = sum(retrievability * weight) / sum(weights)
review_mastery = 0.807

# Quiz mastery (best of last 3)
quiz_scores = [0.80, 0.90, 0.85]
quiz_mastery = max(quiz_scores)  # = 0.90

# Combined mastery
combined_mastery = (0.807 * 0.625) + (0.90 * 0.375)
# = 0.504 + 0.338 = 0.842 -> PROFICIENT
```

---

## Appendix B: Suitability Scoring Example

```python
# Example: Score suitability for a procedural content block

content = """
Configure OSPF on R1:
1. Enter global configuration mode
2. Enable OSPF process 1
3. Configure network statement
4. Verify with show ip ospf neighbor
"""

# Extract features
features = scorer.extract_features(content)
# has_numbered_steps = True
# step_count = 4
# has_cli_commands = True
# word_count = 25

# Knowledge type = procedural
knowledge_signal = KNOWLEDGE_TYPE_AFFINITY["procedural"]
# parsons: 1.0, sequence: 1.0, flashcard: 0.3

# Structure signal for parsons
structure_signal = 0.5 + 0.4 (has_cli) + 0.1 (has_steps) = 1.0

# Length signal (optimal: 15-60 for parsons)
length_signal = 1.0  # 25 words in optimal range

# Combined score for parsons
suitability = (1.0 * 0.6) + (1.0 * 0.3) + (1.0 * 0.1) = 1.0
# Recommendation: parsons with high confidence
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-03 | Initial documentation |
