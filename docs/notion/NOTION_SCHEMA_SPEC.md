# Cortex 2.0 Notion Schema Specification

> **Purpose**: Define the optimal Notion database structure for the Cortex 2.0 Notion-centric learning system.
>
> **Principle**: Notion is the Source of Truth. PostgreSQL mirrors Notion, not vice versa.

---

## Current Database Inventory

Based on `.env` configuration:

| Database | Source ID | Current Role | Cortex 2.0 Role |
|----------|-----------|--------------|-----------------|
| Flashcards | `2a2f8e54...` | Learning atoms | **Primary: All-Atom Master** |
| Concepts | `1c6b6a33...` | L2 concepts | Merge into hierarchy |
| Superconcepts | `42c919da...` | L1 clusters | Merge into hierarchy |
| Subconcepts | `a176306b...` | L3 sub-concepts | Merge into Flashcards |
| Modules | `97623fb6...` | Curriculum units | Keep |
| Tracks | `381b80ea...` | Learning paths | Keep |
| Programs | `66678bdc...` | Degree paths | Keep (optional) |
| Quizzes | `c91cc76d...` | Assessments | Keep |
| Activities | `455dea65...` | Exercises | Keep |
| Sessions | `74205a0f...` | Study logs | Keep |
| Critical Skills | `6df76f06...` | Procedural mastery | Merge into Flashcards |
| Mental Models | `60cfc859...` | Meta-learning | Keep |
| Resources | `a22bff04...` | External links | Keep |
| Evidence | `1361d8f1...` | Research citations | Keep |
| Recall SRS | `bc4b756b...` | Anki sync staging | Keep (internal) |

### Neuroplasticity Databases (Separate Domain)
| Database | Source ID | Role |
|----------|-----------|------|
| Brain Regions | `d6b27a3a...` | Neural systems |
| Training Protocols | `118f5a70...` | Intervention protocols |
| Assessments | `a9e52b7f...` | Cognitive tests |
| Evidence Base | `d095e3ba...` | Research evidence |

---

## Recommended Schema Architecture

### Decision: Unified vs. Federated

**Recommendation: Hybrid Approach**

- **Flashcards** becomes the unified "All-Atom Master Database" (L3 atoms + L2 concepts inline)
- **Superconcepts** becomes a lightweight "Knowledge Areas" reference (L0/L1 only)
- **Subconcepts** and **Critical Skills** merge INTO Flashcards
- Keep **Modules/Tracks/Programs** as curriculum structure

This preserves your existing investment while enabling Cortex 2.0's graph algorithms.

---

## Database 1: Flashcards (All-Atom Master)

> The heart of Cortex 2.0. Every reviewable learning unit lives here.

### Required Properties (Add These)

| Property | Type | Purpose | Default |
|----------|------|---------|---------|
| `Z_Score` | Number | Computed attention urgency | `0.0` |
| `Z_Activation` | Checkbox | Focus Stream membership | `false` |
| `Memory_State` | Status | Learning stage | `NEW` |
| `PSI` | Number | Pattern Separation Index | `0.5` |
| `PFIT` | Number | P-FIT Integration Index | `0.5` |
| `Stability` | Number | FSRS stability (days) | `0.0` |
| `Difficulty` | Number | FSRS difficulty | `0.3` |
| `Last_Review` | Date | Last interaction | - |
| `Next_Review` | Date | Computed due date | - |
| `Review_Count` | Number | Total reviews | `0` |
| `Lapses` | Number | Incorrect count | `0` |
| `Quality_Grade` | Select | Atomicity grade | - |
| `Hierarchy_Level` | Select | Knowledge level | `Atom` |
| `Launch_PLM` | Formula | PLM deep link | See below |
| `Prerequisites` | Relation | Self-relation | - |
| `Confusables` | Relation | Self-relation | - |
| `Parent_Concept` | Relation | Link to Superconcepts | - |

### Existing Properties (Keep/Rename)

| Current Name | Action | New Name (if changed) |
|--------------|--------|----------------------|
| `Name` / `Question` | Keep | - |
| `Answer` | Keep | - |
| `Card Type` / `Type` | Keep | `Atom_Type` |
| `Module` | Keep | - |
| `Concepts` | Rename | `Parent_Concept` |
| `Status` | Rename | `Memory_State` |
| `Card ID` | Keep | - |

