# Database Schema Reference

Complete PostgreSQL schema documentation for Cortex.

---

## Overview

Cortex uses a **staging -> canonical** pattern:

```
Notion API
    |
    v
+-------------------+
| Staging Tables    |  <- Raw JSONB from Notion
| (stg_*)           |
+-------------------+
    |
    v
+-------------------+
| Cleaning Pipeline |
+-------------------+
    |
    v
+-------------------+
| Canonical Tables  |  <- Trusted, clean data
| (clean_*)         |
+-------------------+
```

---

## Staging Tables

Raw data from Notion. Ephemeral; can be rebuilt from Notion.

### stg_notion_flashcards

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `notion_page_id` | TEXT | NO (PK) | Notion page UUID |
| `raw_properties` | JSONB | NO | All Notion properties |
| `raw_content` | JSONB | YES | Page blocks |
| `last_synced_at` | TIMESTAMPTZ | NO | Last sync timestamp |
| `sync_hash` | TEXT | YES | MD5 hash for change detection |

### stg_notion_concepts

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `notion_page_id` | TEXT | NO (PK) | Notion page UUID |
| `raw_properties` | JSONB | NO | All Notion properties |
| `parent_type` | TEXT | YES | 'area', 'cluster', or NULL |
| `parent_notion_id` | TEXT | YES | Parent page ID |
| `last_synced_at` | TIMESTAMPTZ | NO | Last sync timestamp |

### stg_notion_modules

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `notion_page_id` | TEXT | NO (PK) | Notion page UUID |
| `raw_properties` | JSONB | NO | All Notion properties |
| `last_synced_at` | TIMESTAMPTZ | NO | Last sync timestamp |

---

## Canonical Tables - Knowledge Hierarchy

### clean_concept_areas

Top-level knowledge domains (L0).

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | UUID (PK) | gen_random_uuid() | Primary key |
| `notion_id` | TEXT (UK) | - | Source Notion ID |
| `name` | TEXT | - | Area name |
| `description` | TEXT | - | Description |
| `domain` | TEXT | - | Domain category |
| `display_order` | INT | 0 | Sort order |
| `created_at` | TIMESTAMPTZ | now() | Creation time |
| `updated_at` | TIMESTAMPTZ | now() | Last update |

### clean_concept_clusters

Thematic groupings within areas (L1).

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | UUID (PK) | gen_random_uuid() | Primary key |
| `notion_id` | TEXT (UK) | - | Source Notion ID |
| `concept_area_id` | UUID (FK) | - | Parent area |
| `name` | TEXT | - | Cluster name |
| `description` | TEXT | - | Description |
| `exam_weight` | DECIMAL(5,2) | - | Percentage weight |
| `display_order` | INT | 0 | Sort order |

### clean_concepts

Atomic knowledge units (L2).

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `id` | UUID (PK) | gen_random_uuid() | Primary key |
| `notion_id` | TEXT (UK) | - | Source Notion ID |
| `cluster_id` | UUID (FK) | - | Parent cluster |
| `name` | TEXT | - | Concept name |
| `definition` | TEXT | - | Formal definition |
| `status` | TEXT | 'to_learn' | Learning status |
| `dec_score` | DECIMAL(4,2) | - | Declarative score (0-10) |
| `proc_score` | DECIMAL(4,2) | - | Procedural score (0-10) |
| `app_score` | DECIMAL(4,2) | - | Application score (0-10) |

Status values: `to_learn`, `active`, `reviewing`, `mastered`, `stale`

---

## Canonical Tables - Curriculum

### clean_programs

Degree or certification paths.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `notion_id` | TEXT (UK) | Source Notion ID |
| `name` | TEXT | Program name |
| `description` | TEXT | Description |
| `status` | TEXT | Program status |
| `start_date` | DATE | Start date |
| `end_date` | DATE | End date |

### clean_tracks

Course-level sequences.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `notion_id` | TEXT (UK) | Source Notion ID |
| `program_id` | UUID (FK) | Parent program |
| `name` | TEXT | Track name |
| `display_order` | INT | Sort order |

### clean_modules

Week or chapter units.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `notion_id` | TEXT (UK) | Source Notion ID |
| `track_id` | UUID (FK) | Parent track |
| `name` | TEXT | Module name |
| `week_order` | INT | Week number |
| `status` | TEXT | Module status |

---

## Canonical Tables - Learning Atoms

### clean_atoms

Core learning content (flashcards, MCQs, etc.).

