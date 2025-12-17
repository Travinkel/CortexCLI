# Struggle-Aware Study System

This document explains how Cortex identifies and targets learning struggles through static configuration and dynamic real-time tracking.

---

## Overview

The Struggle-Aware System combines two complementary approaches:

1. **Static Configuration**: User-declared struggle areas from `struggles.yaml`
2. **Dynamic Tracking**: Real-time NCDE-diagnosed patterns recorded in `struggle_weight_history`

```
+-----------------+      +------------------+      +-----------------+
|  struggles.yaml | ---> | struggle_weights | ---> |  Study Session  |
|  (User Input)   |      |     (Static)     |      |  (Cortex CLI)   |
+-----------------+      +--------+---------+      +--------+--------+
                                 |                          |
                                 v                          v
+-----------------+      +------------------+      +------------------+
|  Atom Gen       | <--- |      NCDE        | ---> | History Audit    |
|  (Gemini)       |      |  Pipeline        |      | (struggle_weight |
|                 |      |                  |      |  _history)       |
+-----------------+      +--------+---------+      +------------------+
                                 |
                                 v
                        +------------------+
                        | Dynamic Weight   |
                        | Updates          |
                        | (ncde_weight)    |
                        +------------------+
```

### Key Components

| Component | Purpose | Update Frequency |
|-----------|---------|------------------|
| `struggles.yaml` | User-declared weak areas | Manual import |
| `struggle_weights` | Combined static + dynamic weights | Per-interaction |
| `struggle_weight_history` | Audit trail of all changes | Per-diagnosis |
| `update_struggle_from_ncde()` | PostgreSQL function for updates | Per-error |

---

## Theoretical Foundation

### Targeted Practice

Research suggests that identifying and addressing specific knowledge gaps is more effective than uniform review across all content. Dunlosky et al. (2013) rated "practice testing" and "distributed practice" as high-utility learning strategies, both of which are enhanced by focusing on weak areas.

### Metacognitive Awareness

Koriat (2012) documented the importance of accurate self-assessment in learning. The Struggle Map leverages learner self-knowledge to identify weak areas that may not yet be evident in performance data.

**Design Philosophy**: This system combines:
1. User-declared struggles (metacognitive input)
2. NCDE-diagnosed patterns (behavioral data)
3. FSRS retrievability (memory model)

The specific weighting formula and thresholds are design choices, not empirically validated optima.

---

## Struggle Map

### Definition

A struggle map is a user-defined configuration identifying weak areas:

```yaml
# struggles.yaml
chains:
  layer2_foundations:
    name: "Layer 2 Foundations"
    description: "Physical -> Ethernet/Switching -> MAC/Frames"
    priority: 1
    sequence: [4, 5, 7]

  lab_skills:
    name: "Packet Tracer Lab Skills"
    description: "Procedural skills for hands-on PT assessments"
    priority: 1
    parallel: true
    topics:
      - "Initial router configuration sequence"
      - "SSH configuration sequence"
      - "VLSM design for specific host requirements"

struggles:
  - module: 5
    chain: layer2_foundations
    chain_position: 2
    sections:
      - "5.1.1"  # LAN Protocols
      - "5.2.1"  # CAM Table
      - "5.3.1"  # Store-and-Forward
    severity: critical
    failure_modes: ["DISCRIMINATION", "INTEGRATION"]
    notes: "40+ failed cards trace here - YOUR WEAKEST AREA"
    topics:
      - "MAC Address structure (OUI + Device ID)"
      - "Frame Fields (Preamble, SFD, DA, SA, Type/Length, Data, FCS)"
```

### Prerequisite Chains

The `struggles.yaml` supports prerequisite chains that define study order:

| Chain | Modules | Description |
|-------|---------|-------------|
| `layer2_foundations` | 4 -> 5 -> 7 | Physical -> Ethernet -> MAC |
| `layer3_addressing` | 8 -> 10 -> 9 | IPv4 -> IPv6 -> ARP/ND |
| `upper_layers` | 11 -> 12 -> 13 | ICMP -> TCP/UDP -> Application |
| `cli_foundations` | 2 -> 3 | IOS Navigation -> OSI Model |
| `lab_skills` | (parallel) | Packet Tracer procedural skills |

