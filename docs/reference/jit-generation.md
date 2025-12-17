# JIT Content Generation

Just-In-Time (JIT) Content Generation fills learning gaps by creating atoms on-demand when existing remediation content is exhausted.

## Overview

JIT Generation activates when the adaptive learning engine detects insufficient remediation atoms for a struggling concept. Rather than leaving learners without support, the system generates targeted content based on the diagnosed cognitive failure mode.

**Primary use cases:**

1. Learner fails a question and fewer than 3 remediation atoms exist
2. A concept has no atoms (missing coverage)
3. User explicitly requests additional practice material
4. System proactively generates content for upcoming concepts

**Key principle:** Generate the right type of content for the specific learning failure, not generic practice material.

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        LearningEngine                           │
│  submit_answer() → diagnose → remediate → JIT if atoms < 3      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RemediationRouter                          │
│  get_remediation_atoms_with_jit()                               │
│  MIN_REMEDIATION_ATOMS = 3                                      │
│  enable_jit: bool                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JITGenerationService                         │
│  src/adaptive/jit_generator.py                                  │
│                                                                 │
│  Methods:                                                       │
│  - generate_for_gap(request)                                    │
│  - generate_for_failed_question(concept_id, learner_id, ...)    │
│  - generate_for_missing_coverage(concept_id, atom_count)        │
│  - generate_on_user_request(concept_id, learner_id, type)       │
│  - proactive_generation(learner_id, upcoming_concepts)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AtomizerService                            │
│  src/ccna/atomizer_service.py                                   │
│  Generates atoms using LLM (Gemini)                             │
└─────────────────────────────────────────────────────────────────┘
```

### JITGenerationService

**Location:** `src/adaptive/jit_generator.py`

**Constructor:**

```python
JITGenerationService(
    session: Session | None = None,
    atomizer: AtomizerService | None = None,
)
```

**Key attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `_cache` | `dict[str, GenerationResult]` | In-memory cache of generated content |
| `_atomizer` | `AtomizerService` | Lazy-loaded content generation service |

### Data Models

**GenerationTrigger** (Enum):

| Value | Description |
|-------|-------------|
| `FAILED_QUESTION` | Learner failed, remediation exhausted |
| `MISSING_COVERAGE` | Concept has no atoms |
| `USER_REQUEST` | Learner asked for more practice |
| `PROACTIVE` | System predicted need |

**ContentType** (Enum):

| Value | Description |
|-------|-------------|
| `PRACTICE` | Flashcards, MCQ, cloze |
| `EXPLANATION` | Elaborative content |
| `WORKED_EXAMPLE` | Step-by-step walkthrough |

**GenerationRequest**:

```python
@dataclass
class GenerationRequest:
    concept_id: UUID
    trigger: GenerationTrigger
    content_types: list[ContentType] = [ContentType.PRACTICE]
    atom_count: int = 3
    learner_id: str | None = None
    fail_mode: str | None = None
    context: dict[str, Any] = {}
```

**GenerationResult**:

```python
@dataclass
class GenerationResult:
    concept_id: UUID
    atoms: list[GeneratedAtom]
    trigger: GenerationTrigger
    generation_time_ms: int
    from_cache: bool = False
    errors: list[str] = []
```

## Integration Flow

### Study Session Flow

```
Learner answers incorrectly
         │
         ▼
LearningEngine.submit_answer()
         │
         ├── NCDE diagnoses fail_mode (encoding, discrimination, etc.)
         │
         ▼
_get_cognitive_remediation()
         │
         ├── Select atoms matching fail_mode
         │
         ▼
_enhance_remediation_with_jit()
         │
         ├── Check: len(atoms) >= MIN_REMEDIATION_ATOMS (3)?
         │       │
         │       ├── Yes → Return existing atoms
         │       │
         │       └── No → Trigger JIT generation
         │                    │
         │                    ▼
         │             jit_generator.generate_for_failed_question()
         │                    │
         │                    ├── Map fail_mode → ContentType
         │                    ├── Generate atoms via AtomizerService
         │                    ├── Tag atoms: jit_generated, trigger:failed_question
         │                    ├── Save to database
         │                    │
         │                    ▼
         │             Return combined atom list
         │
         ▼