| Column | Type | Description |
|--------|------|-------------|
| **Identity** |
| `id` | UUID (PK) | Primary key |
| `notion_id` | TEXT | Source Notion ID (NULL if AI-generated) |
| `card_id` | TEXT (UK) | Human-readable ID (e.g., "NET-M1-015-DEC") |
| **Content** |
| `atom_type` | TEXT | Type: flashcard, cloze, mcq, etc. |
| `front` | TEXT | Question/prompt |
| `back` | TEXT | Answer/content |
| **Relationships** |
| `concept_id` | UUID (FK) | Related concept |
| `module_id` | UUID (FK) | Related module |
| **Quality** |
| `quality_score` | DECIMAL(3,2) | Score (0.00-1.00) |
| `is_atomic` | BOOLEAN | Passes atomicity check |
| `front_word_count` | INT | Question word count |
| `back_word_count` | INT | Answer word count |
| `atomicity_status` | TEXT | 'atomic', 'verbose', 'needs_split' |
| **Review Status** |
| `needs_review` | BOOLEAN | Flagged for review |
| `rewrite_count` | INT | Number of AI rewrites |
| **Anki Sync** |
| `anki_note_id` | BIGINT | Anki note ID |
| `anki_card_id` | BIGINT | Anki card ID |
| `anki_deck` | TEXT | Anki deck name |
| `anki_exported_at` | TIMESTAMPTZ | Export timestamp |
| `anki_synced_at` | TIMESTAMPTZ | Last sync with Anki |
| **Anki Review Stats** |
| `anki_ease_factor` | DECIMAL(4,3) | Ease factor (e.g., 2.500) |
| `anki_interval_days` | INT | Current interval |
| `anki_review_count` | INT | Total reviews |
| `anki_lapses` | INT | Times forgotten |
| `anki_due_date` | DATE | Next review date |
| **FSRS Metrics** |
| `anki_stability` | DECIMAL(8,2) | FSRS memory stability (days) |
| `retrievability` | DECIMAL(5,4) | Recall probability (0-1) |
| **Remediation** |
| `dont_know_count` | INT | Times user selected "I don't know" |
| **Source** |
| `source` | TEXT | Origin: notion, ai_batch, manual |
| `batch_id` | TEXT | Generation batch ID |
| **Timestamps** |
| `created_at` | TIMESTAMPTZ | Creation time |
| `updated_at` | TIMESTAMPTZ | Last update |

**Atom Types**: `flashcard`, `cloze`, `mcq`, `true_false`, `matching`, `parsons`, `numeric`

**Key Indexes**:
- `idx_clean_atoms_notion` (notion_id)
- `idx_clean_atoms_concept` (concept_id)
- `idx_clean_atoms_module` (module_id)
- `idx_clean_atoms_needs_review` (needs_review) WHERE needs_review = true
- `idx_clean_atoms_anki` (anki_note_id) WHERE anki_note_id IS NOT NULL
- `idx_clean_atoms_due` (anki_due_date) WHERE anki_due_date IS NOT NULL

---

## Review Queue

AI-generated content pending approval.

### review_queue

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `atom_type` | TEXT | Atom type |
| `front` | TEXT | Proposed question |
| `back` | TEXT | Proposed answer |
| `original_front` | TEXT | Before rewrite |
| `original_back` | TEXT | Before rewrite |
| `original_atom_id` | UUID (FK) | Source atom |
| `status` | TEXT | Review status |
| `source` | TEXT | Origin: notion_ai, vertex, gemini |
| `quality_score` | DECIMAL(3,2) | Quality score |
| `ai_confidence` | DECIMAL(3,2) | AI confidence |
| `approved_at` | TIMESTAMPTZ | Approval time |
| `approved_atom_id` | UUID (FK) | Created atom |

Status values: `pending`, `approved`, `rejected`, `edited`

---

## Audit Tables

### sync_log

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `sync_type` | TEXT | Type: notion_full, anki_push, etc. |
| `started_at` | TIMESTAMPTZ | Start time |
| `completed_at` | TIMESTAMPTZ | End time |
| `status` | TEXT | Status |
| `items_processed` | INT | Total processed |
| `items_added` | INT | Items added |
| `items_updated` | INT | Items updated |
| `error_message` | TEXT | Error details |

### cleaning_log

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `atom_id` | UUID (FK) | Affected atom |
| `operation` | TEXT | Operation type |
| `old_value` | JSONB | Before change |
| `new_value` | JSONB | After change |
| `performed_at` | TIMESTAMPTZ | Operation time |