### Severity Levels

| Severity | Weight | Multiplier | Description |
|----------|--------|------------|-------------|
| `critical` | 1.0 | 3.0x | Cannot pass exam without mastering |
| `high` | 0.75 | 2.0x | Significant weakness |
| `medium` | 0.5 | 1.5x | Needs attention |
| `low` | 0.25 | 1.0x | Minor gaps |

**Module Coverage**: All 17 CCNA modules (M1-M17) are tracked with current severity:

| Module | Content | Current Severity |
|--------|---------|------------------|
| M2 | IOS Navigation | critical (Q27 weakness) |
| M3 | OSI Model | critical (0% Communications) |
| M5 | Ethernet/Switching | critical (40+ failures) |
| M8 | IPv4 Subnetting | critical |
| M14 | Transport Layer | high (Q38, Q41 missed) |

### Failure Modes (Extended)

New failure modes for procedural and calculation errors:

| Mode | Name | Description | Target Atom Types |
|------|------|-------------|-------------------|
| `PACKET_WALKTHROUGH` | Frame Processing | Cannot trace packet through network | MATCHING, FLASHCARD |
| `CLI_MODE_MAPPING` | Command Mode Confusion | Wrong mode for commands | PARSONS, MCQ |
| `SUBNETTING_CALCULATION` | Subnet Math Errors | Network/broadcast/host calculation | NUMERIC |

### Wildcard Expansion

Section wildcards expand to all matching sections:
- `5.x` -> 5.1, 5.2, 5.3, ...
- `11.x` -> 11.1, 11.2, 11.3, ...
- `3.2.x` -> 3.2.1, 3.2.2, 3.2.3, ...

---

## Failure Mode Classification

Drawing on cognitive psychology research, we categorize common error patterns:

| Code | Name | Description | Atom Types |
|------|------|-------------|------------|
| FM1 | Confusions | Similar terms/concepts mixed | MCQ, Matching |
| FM2 | Process | Multi-step procedure errors | Parsons, Sequence |
| FM3 | Calculation | Numeric computation errors | Numeric |
| FM4 | Application | Cannot apply to scenarios | MCQ, Problem |
| FM5 | Vocabulary | Terminology recall failure | Flashcard, Cloze |
| FM6 | Comparison | Cannot distinguish related | Compare, Matching |
| FM7 | Troubleshooting | Cannot diagnose from symptoms | Problem, Prediction |

**Note**: These categories are heuristic classifications informed by error analysis research. Individual errors often involve multiple overlapping causes.

---

## Priority Calculation

The scheduler uses a weighted formula:

```
priority = (
    struggle_weight * 3.0 +      # User-declared struggles
    ncde_urgency * 2.0 +         # Real-time diagnosis
    fsrs_retrievability * 1.0    # Spaced repetition
)
```

**Design Note**: We chose these multipliers (3.0, 2.0, 1.0) to prioritize user-declared struggles, then diagnosed issues, then standard spaced repetition signals. These weights reflect our judgment that explicit self-identified weaknesses deserve highest attention, but they are not empirically validated. You may need to adjust these weights based on your learning outcomes.

### Example Calculation

| Factor | Value | Weight | Contribution |
|--------|-------|--------|--------------|
| Struggle weight | 0.8 (high) | 3.0 | 2.4 |
| NCDE urgency | 0.5 (recent errors) | 2.0 | 1.0 |
| Retrievability | 0.3 (overdue) | 1.0 | 0.7 |
| **Total** | | | **4.1** |

---

## CLI Commands

### Import Struggle Map

```bash
nls cortex struggle --import struggles.yaml
```

### View Current Struggles

```bash
nls cortex struggle --show
```

Output:
```
Struggle Heatmap
================

Module 5:  [====      ] 40% (Binary)
Module 11: [========  ] 80% (Subnetting) CRITICAL
Module 12: [======    ] 60% (IPv6)

Failure Modes:
  FM3 (Calculation): 45%
  FM1 (Confusions): 30%
  FM5 (Vocabulary): 25%
```

### Interactive Configuration

```bash
nls cortex struggle --interactive
```