### Status Options for Memory_State

Configure as **Status** property with these options:

| Status | Color | Group |
|--------|-------|-------|
| `NEW` | Gray | To Do |
| `LEARNING` | Blue | In Progress |
| `REVIEW` | Yellow | In Progress |
| `MASTERED` | Green | Complete |
| `SUSPENDED` | Red | Complete |

### Select Options for Atom_Type

| Option | Color | Description |
|--------|-------|-------------|
| `Flashcard` | Blue | Standard Q&A |
| `Definition` | Purple | Core definition |
| `Theorem` | Indigo | Mathematical theorem |
| `Procedure` | Orange | Step-by-step process |
| `Fact` | Gray | Atomic fact |
| `Example` | Green | Worked example |
| `Counter_Example` | Red | Boundary case |
| `Adversarial_Lure` | Pink | Confusable item |
| `MCQ` | Teal | Multiple choice |
| `Cloze` | Brown | Fill-in-blank |

### Select Options for Hierarchy_Level

| Option | Color | Description |
|--------|-------|-------------|
| `Atom` | Blue | L3: Reviewable unit |
| `Concept` | Purple | L2: Concept grouping |
| `Skill` | Orange | Critical skill |

### Formula for Launch_PLM

```
"cortex://plm/" + prop("Card ID")
```

Or if using Notion page ID:
```
"cortex://plm/" + id()
```

---

## Database 2: Superconcepts (Knowledge Areas)

> Lightweight hierarchy for L0 (Areas) and L1 (Clusters)

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Concept name |
| `Level` | Select | `Area` or `Cluster` |
| `Parent` | Relation | Self-relation to parent |
| `Children` | Relation | Self-relation (reverse) |
| `Atoms` | Relation | Link to Flashcards |
| `Atom_Count` | Rollup | Count of atoms |
| `Mastery` | Rollup | Avg mastery of atoms |
| `Description` | Rich Text | Explanation |
| `Icon` | Text | Emoji for display |

### Select Options for Level

| Option | Color |
|--------|-------|
| `Area` | Purple |
| `Cluster` | Blue |

---

## Database 3: Modules (Curriculum Units)

> Weekly/chapter study units

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Module title |
| `Order` | Number | Sequence number |
| `Track` | Relation | Parent track |
| `Atoms` | Relation | Linked flashcards |
| `Duration_Hours` | Number | Estimated time |
| `Mastery` | Rollup | Avg Z_Score of atoms |
| `Completion` | Formula | % atoms mastered |
| `Start_Date` | Date | Scheduled start |
| `Status` | Status | Not Started / In Progress / Complete |

---

## Database 4: Tracks (Learning Paths)

> Course-level sequences

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Track name |
| `Modules` | Relation | Child modules |
| `Program` | Relation | Parent program |
| `Total_Atoms` | Rollup | Count via modules |
| `Progress` | Formula | % complete |
| `Active` | Checkbox | Currently studying |
| `Description` | Rich Text | Track overview |
| `Certification` | Text | Target cert |

---

## Database 5: Sessions (Study Logs)