---

## Views

### v_due_atoms

Atoms due for review with full context.

```sql
SELECT
    a.*,
    c.name as concept_name,
    m.name as module_name
FROM clean_atoms a
LEFT JOIN clean_concepts c ON a.concept_id = c.id
LEFT JOIN clean_modules m ON a.module_id = m.id
WHERE a.anki_due_date <= CURRENT_DATE
  AND a.is_atomic = true
  AND a.needs_review = false;
```

### v_concept_atom_stats

Atom statistics by concept.

```sql
SELECT
    c.id as concept_id,
    c.name as concept_name,
    COUNT(a.id) as total_atoms,
    COUNT(a.id) FILTER (WHERE a.is_atomic = true) as atomic_count,
    COUNT(a.id) FILTER (WHERE a.needs_review = true) as needs_review_count,
    COUNT(a.id) FILTER (WHERE a.anki_note_id IS NOT NULL) as in_anki_count,
    AVG(a.anki_ease_factor) as avg_ease
FROM clean_concepts c
LEFT JOIN clean_atoms a ON a.concept_id = c.id
GROUP BY c.id, c.name;
```

---

## Migrations

### Migration 017: Schema Cleanup and Missing FK

**Purpose**: Fix missing foreign key constraints and update views to use correct table names.

**Changes**:

1. **Foreign Key Addition**:
   ```sql
   ALTER TABLE learning_path_sessions
       ADD CONSTRAINT learning_path_sessions_target_cluster_id_fkey
       FOREIGN KEY (target_cluster_id) REFERENCES concept_clusters(id);
   ```

2. **View Updates**: Recreated views to use correct canonical table names:
   - `v_learner_progress` - uses `concepts`, `concept_clusters`
   - `v_suitability_mismatches` - uses `learning_atoms`
   - `v_session_analytics` - uses `concepts`, `concept_clusters`

**Table Name Conventions** (post-migration 013):

| Old Name | Canonical Name |
|----------|----------------|
| `clean_atoms` | `learning_atoms` |
| `clean_concepts` | `concepts` |
| `clean_concept_clusters` | `concept_clusters` |

### Migration 018: Remediation Notes System

**Purpose**: Add LLM-generated study notes with quality tracking for the Remediation Learning Loop.

**Tables Created**:

#### remediation_notes

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `section_id` | VARCHAR(20) (UK) | Section identifier (e.g., "11.2") |
| `module_number` | INT | Module number |
| `title` | VARCHAR(255) | Note title |
| `content` | TEXT | Markdown content |
| `source_hash` | VARCHAR(64) | SHA256 hash of source material |
| `read_count` | INT | Times note has been read |
| `user_rating` | INT | User rating (1-5) |
| `pre_error_rate` | FLOAT | Section error rate before first read |
| `post_error_rate` | FLOAT | Section error rate after reading |
| `effectiveness` | FLOAT (computed) | `pre_error_rate - post_error_rate` |
| `qualified` | BOOLEAN | Meets quality threshold |
| `is_stale` | BOOLEAN | Source material has changed |
| `created_at` | TIMESTAMP | Creation time |
| `last_read_at` | TIMESTAMP | Last read timestamp |
| `expires_at` | TIMESTAMP | Expiration (default: 30 days) |

**Indexes**:
- `idx_remediation_notes_section` (section_id)
- `idx_remediation_notes_qualified` (qualified, is_stale)
- `idx_remediation_notes_module` (module_number)

#### note_read_history

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `note_id` | UUID (FK) | Reference to remediation_notes |
| `user_id` | VARCHAR(100) | User identifier |
| `read_at` | TIMESTAMP | When note was read |
| `rating` | INT | Rating given at read time (1-5) |
| `section_error_rate_before` | FLOAT | Error rate at read time |
| `section_error_rate_after` | FLOAT | Error rate after next session |

**Column Additions**:

- `learning_atoms.dont_know_count` (INT): Tracks "I don't know" responses per atom

**Views Created**:

#### v_sections_needing_notes

Identifies sections with high error rates or "don't know" responses that may benefit from remediation notes:

```sql
SELECT
    section_id,
    module_number,
    section_title,
    total_atoms,
    struggling_atoms,
    avg_lapses,
    total_dont_knows,
    existing_note_id,
    note_qualified,
    note_stale
FROM v_sections_needing_notes
ORDER BY total_dont_knows DESC, avg_lapses DESC;
```