### Set Modules Directly

```bash
nls cortex struggle --modules 11,12,14
```

### Study Struggle Areas

```bash
nls cortex start --struggle-focus
```

---

## NCDE Integration

### Real-Time Updates

During study sessions, the NCDE Pipeline processes each interaction:

1. **Feature Extraction**: Normalize response time, hesitation, selection changes
2. **Confusion Matrix Update**: Track pattern separation index (PSI)
3. **Fatigue Calculation**: Multi-dimensional fatigue vector
4. **Cognitive Diagnosis**: Classify failure mode
5. **Struggle Weight Update**: Call `update_struggle_from_ncde()` PostgreSQL function

### NCDE Pipeline Integration

The `NCDEPipeline.process()` method integrates with struggle tracking:

```python
# src/adaptive/ncde_pipeline.py
diagnosis, strategy = pipeline.process(raw_event, context)

# Prepare struggle update data
update_data = prepare_struggle_update(
    diagnosis=diagnosis,
    module_number=module,
    section_id=section,
    is_correct=raw_event.is_correct,
    atom_id=raw_event.atom_id,
    session_id=context.session_id,
)

# Update database (async or sync)
await update_struggle_weight_async(db_session, update_data)
```

### Failure Mode Multipliers

Different failure modes indicate different severity of knowledge gaps:

| Failure Mode | Multiplier | Rationale |
|--------------|------------|-----------|
| `encoding` | 0.25 | Never consolidated - serious gap |
| `integration` | 0.20 | Facts don't connect - needs scaffolding |
| `retrieval` | 0.15 | Stored but can't access - needs practice |
| `discrimination` | 0.15 | Confusing similar concepts - needs contrast |
| `executive` | 0.05 | Careless error - not a knowledge gap |
| `fatigue` | 0.02 | Cognitive exhaustion - not a knowledge gap |

### Weight Update Algorithm

```sql
-- PostgreSQL function: update_struggle_from_ncde()
IF p_accuracy < 0.5 THEN
    -- Error: increase weight by multiplier * (1 - accuracy)
    v_new_ncde := LEAST(1.0, v_current_ncde + v_multiplier * (1 - p_accuracy));
ELSE
    -- Correct: decay weight by 5%
    v_new_ncde := GREATEST(0.0, v_current_ncde * 0.95);
END IF;
```

### Weight Decay

Struggles fade over time as mastery improves:

```sql
-- Run weekly via: SELECT decay_struggle_weights(0.10, 14);
-- Parameters: decay_rate (10%), min_age_days (14)

UPDATE struggle_weights
SET ncde_weight = GREATEST(0.0, ncde_weight * (1 - p_decay_rate))
WHERE last_diagnosis_at < NOW() - (p_min_age_days || ' days')::INTERVAL;
```

---

## Dynamic Struggle Tracking (Migration 020)

### Architecture

The Dynamic Struggle Tracking system records every struggle weight change for analysis and audit:

```
+----------------+       +---------------------+       +----------------------+
| NCDE Pipeline  | ----> | update_struggle_    | ----> | struggle_weight_     |
| (per response) |       | from_ncde()         |       | history              |
+----------------+       +---------------------+       +----------------------+
                                 |
                                 v
                         +---------------------+
                         | struggle_weights    |
                         | (ncde_weight)       |
                         +---------------------+
```

### struggle_weight_history Table

Records every weight change with full context:

| Column | Type | Description |
|--------|------|-------------|
| `module_number` | INT | CCNA module (1-17) |
| `section_id` | TEXT | Section ID (e.g., "5.1.2") or NULL for module-level |
| `static_weight` | DECIMAL | From YAML import |
| `ncde_weight` | DECIMAL | From real-time diagnosis |
| `combined_priority` | DECIMAL | `static * 3.0 + ncde * 2.0` |
| `trigger_type` | TEXT | `ncde_diagnosis`, `yaml_import`, `manual`, `decay` |
| `failure_mode` | TEXT | Which failure mode detected |
| `atom_id` | UUID | Which atom triggered this |
| `session_accuracy` | DECIMAL | Accuracy at time of update (0-1) |
| `session_id` | UUID | Link to study session |
| `created_at` | TIMESTAMPTZ | When recorded |