> Automatic session tracking from Cortex CLI

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Session_ID` | Title | Unique identifier |
| `Start_Time` | Date | Session start |
| `End_Time` | Date | Session end |
| `Duration_Minutes` | Formula | End - Start |
| `Atoms_Reviewed` | Number | Count |
| `Correct` | Number | Correct answers |
| `Accuracy` | Formula | Correct / Reviewed |
| `Avg_Response_ms` | Number | Response time |
| `Diagnoses` | Multi-Select | Fail modes |
| `Remediations` | Multi-Select | Strategies |
| `Fatigue_Peak` | Number | Max fatigue |
| `Mode` | Select | `Normal` / `War` / `PLM` |

### Multi-Select for Diagnoses

| Option | Color |
|--------|-------|
| `ENCODING_ERROR` | Red |
| `RETRIEVAL_ERROR` | Orange |
| `DISCRIMINATION_ERROR` | Yellow |
| `INTEGRATION_ERROR` | Purple |
| `EXECUTIVE_ERROR` | Indigo |
| `FATIGUE_ERROR` | Gray |

### Multi-Select for Remediations

| Option | Color |
|--------|-------|
| `StandardFlow` | Blue |
| `MicroBreak` | Green |
| `ForceZ` | Orange |
| `PLM` | Purple |
| `ContrastiveLure` | Pink |

---

## Database 6: Projects (Learning Focus)

> **NEW DATABASE** - For Z-Score project relevance signal P(a)

### Properties

| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Project name |
| `Description` | Rich Text | Goal |
| `Target_Concepts` | Relation | Link to Superconcepts |
| `Target_Atoms` | Relation | Link to Flashcards |
| `Deadline` | Date | Target date |
| `Active` | Checkbox | Currently active |
| `Priority` | Number | Weight (1-10) |
| `Status` | Status | Planning / Active / Complete |

---

## Notion Views Configuration

### Flashcards Database Views

#### 1. Focus Stream (Primary Study View)
```
Filter: Z_Activation = ✓ AND Memory_State ≠ SUSPENDED
Sort: Z_Score DESC
Show: Question, Atom_Type, Memory_State, PSI, Next_Review, Launch_PLM
```

#### 2. Due Today
```
Filter: Next_Review ≤ Today AND Memory_State IN [LEARNING, REVIEW]
Sort: Z_Score DESC
```

#### 3. New Atoms
```
Filter: Memory_State = NEW
Sort: Created time DESC
```

#### 4. Struggling (Force Z Candidates)
```
Filter: PSI < 0.4 OR Lapses ≥ 3
Sort: Lapses DESC
```

#### 5. Mastered
```
Filter: Memory_State = MASTERED
Group by: Parent_Concept
```

#### 6. By Module (Curriculum View)
```
Filter: Hierarchy_Level = Atom
Group by: Module
Sort: Order ASC (within group)
```

#### 7. Quality Audit
```
Filter: Quality_Grade IN [D, F] OR Quality_Grade is empty
Sort: Created time ASC
```

#### 8. Confusables Network
```
Filter: Confusables is not empty
Show: Question, Confusables, PSI
```

---

## Property Formulas

### Next_Review (Flashcards)
```
if(
  prop("Memory_State") == "NEW",
  now(),
  if(
    prop("Memory_State") == "MASTERED",
    dateAdd(prop("Last_Review"), prop("Stability"), "days"),
    dateAdd(prop("Last_Review"), 1, "days")
  )
)
```

### Completion (Modules)
```
round(
  prop("Mastery") / 100 * 100
) + "%"
```

### Duration_Minutes (Sessions)
```
dateBetween(prop("End_Time"), prop("Start_Time"), "minutes")
```

### Accuracy (Sessions)
```
if(
  prop("Atoms_Reviewed") > 0,
  round(prop("Correct") / prop("Atoms_Reviewed") * 100) + "%",
  "N/A"
)
```

---

## Migration Checklist

### Phase 1: Add Cortex 2.0 Properties to Flashcards
- [ ] Add `Z_Score` (Number, default 0)
- [ ] Add `Z_Activation` (Checkbox, default false)
- [ ] Add `Memory_State` (Status with options)
- [ ] Add `PSI` (Number, default 0.5)
- [ ] Add `PFIT` (Number, default 0.5)
- [ ] Add `Stability` (Number, default 0)
- [ ] Add `Difficulty` (Number, default 0.3)
- [ ] Add `Last_Review` (Date)
- [ ] Add `Next_Review` (Date)
- [ ] Add `Review_Count` (Number, default 0)
- [ ] Add `Lapses` (Number, default 0)
- [ ] Add `Quality_Grade` (Select)
- [ ] Add `Hierarchy_Level` (Select, default "Atom")
- [ ] Add `Launch_PLM` (Formula)
- [ ] Add `Prerequisites` (Relation to self)
- [ ] Add `Confusables` (Relation to self)

### Phase 2: Rename/Update Existing Properties
- [ ] Rename `Status` → `Memory_State` (or map in config)
- [ ] Rename `Concepts` → `Parent_Concept`
- [ ] Ensure `Card Type` → `Atom_Type` options match

### Phase 3: Create Views
- [ ] Create "Focus Stream" view
- [ ] Create "Due Today" view
- [ ] Create "Struggling" view
- [ ] Create "By Module" view

### Phase 4: Create Projects Database
- [ ] Create new "Projects" database
- [ ] Add relation to Flashcards
- [ ] Add relation to Superconcepts

### Phase 5: Merge Subconcepts/Critical Skills
- [ ] Export Subconcepts to Flashcards with `Hierarchy_Level = Concept`
- [ ] Export Critical Skills to Flashcards with `Atom_Type = Procedure`
- [ ] Archive old databases

---

## Environment Variable Mapping

Update `.env` to match new schema:

```env
# Primary Databases
FLASHCARDS_DB_ID="2a2f8e54a33080f49f33e59e1d9fc23d"
SUPERCONCEPTS_DB_ID="42c919da-cc06-445f-b481-bf20a7584bce"
MODULES_DB_ID="97623fb6-1e11-4574-ab11-121581e1107c"
TRACKS_DB_ID="381b80ea-833e-49e1-ae2f-b8fe7ae14481"
PROGRAMS_DB_ID="66678bdc-cf5a-40c7-b776-1a7b94be67e7"
SESSIONS_DB_ID="74205a0f-fa49-4143-a0bc-0abfc8d0cb71"
PROJECTS_DB_ID=""  # Create new