### Migration 019: Transfer Testing for Memorization Detection

**Purpose**: Detect rote memorization vs genuine understanding by tracking performance consistency across different question formats.

**Columns Added to `learning_atoms`**:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `format_seen` | JSONB | `{}` | Tracks which question formats have been presented |
| `transfer_queue` | TEXT[] | - | Queue of target formats for transfer testing |
| `accuracy_by_type` | JSONB | `{}` | Per-format accuracy statistics |
| `transfer_score` | FLOAT | NULL | Consistency score across formats (0-1) |
| `memorization_suspect` | BOOLEAN | FALSE | Flagged when T/F accuracy >> procedural accuracy |

**accuracy_by_type Format**:
```json
{
  "true_false": {"correct": 5, "total": 6},
  "mcq": {"correct": 7, "total": 10},
  "parsons": {"correct": 2, "total": 5}
}
```

**Indexes Created**:
- `idx_learning_atoms_transfer_queue` (GIN index on transfer_queue)
- `idx_learning_atoms_memorization_suspect` (partial index WHERE memorization_suspect = TRUE)

**Views Created**:

#### v_section_transfer_analysis

Aggregates transfer testing data at section level:

```sql
SELECT
    ccna_section_id,
    total_atoms,
    suspect_atoms,
    avg_transfer_score,
    avg_tf_accuracy,
    avg_parsons_accuracy,
    avg_mcq_accuracy
FROM v_section_transfer_analysis;
```

| Column | Description |
|--------|-------------|
| `ccna_section_id` | Section identifier |
| `total_atoms` | Number of atoms in section |
| `suspect_atoms` | Atoms flagged as memorization suspects |
| `avg_transfer_score` | Average transfer consistency (0-1) |
| `avg_tf_accuracy` | Average True/False accuracy |
| `avg_parsons_accuracy` | Average Parsons problem accuracy |
| `avg_mcq_accuracy` | Average MCQ accuracy |

**Memorization Detection Logic**:

An atom is flagged as `memorization_suspect = TRUE` when:
- Recognition accuracy (T/F + MCQ) >= procedural accuracy (Parsons + numeric) + 35%
- Sufficient data exists (3+ recognition responses, 2+ procedural responses)

### Migration 020: Dynamic Struggle Tracking

**Purpose**: Enable real-time struggle weight updates from NCDE diagnosis with full audit trail.

**Tables Created**:

#### struggle_weight_history

Audit trail of all struggle weight changes:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `module_number` | INT | CCNA module (1-17) |
| `section_id` | TEXT | Section ID (e.g., "5.1.2") or NULL for module-level |
| `static_weight` | DECIMAL(3,2) | Weight from YAML import |
| `ncde_weight` | DECIMAL(3,2) | Weight from real-time diagnosis |
| `combined_priority` | DECIMAL(5,3) | Calculated: `static * 3.0 + ncde * 2.0` |
| `trigger_type` | TEXT | `ncde_diagnosis`, `yaml_import`, `manual`, `decay` |
| `failure_mode` | TEXT | Detected failure mode (if ncde_diagnosis) |
| `atom_id` | UUID (FK) | Atom that triggered update |
| `session_accuracy` | DECIMAL(3,2) | Accuracy at time of update (0-1) |
| `cumulative_accuracy` | DECIMAL(3,2) | Overall accuracy for section |
| `error_count` | INT | Errors in session for this section |
| `session_id` | UUID (FK) | Link to learning_path_sessions |
| `created_at` | TIMESTAMPTZ | When recorded |

**Indexes**:
- `idx_swh_module` (module_number)
- `idx_swh_section` (section_id)
- `idx_swh_created` (created_at DESC)
- `idx_swh_trigger` (trigger_type)
- `idx_swh_module_time` (module_number, created_at DESC)

**Functions Created**:

#### get_failure_mode_multiplier(mode TEXT)

Returns weight multiplier based on failure mode severity:

| Mode | Multiplier | Rationale |
|------|------------|-----------|
| `encoding` | 0.25 | Never consolidated |
| `integration` | 0.20 | Facts don't connect |
| `retrieval` | 0.15 | Can't access stored knowledge |
| `discrimination` | 0.15 | Confusing similar concepts |
| `executive` | 0.05 | Careless error |
| `fatigue` | 0.02 | Cognitive exhaustion |