### StruggleWeightHistory SQLAlchemy Model

```python
# src/db/models/adaptive.py
class StruggleWeightHistory(Base):
    __tablename__ = "struggle_weight_history"

    id: Mapped[UUID]
    module_number: Mapped[int]
    section_id: Mapped[str | None]
    static_weight: Mapped[Decimal | None]
    ncde_weight: Mapped[Decimal | None]
    combined_priority: Mapped[Decimal | None]
    trigger_type: Mapped[str]  # 'ncde_diagnosis', 'yaml_import', 'manual', 'decay'
    failure_mode: Mapped[str | None]
    atom_id: Mapped[UUID | None]
    session_accuracy: Mapped[Decimal | None]
    created_at: Mapped[datetime]
```

### Analytics Views

**v_struggle_evolution**: Daily aggregation of struggle metrics:

```sql
SELECT
    module_number,
    section_id,
    DATE_TRUNC('day', created_at) as date,
    AVG(ncde_weight) as avg_ncde_weight,
    AVG(session_accuracy) as avg_accuracy,
    COUNT(*) FILTER (WHERE session_accuracy < 0.5) as error_count
FROM struggle_weight_history
WHERE trigger_type = 'ncde_diagnosis'
GROUP BY module_number, section_id, DATE_TRUNC('day', created_at);
```

**v_struggle_summary**: Current status with 7-day trend:

```sql
SELECT
    module_number,
    section_id,
    severity,
    static_weight,
    ncde_weight,
    priority_score,
    recent_errors_7d,
    avg_accuracy_7d,
    CASE
        WHEN trend_ncde > ncde_weight THEN 'improving'
        WHEN trend_ncde < ncde_weight THEN 'declining'
        ELSE 'stable'
    END as trend
FROM v_struggle_summary
ORDER BY priority_score DESC;
```

### Python Integration Functions

```python
# src/adaptive/ncde_pipeline.py

def prepare_struggle_update(
    diagnosis: CognitiveDiagnosis,
    module_number: int,
    section_id: str | None,
    is_correct: bool,
    atom_id: str | None = None,
    session_id: str | None = None,
) -> StruggleUpdateData:
    """Prepare data for database update from NCDE diagnosis."""

async def update_struggle_weight_async(
    db_session: Any,
    update_data: StruggleUpdateData,
) -> None:
    """Update struggle weights via PostgreSQL function (async)."""

def update_struggle_weight_sync(
    db_connection: Any,
    update_data: StruggleUpdateData,
) -> None:
    """Update struggle weights via PostgreSQL function (sync)."""
```

---

## Anki Integration

Use Anki's filtered deck feature with section tags:

```
# Critical calculation modules
Search: (tag:CCNA::M5* OR tag:CCNA::M11* OR tag:CCNA::M12*) -is:suspended

# Specific weak sections
Search: (tag:CCNA::M11::S3* OR tag:CCNA::M11::S5*) -is:suspended

# Due items from struggle areas
Search: (tag:CCNA::M5* OR tag:CCNA::M11*) is:due
```

---

## Database Schema

### struggle_weights Table

```sql
CREATE TABLE struggle_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_number INTEGER NOT NULL,
    section_id TEXT,
    severity TEXT NOT NULL,           -- critical, high, medium, low
    weight DECIMAL(3,2) NOT NULL,     -- 0.0-1.0
    failure_modes TEXT[],             -- ['FM1', 'FM3']
    notes TEXT,
    ncde_weight DECIMAL(3,2),         -- Computed from diagnosis
    last_diagnosis_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(module_number, section_id)
);
```

### v_struggle_priority View

```sql
CREATE VIEW v_struggle_priority AS
SELECT
    ca.id as atom_id,
    ca.card_id,
    cs.module_number,
    cs.section_id,
    COALESCE(sw.weight, 0.3) as struggle_weight,
    COALESCE(sw.ncde_weight, 0.0) as ncde_weight,
    COALESCE(ca.retrievability, 0.5) as retrievability,
    (
        COALESCE(sw.weight, 0.3) * 3.0 +
        COALESCE(sw.ncde_weight, 0.0) * 2.0 +
        (1 - COALESCE(ca.retrievability, 0.5)) * 1.0
    ) as priority_score
FROM clean_atoms ca
JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
LEFT JOIN struggle_weights sw ON sw.module_number = cs.module_number
ORDER BY priority_score DESC;
```