# Supporting Databases
QUIZZES_DB_ID="c91cc76d-73b0-4ced-8ad5-64f1452c14ae"
ACTIVITIES_DB_ID="455dea65-d587-4219-b4de-54cc395a0c8c"
MENTAL_MODELS_DB_ID="60cfc859-de09-4681-97fb-f1b5353b9806"
RESOURCES_DB_ID="a22bff04-ab0f-4d13-880b-8c371ac1bc71"
EVIDENCE_DB_ID="1361d8f1-b0b0-4316-ba81-5b64bae7a16a"
CRITICAL_SKILLS_DB_ID="6df76f06-603d-4c04-a618-558c7c07d347"

# Cortex 2.0 Property Names
NOTION_PROP_Z_SCORE="Z_Score"
NOTION_PROP_Z_ACTIVATION="Z_Activation"
NOTION_PROP_MEMORY_STATE="Memory_State"
NOTION_PROP_PSI="PSI"
NOTION_PROP_PFIT="PFIT"
NOTION_PROP_STABILITY="Stability"
NOTION_PROP_DIFFICULTY="Difficulty"
NOTION_PROP_LAST_REVIEW="Last_Review"
NOTION_PROP_NEXT_REVIEW="Next_Review"
NOTION_PROP_REVIEW_COUNT="Review_Count"
NOTION_PROP_LAPSES="Lapses"
NOTION_PROP_QUALITY_GRADE="Quality_Grade"
NOTION_PROP_HIERARCHY_LEVEL="Hierarchy_Level"
NOTION_PROP_ATOM_TYPE="Atom_Type"
NOTION_PROP_PREREQUISITES="Prerequisites"
NOTION_PROP_CONFUSABLES="Confusables"
NOTION_PROP_PARENT_CONCEPT="Parent_Concept"
```

---

## Summary

### Databases to Keep (6 Core)
1. **Flashcards** - All-Atom Master (enhanced)
2. **Superconcepts** - Knowledge Areas (L0/L1)
3. **Modules** - Curriculum units
4. **Tracks** - Learning paths
5. **Sessions** - Study logs
6. **Projects** - NEW: Learning focus

### Databases to Keep (Supporting)
- Quizzes, Activities, Mental Models, Resources, Evidence
- Neuroplasticity suite (separate domain)

### Databases to Merge/Archive
- **Subconcepts** → Merge into Flashcards
- **Critical Skills** → Merge into Flashcards
- **Concepts** → Evaluate overlap with Superconcepts

### Key Properties Added to Flashcards
- Z_Score, Z_Activation (Focus Stream)
- Memory_State (learning progression)
- PSI, PFIT (cognitive indices)
- Stability, Difficulty (FSRS)
- Prerequisites, Confusables (graph edges)