#### update_struggle_from_ncde(p_module, p_section, p_failure_mode, p_accuracy, p_atom_id, p_session_id)

Main entry point called by NCDE pipeline after each diagnosis:

```sql
-- Usage from Python:
SELECT update_struggle_from_ncde(
    5,                    -- module_number
    '5.1.2',              -- section_id
    'discrimination',     -- failure_mode
    0.0,                  -- accuracy (0 = wrong, 1 = correct)
    'uuid-of-atom',       -- atom_id
    'uuid-of-session'     -- session_id
);
```

**Algorithm**:
1. Get failure mode multiplier
2. If error (accuracy < 0.5): increase `ncde_weight` by `multiplier * (1 - accuracy)`
3. If correct: decay `ncde_weight` by 5%
4. Update `struggle_weights` table
5. Insert record to `struggle_weight_history`

#### decay_struggle_weights(p_decay_rate, p_min_age_days)

Periodic maintenance function to fade stale struggles:

```sql
-- Run weekly to decay weights not updated in 14 days by 10%
SELECT decay_struggle_weights(0.10, 14);
```

#### record_yaml_import(p_module, p_section, p_severity, p_weight)

Records YAML import events in history for tracking configuration changes.

**Views Created**:

#### v_struggle_evolution

Daily aggregation of struggle metrics over time:

```sql
SELECT
    module_number,
    section_id,
    date,
    avg_ncde_weight,
    avg_accuracy,
    diagnosis_count,
    error_count,
    correct_count
FROM v_struggle_evolution
ORDER BY date DESC, module_number;
```

#### v_struggle_summary

Current struggle status with 7-day trend analysis:

| Column | Description |
|--------|-------------|
| `module_number` | CCNA module |
| `section_id` | Section identifier |
| `severity` | Static severity level |
| `static_weight` | Weight from YAML |
| `ncde_weight` | Current dynamic weight |
| `priority_score` | Combined priority |
| `total_diagnoses` | All-time diagnosis count |
| `recent_errors_7d` | Errors in last 7 days |
| `avg_accuracy_7d` | Average accuracy (7 days) |
| `trend` | `improving`, `declining`, or `stable` |

### Migration 021: Socratic Dialogue Tables

**Purpose**: Schema for recording Socratic tutoring dialogues when learners say "I don't know".

**Tables Created**:

#### socratic_dialogues

Records each Socratic tutoring session:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL (PK) | Primary key |
| `atom_id` | VARCHAR(64) | Reference to atom being studied |
| `learner_id` | VARCHAR(64) | User identifier (default: 'default') |
| `started_at` | TIMESTAMP | Session start time |
| `ended_at` | TIMESTAMP | Session end time |
| `resolution` | VARCHAR(32) | Outcome: `self_solved`, `guided_solved`, `gave_up`, `revealed` |
| `scaffold_level_reached` | INT | Highest scaffold level used (0-4) |
| `turns_count` | INT | Number of dialogue turns |
| `total_duration_ms` | INT | Session duration in milliseconds |
| `detected_gaps` | TEXT | JSON array of prerequisite topic IDs |
| `created_at` | TIMESTAMP | Record creation time |

**Resolution Types**:

| Value | Meaning | Counted As |
|-------|---------|------------|
| `self_solved` | Learner figured it out at scaffold level 0 | Correct |
| `guided_solved` | Solved with hints (level 1-3) | Correct |
| `gave_up` | Learner requested skip | Incorrect |
| `revealed` | Full answer shown (level 4) | Incorrect |

#### dialogue_turns

Records individual turns within a Socratic dialogue:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL (PK) | Primary key |
| `dialogue_id` | INT (FK) | Reference to socratic_dialogues |
| `turn_number` | INT | Turn sequence number |
| `role` | VARCHAR(16) | `tutor` or `learner` |
| `content` | TEXT | Message content |
| `latency_ms` | INT | Response latency |
| `signal` | VARCHAR(32) | Cognitive signal: `confused`, `progressing`, `breakthrough`, `stuck` |
| `timestamp` | TIMESTAMP | Turn timestamp |

**Indexes**:
- `idx_dialogues_atom` (atom_id)
- `idx_dialogues_learner` (learner_id)
- `idx_dialogues_resolution` (resolution)
- `idx_turns_dialogue` (dialogue_id)

### Migration 022: User Flags

**Purpose**: Allow users to flag problematic questions during study sessions for later review.

**Tables Created**:

#### user_flags