---

## Individual Differences

**Important caveat**: Struggle identification and remediation effectiveness vary across individuals:

- **Self-assessment accuracy**: Some learners accurately identify weaknesses; others exhibit overconfidence or underconfidence (Koriat, 2012)
- **Failure mode overlap**: Your errors may not fit neatly into predefined categories
- **Optimal prioritization**: The weight formula may need adjustment for your learning style
- **Decay rates**: Memory consolidation timelines vary between individuals

Consider adjusting:
- Severity weights based on observed impact on your performance
- Decay parameters based on how quickly you retain improvements
- Priority weights based on which signals best predict your future performance

---

## Implementation Status

### Completed

- Struggle map import from `struggles.yaml`
- YAML schema with prerequisite chains and wildcards
- Priority formula integration (`static * 3.0 + ncde * 2.0`)
- Manual mode with section selection
- JSON telemetry logging
- All 17 CCNA modules (M1-M17) in `struggle_weights` table
- Struggle heatmap sorted by module number (M1-M17)
- **Dynamic Struggle Tracking (Migration 020)**:
  - `struggle_weight_history` table for audit trail
  - `update_struggle_from_ncde()` PostgreSQL function
  - `decay_struggle_weights()` function for stale weight cleanup
  - `record_yaml_import()` function for import tracking
  - `v_struggle_evolution` view for daily metrics
  - `v_struggle_summary` view with 7-day trend analysis
- **NCDE Pipeline Integration**:
  - `StruggleUpdateData` dataclass
  - `prepare_struggle_update()` helper function
  - `update_struggle_weight_async()` for async sessions
  - `update_struggle_weight_sync()` for sync connections
- **Real-Time Session Updates**:
  - `CortexSession._update_struggle_weight()` calls PostgreSQL function after each interaction
  - Dynamic weights update based on NCDE diagnosis during active study sessions
  - Automatic tracking of failure modes and accuracy per section
- **New Failure Modes**:
  - `PACKET_WALKTHROUGH` for frame processing errors
  - `CLI_MODE_MAPPING` for command mode confusion
  - `SUBNETTING_CALCULATION` for subnet math errors
- **Lab Skills Chain**: Packet Tracer procedural knowledge tracking

### Planned

- Struggle progress dashboard with trend visualization
- Failure mode visualization (heatmap by module/section)
- Auto-detection without explicit user input
- Integration with Anki review statistics

---

## Configuration

```bash
# Struggle weights (design choices)
STRUGGLE_CRITICAL_WEIGHT=1.0
STRUGGLE_HIGH_WEIGHT=0.8
STRUGGLE_MEDIUM_WEIGHT=0.5
STRUGGLE_LOW_WEIGHT=0.3

# Priority formula weights (design choices, not empirically derived)
STRUGGLE_PRIORITY_WEIGHT=3.0
NCDE_PRIORITY_WEIGHT=2.0
FSRS_PRIORITY_WEIGHT=1.0

# Decay settings (design choices)
STRUGGLE_DECAY_DAYS=14
STRUGGLE_DECAY_RATE=0.9
```

---

## References

### Primary Research

- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students' learning with effective learning techniques. *Psychological Science in the Public Interest, 14*(1), 4-58.
- Koriat, A. (2012). The self-consistency model of subjective confidence. *Psychological Review, 119*(1), 80-113.
- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about knowing* (pp. 185-205). MIT Press.
- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249-255.

---

## See Also

- [Cognitive Diagnosis](cognitive-diagnosis.md) - NCDE pipeline integration
- [Adaptive Learning](adaptive-learning.md) - Priority-based scheduling
- [Database Schema](../reference/database-schema.md) - Migration 020 reference
- [Generate Atoms](../how-to/generate-atoms.md) - Struggle-targeted generation
- [Maximize Retention](../how-to/maximize-retention.md)