RemediationPlan with enhanced atoms
```

### RemediationRouter Integration

The `RemediationRouter` (line 54-56 in `remediation_router.py`) defines:

```python
MIN_REMEDIATION_ATOMS = 3
enable_jit: bool = True
```

Method `get_remediation_atoms_with_jit()`:

1. Query existing atoms for concept
2. If count >= `MIN_REMEDIATION_ATOMS`: return existing
3. If JIT enabled: generate missing atoms
4. Save generated atoms to `learning_atoms` table
5. Return combined list

## Triggers

### 1. Failed Question (Automatic)

Activates when a learner fails and existing remediation atoms < 3.

```python
result = await service.generate_for_failed_question(
    concept_id=concept_uuid,
    learner_id="user123",
    fail_mode="encoding_error",
    existing_atom_count=1,
)
```

The `existing_atom_count` determines how many new atoms to generate (fills gap to 5).

### 2. Missing Coverage (CLI)

Find and fill content gaps across concepts.

```bash
nls generate gaps
nls generate gaps --min-atoms 5
nls generate gaps --cluster abc123 --dry-run
```

Scans for concepts with fewer than `--min-atoms` and generates content.

### 3. User Request (CLI)

Generate content on-demand for a specific concept.

```bash
nls generate concept <uuid> --count 5
nls generate concept <uuid> --type explanation
nls generate concept <uuid> --dry-run
```

### 4. Proactive (API)

Pre-generate content for upcoming concepts.

```python
results = await service.proactive_generation(
    learner_id="user123",
    upcoming_concepts=[uuid1, uuid2, uuid3],
)
```

Limits to 3 concepts per call. Only generates if concept has < 3 atoms.

## Content Type Selection

### NCDE Fail Mode Mapping

The system maps cognitive failure modes to appropriate content types:

| Fail Mode | Content Types | Atom Types Prioritized |
|-----------|---------------|------------------------|
| `encoding_error` | EXPLANATION, PRACTICE | Flashcard, Cloze |
| `retrieval_error` | PRACTICE | Standard remediation |
| `discrimination_error` | PRACTICE | True/False, Compare, MCQ |
| `integration_error` | WORKED_EXAMPLE, PRACTICE | Parsons, Numeric, Sequence |
| `executive_error` | PRACTICE | (No generation - behavioral issue) |
| `fatigue_error` | None | (Suggest break - no generation) |

### Mapping Implementation

From `_fail_mode_to_content_types()` (line 463-480):

```python
mapping = {
    "encoding_error": [ContentType.EXPLANATION, ContentType.PRACTICE],
    "retrieval_error": [ContentType.PRACTICE],
    "discrimination_error": [ContentType.PRACTICE],
    "integration_error": [ContentType.WORKED_EXAMPLE, ContentType.PRACTICE],
    "executive_error": [ContentType.PRACTICE],
    "fatigue_error": [],  # Don't generate - suggest break
}
```

### Atom Type Prioritization

From `_map_content_types_to_atom_types()` (line 420-461):

**ContentType.PRACTICE:**
- Flashcard, MCQ, Cloze

**ContentType.EXPLANATION:**
- Flashcard (conceptual focus)

**ContentType.WORKED_EXAMPLE:**
- Parsons, Numeric

**Fail mode adjustments:**

- `discrimination_error`: Prepends True/False, Compare
- `encoding_error`: Prepends Flashcard, Cloze
- `integration_error`: Prepends Parsons, Numeric

## CLI Commands

### nls generate concept

Generate atoms for a specific concept.

```bash
nls generate concept <uuid> [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `concept_id` | Yes | Concept UUID |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--count`, `-c` | 3 | Number of atoms to generate |
| `--type`, `-t` | practice | Content type: practice, explanation, worked_example |
| `--dry-run`, `-n` | False | Preview without saving |

**Examples:**

```bash
# Generate 5 practice atoms
nls generate concept abc123-def456 --count 5

# Generate explanations for encoding errors
nls generate concept abc123-def456 --type explanation

# Preview without saving
nls generate concept abc123-def456 --dry-run
```

### nls generate gaps

Find and fill content gaps across the knowledge base.

```bash
nls generate gaps [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--cluster`, `-c` | None | Limit to specific cluster UUID |
| `--min-atoms` | 3 | Minimum atoms before gap is detected |
| `--dry-run`, `-n` | False | Preview without generating |

**Examples:**

```bash
# Find all gaps and prompt to fill
nls generate gaps

# Require 5 atoms minimum
nls generate gaps --min-atoms 5

# Preview gaps in a cluster
nls generate gaps --cluster abc123 --dry-run
```

### nls generate stats

Display statistics about JIT-generated content.

```bash
nls generate stats
```

**Output:**

```
┌────────────────────────────┬─────────┐
│ Metric                     │ Value   │
├────────────────────────────┼─────────┤
│ Total atoms                │ 5,432   │
│ JIT-generated              │ 234 (4.3%) │
│                            │         │
│ By trigger:                │         │
│   Failed question          │ 156     │
│   Missing coverage         │ 52      │
│   User request             │ 18      │
│   Proactive                │ 8       │
└────────────────────────────┴─────────┘
```

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| N/A | | | JIT uses LearningEngine and RemediationRouter defaults |

### Runtime Configuration

**LearningEngine:**

```python
engine = LearningEngine(
    session=db_session,
    enable_jit=True,  # Enable/disable JIT generation
)
```

**RemediationRouter:**

```python
router = RemediationRouter(
    session=db_session,
    enable_jit=True,  # Enable/disable JIT generation
)
```

### Constants

| Constant | Value | Location |
|----------|-------|----------|
| `MIN_REMEDIATION_ATOMS` | 3 | `RemediationRouter`, `LearningEngine` |
| `atom_count` (failed question) | 5 - existing | `JITGenerationService` |
| `atom_count` (proactive) | 3 - existing | `JITGenerationService` |
| Max proactive concepts | 3 | `JITGenerationService.proactive_generation()` |

## Generated Atom Metadata

All JIT-generated atoms receive the following tags:

| Tag | Description |
|-----|-------------|
| `jit_generated` | Identifies atom as machine-generated |
| `trigger:<type>` | Identifies trigger: `failed_question`, `missing_coverage`, `user_request`, `proactive` |

Example tags array:

```python
["jit_generated", "trigger:failed_question"]
```

### Database Storage

Generated atoms are inserted into `learning_atoms` with:

```sql
INSERT INTO learning_atoms (
    id, concept_id, card_id, atom_type, front, back,
    knowledge_type, tags, is_hydrated, fidelity_type,
    source_fact_basis, quality_score, created_at
) VALUES (...)
```

Default `quality_score` for JIT atoms: **75.0**

## Caching

JIT results are cached in-memory to avoid regeneration.

**Cache key format:**

```
{concept_id}:{trigger}:{sorted_content_types}
```

Example: `abc123:failed_question:explanation,practice`

**Cache operations:**

```python
# Clear cache for specific concept
cleared = service.clear_cache(concept_id=uuid)

# Clear entire cache
cleared = service.clear_cache()
```

Returns count of entries cleared.

## Error Handling

Generation errors are collected but do not block the flow:

```python
result = await service.generate_for_gap(request)

if result.errors:
    for error in result.errors:
        logger.warning(error)

# Atoms may be partial or empty on error
if result.atoms:
    # Use what was generated
```

Common error conditions:

| Condition | Behavior |
|-----------|----------|
| No source content for concept | Logs warning, returns empty atoms |
| AtomizerService failure | Logs error, continues with other types |
| Database save failure | Logs error, atom skipped |

## Performance

**Typical generation times:**

| Trigger | Atoms | Time |
|---------|-------|------|
| Failed question | 2-4 | 800-1500ms |
| Missing coverage | 5 | 1000-2000ms |
| User request | 3 | 600-1200ms |

**Optimization strategies:**

1. In-memory cache prevents regeneration
2. Proactive generation runs during idle periods
3. Batch operations limited to 3 concepts
4. Only generates missing count (not full set)

## See Also

- [CLI Commands Reference](./cli-commands.md) - Full CLI documentation
- [Database Schema](./database-schema.md) - `learning_atoms` table structure
- [Configuration](./configuration.md) - Environment variables
- [Generate Atoms](../how-to/generate-atoms.md) - How-to guide for atom generation
- [Struggle-Aware System](../explanation/struggle-aware-system.md) - Struggle-targeted generation