Records user-reported issues with learning atoms:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `atom_id` | UUID (FK) | Reference to learning_atoms |
| `user_id` | TEXT | User identifier (future: real user system) |
| `flag_type` | TEXT | Issue type (see below) |
| `flag_reason` | TEXT | Optional user-provided explanation |
| `session_id` | UUID | Optional link to study session |
| `created_at` | TIMESTAMPTZ | When flagged |
| `resolved_at` | TIMESTAMPTZ | When resolved (NULL = unresolved) |
| `resolution_notes` | TEXT | Notes on how issue was resolved |
| `resolved_by` | TEXT | Who resolved the flag |

**Flag Types**:

| Type | Description |
|------|-------------|
| `wrong_answer` | Marked answer is incorrect |
| `ambiguous` | Question is unclear or has multiple interpretations |
| `typo` | Spelling or formatting error |
| `outdated` | Information is no longer accurate |
| `too_easy` | Not challenging enough |
| `too_hard` | Requires knowledge not covered |

**Indexes**:
- `idx_user_flags_unresolved` (resolved_at) WHERE resolved_at IS NULL
- `idx_user_flags_atom` (atom_id)
- `idx_user_flags_type` (flag_type)

**Views Created**:

#### v_flagged_atoms

Aggregates flags by atom for prioritized review:

```sql
SELECT
    atom_id,
    card_id,
    atom_type,
    front,
    flag_count,
    flag_types,          -- ARRAY of distinct flag types
    first_flagged,
    last_flagged
FROM v_flagged_atoms
WHERE flag_count >= 2    -- Multiple reports = higher priority
ORDER BY flag_count DESC;
```

### Migration 023: Source File Tracking

**Purpose**: Enable subdivided adaptive learning by tracking the source content file for each atom. Supports filtering sessions by module groups or ITN assessments.

**Columns Added to `learning_atoms`**:

| Column | Type | Description |
|--------|------|-------------|
| `source_file` | TEXT | Source content file (e.g., "CCNAModule1-3.txt", "ITNFinalPacketTracer.txt") |

**Indexes Created**:
- `idx_learning_atoms_source_file` (source_file) WHERE source_file IS NOT NULL

**Source File Values**:

| File | Content |
|------|---------|
| `CCNAModule1-3.txt` | Modules 1-3 (Foundations) |
| `CCNAModule4-7.txt` | Modules 4-7 (Physical & Data Link) |
| `CCNAModule8-10.txt` | Modules 8-10 (Network Layer Basics) |
| `CCNAModule11-13.txt` | Modules 11-13 (IP Addressing) |
| `CCNAModule14-15.txt` | Modules 14-15 (Transport & Application) |
| `CCNAModule16-17.txt` | Modules 16-17 (Security & Integration) |
| `ITNFinalPacketTracer.txt` | ITN Final Packet Tracer exam |
| `ITNPracticeFinalExam.txt` | ITN Practice Final Exam |
| `ITNPracticeTest.txt` | ITN Practice Test |
| `ITNSkillsAssessment.txt` | ITN Skills Assessment |

**Views Created**:

#### v_atoms_by_source

Atom counts by source file and type:

```sql
SELECT
    source_file,
    atom_count,
    mcq_count,
    tf_count,
    flashcard_count,
    cloze_count,
    parsons_count,
    matching_count,
    numeric_count
FROM v_atoms_by_source
ORDER BY source_file;
```

**Backfill Logic**:

The migration automatically backfills `source_file` based on `card_id` patterns:
- `NET-M{N}-*` or `CPE-M{N}-*` -> Corresponding CCNAModule file
- `ITN-FINAL-*` -> ITNFinalPacketTracer.txt
- `ITN-PRAC-*` -> ITNPracticeFinalExam.txt
- `ITN-PTEST-*` or `ITN-TEST-*` -> ITNPracticeTest.txt
- `ITN-SKILL-*` -> ITNSkillsAssessment.txt

**Usage**:

Filter study sessions by source file via the CLI:

```bash
# Use named preset
nls cortex start --source itn-final

# Or filter by modules which maps to source files internally
nls cortex start --modules 11-13
```

---

## See Also

- [Configuration Reference](configuration.md)
- [Architecture Overview](../explanation/architecture.md)
- [Transfer Testing Explanation](../explanation/transfer-testing.md)
- [Struggle-Aware System](../explanation/struggle-aware-system.md)
- [Session Remediation](../explanation/session-remediation.md) - Socratic dialogue system documentation
