# Cortex 2.0: Complete Notion UI Configuration Guide

> **Purpose**: Comprehensive guide to setting up and configuring Notion databases for the Cortex 2.0 neuromorphic learning system.
>
> **Scope**: This system is NOT just flashcards - it's a multi-dimensional competency tracking platform with cognitive science foundations.

---

## System Overview

### The Three Pillars of Learning

Cortex 2.0 tracks mastery across **three orthogonal dimensions**:

| Dimension | Symbol | What It Measures | Primary Source |
|-----------|--------|------------------|----------------|
| **Declarative** | 💯 | "What you know" - Facts, definitions, recall | Flashcards + SRS |
| **Procedural** | 🔧 | "What you can do" - Skills, processes, execution | Critical Skills + Labs |
| **Application** | 🧠 | "How you apply it" - Transfer, problem-solving | Quizzes + Projects |

### Database Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KNOWLEDGE LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│  Superconcepts (L0/L1)  →  Concepts (L2)  →  Learning Atoms (L3)   │
│       Areas/Clusters         Subconcepts       Flashcards/Skills    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRICULUM LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│     Programs  →  Tracks  →  Modules  →  Activities                  │
│    (Degrees)    (Courses)   (Weeks)    (Exercises)                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                        ASSESSMENT LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│           Quizzes  ←  Sessions  →  Critical Skills                  │
│        (Application)   (Logs)      (Procedural)                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                        SUPPORT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│      Mental Models  |  Resources  |  Evidence  |  Brain Regions     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Specifications

### Total: 14 Core Databases

| # | Database | Purpose | Critical? |
|---|----------|---------|-----------|
| 1 | **Flashcards** | Learning atoms (declarative) | ✅ Core |
| 2 | **Concepts** | L2 competency units with 3-score | ✅ Core |
| 3 | **Superconcepts** | L0/L1 knowledge areas | ✅ Core |
| 4 | **Modules** | Curriculum units (weeks/chapters) | ✅ Core |
| 5 | **Tracks** | Learning paths (courses) | ✅ Core |
| 6 | **Sessions** | Study session logs | ✅ Core |
| 7 | **Quizzes** | Application assessments | ⚡ Important |
| 8 | **Critical Skills** | Procedural competencies | ⚡ Important |
| 9 | **Activities** | Exercises and assignments | ⚡ Important |
| 10 | **Programs** | Degree/certification paths | Optional |
| 11 | **Mental Models** | Meta-learning patterns | Optional |
| 12 | **Resources** | External learning materials | Optional |
| 13 | **Evidence** | Research citations | Optional |
| 14 | **Projects** | Learning focus (NEW for Cortex 2.0) | ✅ Core |

---

## Database 1: Flashcards (Learning Atoms)

> **Role**: The atomic units of declarative knowledge. Each flashcard tests ONE concept.

### Current Properties (37 total)

#### Identity & Content (5)
| Property | Type | Purpose |
|----------|------|---------|
| `Card ID` | Title | Unique identifier |
| `Question` | Rich Text | Front of card (prompt) |
| `Answer` | Rich Text | Back of card (response) |
| `Batch ID` | Text | Generation batch reference |
| `Mnemonic` | Text | Memory aid |

#### Atomicity & Quality (6)
| Property | Type | Purpose | Ideal Value |
|----------|------|---------|-------------|
| `Atomic` | Checkbox | Is card truly atomic? | ✅ |
| `Front Word Count` | Formula | Words in question | 8-15 |
| `Back Word Count` | Formula | Words in answer | 5-15 |
| `⚠️ Verbose Card` | Formula | Flags non-atomic | ❌ |
| `Quality Grade` | Select | A/B/C/D/F grade | A or B |
| `Ready for Export` | Checkbox | Approved for Anki | ✅ |

#### Cognitive Classification (6)
| Property | Type | Options |
|----------|------|---------|
| `Knowledge Type` | Select | Factual, Conceptual, Procedural, Metacognitive |
| `Memory System` | Select | Semantic, Episodic, Procedural |
| `Practice Function` | Select | Recall, Recognition, Application |
| `Note Type` | Select | Basic, Cloze, MCQ, Image |
| `CLT Intrinsic` | Number | Intrinsic cognitive load (1-10) |
| `CLT Extraneous` | Number | Extraneous load (minimize) |
| `CLT Germane` | Number | Germane load (maximize) |

#### Spaced Repetition (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Next Review` | Date | SRS calculated due date |
| `Created` | Created time | Auto timestamp |
| `Stability` | Number | FSRS stability (days) |
| `Difficulty` | Number | FSRS difficulty (0-1) |

#### Bayesian Tracking (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Bayes Prior θ_dec` | Number | Prior probability |
| `Bayes Posterior θ_dec` | Number | Updated probability |

#### Relationships (8)
| Property | Type | Links To |
|----------|------|----------|
| `Target Concept` | Relation | Concepts |
| `Prerequisites` | Relation | Flashcards (self) |
| `Module` | Relation | Modules |
| `Mental Model` | Relation | Mental Models |
| `Neuro Error` | Multi-Select | Error types |
| `Fail Modes` | Multi-Select | Cognitive failures |
| `Success Mode` | Multi-Select | Success patterns |
| `Error Classification` | Select | Error category |

#### Anki Integration (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Anki Deck` | Select | Target deck |
| `Anki Deck (Auto)` | Formula | Auto-computed deck |

#### Generation Metadata (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Generation Prompt` | Text | LLM prompt used |
| `Prompt Type` | Select | Prompt template |
| `Prompt Version` | Text | Version tracking |
| `Concept Count` | Number | Concepts covered |

### Properties to ADD for Cortex 2.0 (8)
| Property | Type | Purpose | Default |
|----------|------|---------|---------|
| `Z_Score` | Number | Attention urgency | 0.0 |
| `Z_Activation` | Checkbox | Focus Stream flag | ❌ |
| `Memory_State` | Status | NEW→LEARNING→REVIEW→MASTERED | NEW |
| `PSI` | Number | Pattern Separation Index | 0.5 |
| `PFIT` | Number | P-FIT Integration Index | 0.5 |
| `Confusables` | Relation | Self-relation for confusion pairs | - |
| `Launch_PLM` | Formula | `"cortex://plm/" + prop("Card ID")` | - |
| `Hierarchy_Level` | Select | Atom/Concept/Skill | Atom |

---

## Database 2: Concepts (Competency Units)

> **Role**: The L2 knowledge units that aggregate flashcards and track multi-dimensional mastery.

### Current Properties (90 total - grouped by function)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Subconcept Name` | Title | Concept name |
| `Definition` | Rich Text | Clear definition |
| `Domain` | Select | Knowledge domain |
| `Cluster / Subdomain` | Select | Grouping category |

#### The Three-Score System (12)

##### Declarative Score (💯)
| Property | Type | Purpose |
|----------|------|---------|
| `🎯 DecScore` | Formula | Declarative mastery (0-100) |
| `✅ DecScore Status` | Formula | Pass/Fail status |
| `💯 Dec: Card Count` | Rollup | Number of flashcards |
| `💯 Dec: Coverage %` | Formula | Concept coverage |
| `💯 Dec: High-R Count` | Rollup | High-retrievability cards |
| `💯 Dec: Mean Retrievability` | Rollup | Average retrievability |

##### Procedural Score (🔧)
| Property | Type | Purpose |
|----------|------|---------|
| `🎯 ProcScore` | Formula | Procedural mastery (0-100) |
| `✅ ProcScore Status` | Formula | Pass/Fail status |
| `🔧 Proc: Pass Rate` | Rollup | Skill pass rate |
| `🔧 Proc: Assist Rate` | Rollup | Needed assistance % |
| `🔧 Proc: Speed Index` | Rollup | Execution speed |
| `🔧 Proc: Core Score` | Formula | Core procedural score |
| `🔧 Proc: Days Since` | Formula | Days since practice |
| `🔧 Proc: Decay Factor` | Formula | Time decay |

##### Application Score (🧠)
| Property | Type | Purpose |
|----------|------|---------|
| `🎯 AppScore` | Formula | Application mastery (0-100) |
| `✅ AppScore Status` | Formula | Pass/Fail status |
| `🧠 App: Quiz Count` | Rollup | Number of quizzes |
| `🧠 App: Days Since` | Formula | Days since quiz |
| `🧠 App: Decay Factor` | Formula | Time decay |
| `🧠 App: Penalty` | Formula | Error penalty |
| `🧠 App: Repeated Errors?` | Checkbox | Pattern errors |

##### Combined Status
| Property | Type | Purpose |
|----------|------|---------|
| `🎖️ Overall Status` | Formula | Combined status |
| `🎯 Weakest Dimension` | Formula | Which dimension needs work |
| `Calibrated Score (0-100)` | Formula | Calibrated overall |

#### Bayesian Tracking (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Success Mass (S)` | Number | Beta distribution α |
| `Failure Mass (F)` | Number | Beta distribution β |
| `Trial Count` | Formula | S + F |
| `Calibration Error (Brier)` | Number | Brier score |

#### Learning Stage (5)
| Property | Type | Options |
|----------|------|---------|
| `Learning Stage` | Select | Exposure, Encoding, Consolidation, Mastery |
| `Mastery Gate` | Select | Gated, Unlocked, Mastered |
| `Proficiency Band` | Formula | Novice → Expert |
| `Scaffolding Level` | Select | Full, Partial, None |
| `Recommended Action` | Formula | Next suggested action |

#### Practice Tracking (5)
| Property | Type | Purpose |
|----------|------|---------|
| `Last Practice Date` | Date | Most recent practice |
| `Next Practice` | Formula | Recommended next |
| `Practice Hours` | Number | Total practice time |
| `Recommended Practice Type` | Formula | Dec/Proc/App |
| `Is Stale?` | Formula | Needs refresh |
| `Staleness (Days)` | Formula | Days since touch |

#### Intervention Flags (2)
| Property | Type | Purpose |
|----------|------|---------|
| `⚠️ Needs Intervention?` | Formula | Requires attention |
| `🚩 Insufficient Data?` | Formula | Not enough samples |

#### Relationships (12)
| Property | Type | Links To |
|----------|------|----------|
| `Parent Concept` | Relation | Concepts (self) |
| `Child Concepts` | Relation | Concepts (self) |
| `Superconcept` | Relation | Superconcepts |
| `Clusters` | Relation | Superconcepts |
| `Related Concepts` | Relation | Concepts (self) |
| `Flashcards 1` | Relation | Flashcards |
| `Modules` | Relation | Modules |
| `Quizzes` | Relation | Quizzes |
| `Activities` | Relation | Activities |
| `Sessions` | Relation | Sessions |
| `Practice Items` | Relation | Critical Skills |
| `Evidence` | Relation | Evidence |
| `Key Resource` | Relation | Resources |

### Properties to ADD for Cortex 2.0 (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Z_Score` | Number | Concept-level urgency |
| `Z_Activation` | Checkbox | Focus Stream |
| `Force_Z_Target` | Checkbox | Prerequisite remediation |
| `Confusable_Concepts` | Relation | Self-relation |

---

## Database 3: Superconcepts (Knowledge Areas)

> **Role**: L0 (Areas) and L1 (Clusters) - the high-level organization of knowledge.

### Recommended Properties (15)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Area/Cluster name |
| `Level` | Select | Area (L0) or Cluster (L1) |
| `Description` | Rich Text | Explanation |
| `Icon` | Text | Emoji for display |

#### Hierarchy (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Parent` | Relation | Self (for L1 → L0) |
| `Children` | Relation | Self (reverse) |
| `Concepts` | Relation | Link to Concepts DB |

#### Aggregations (5)
| Property | Type | Formula/Rollup |
|----------|------|----------------|
| `Concept Count` | Rollup | Count of concepts |
| `Atom Count` | Rollup | Count via concepts |
| `Avg DecScore` | Rollup | Average declarative |
| `Avg ProcScore` | Rollup | Average procedural |
| `Avg AppScore` | Rollup | Average application |

#### Status (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Overall Mastery` | Formula | Combined score |
| `Weakest Cluster` | Formula | Which needs work |
| `Completion %` | Formula | Progress |

---

## Database 4: Modules (Curriculum Units)

> **Role**: Week/chapter-level curriculum organization.

### Recommended Properties (18)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Module title |
| `Order` | Number | Sequence (1, 2, 3...) |
| `Description` | Rich Text | Overview |
| `Duration_Hours` | Number | Estimated study time |

#### Relationships (4)
| Property | Type | Links To |
|----------|------|----------|
| `Track` | Relation | Tracks |
| `Concepts` | Relation | Concepts |
| `Flashcards` | Relation | Flashcards |
| `Activities` | Relation | Activities |

#### Scheduling (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Start_Date` | Date | Planned start |
| `End_Date` | Date | Planned end |
| `Status` | Status | Not Started / In Progress / Complete |

#### Progress (5)
| Property | Type | Formula/Rollup |
|----------|------|----------------|
| `Atom Count` | Rollup | Total flashcards |
| `Mastered Count` | Rollup | Mastered flashcards |
| `Completion %` | Formula | Mastered/Total |
| `Avg Mastery` | Rollup | Average score |
| `Time Spent` | Rollup | From sessions |

#### Cortex 2.0 (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Z_Score` | Number | Module urgency |
| `Active` | Checkbox | Currently studying |

---

## Database 5: Tracks (Learning Paths)

> **Role**: Course-level sequences of modules.

### Recommended Properties (14)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Track name (e.g., "CCNA 200-301") |
| `Certification` | Text | Target certification |
| `Description` | Rich Text | Overview |
| `Icon` | Text | Emoji |

#### Relationships (3)
| Property | Type | Links To |
|----------|------|----------|
| `Program` | Relation | Programs |
| `Modules` | Relation | Modules |
| `Prerequisites` | Relation | Tracks (self) |

#### Progress (5)
| Property | Type | Formula/Rollup |
|----------|------|----------------|
| `Module Count` | Rollup | Total modules |
| `Completed Modules` | Rollup | Finished modules |
| `Progress %` | Formula | Completed/Total |
| `Total Hours` | Rollup | Sum of module hours |
| `Hours Completed` | Rollup | Completed hours |

#### Status (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Status` | Status | Not Started / Active / Complete |
| `Active` | Checkbox | Currently enrolled |

---

## Database 6: Sessions (Study Logs)

> **Role**: Automatic tracking of study sessions from Cortex CLI.

### Recommended Properties (22)

#### Identity (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Session_ID` | Title | Unique identifier |
| `Start_Time` | Date | Session start |
| `End_Time` | Date | Session end |

#### Duration & Stats (6)
| Property | Type | Purpose |
|----------|------|---------|
| `Duration_Minutes` | Formula | End - Start |
| `Atoms_Reviewed` | Number | Cards studied |
| `Correct` | Number | Correct answers |
| `Incorrect` | Number | Wrong answers |
| `Accuracy` | Formula | Correct / Total |
| `Avg_Response_ms` | Number | Response time |

#### NCDE Tracking (6)
| Property | Type | Options |
|----------|------|---------|
| `Diagnoses` | Multi-Select | ENCODING_ERROR, RETRIEVAL_ERROR, DISCRIMINATION_ERROR, INTEGRATION_ERROR, EXECUTIVE_ERROR, FATIGUE_ERROR |
| `Remediations` | Multi-Select | StandardFlow, MicroBreak, ForceZ, PLM, ContrastiveLure |
| `Fatigue_Peak` | Number | Max fatigue (0-1) |
| `Cognitive_Load_Avg` | Number | Average load |
| `Force_Z_Count` | Number | Backtracking events |
| `PLM_Triggers` | Number | PLM activations |

#### Context (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Mode` | Select | Normal, War, PLM, Review |
| `Module` | Relation | Focus module |
| `Track` | Relation | Active track |
| `Concepts_Touched` | Relation | Concepts reviewed |

#### Quality (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Session_Quality` | Formula | Overall quality score |
| `Productive_Minutes` | Number | Focused time |
| `Break_Count` | Number | Breaks taken |

---

## Database 7: Quizzes (Application Assessment)

> **Role**: Tests application-level understanding (🧠 AppScore).

### Recommended Properties (16)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Quiz title |
| `Description` | Rich Text | What it tests |
| `Type` | Select | Formative, Summative, Diagnostic |
| `Difficulty` | Select | Easy, Medium, Hard |

#### Relationships (3)
| Property | Type | Links To |
|----------|------|----------|
| `Concepts` | Relation | Concepts tested |
| `Module` | Relation | Curriculum unit |
| `Sessions` | Relation | When taken |

#### Scoring (5)
| Property | Type | Purpose |
|----------|------|---------|
| `Max_Score` | Number | Maximum points |
| `Your_Score` | Number | Achieved score |
| `Percentage` | Formula | Score % |
| `Passing_Threshold` | Number | Pass mark (e.g., 70) |
| `Passed` | Formula | Boolean |

#### Timing (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Date_Taken` | Date | When taken |
| `Time_Limit` | Number | Minutes allowed |

#### Analysis (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Weak_Concepts` | Relation | Concepts with errors |
| `Error_Patterns` | Multi-Select | Common mistakes |

---

## Database 8: Critical Skills (Procedural Competencies)

> **Role**: Tracks procedural skills (🔧 ProcScore) - what you can DO.

### Recommended Properties (18)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Skill name |
| `Description` | Rich Text | What the skill involves |
| `Type` | Select | Configuration, Troubleshooting, Analysis, Design |
| `Complexity` | Select | Basic, Intermediate, Advanced |

#### Relationships (3)
| Property | Type | Links To |
|----------|------|----------|
| `Concepts` | Relation | Related concepts |
| `Prerequisites` | Relation | Skills (self) |
| `Module` | Relation | Curriculum unit |

#### Mastery Tracking (6)
| Property | Type | Purpose |
|----------|------|---------|
| `Attempts` | Number | Total attempts |
| `Passes` | Number | Successful attempts |
| `Pass_Rate` | Formula | Passes / Attempts |
| `Last_Attempt` | Date | Most recent |
| `Best_Time` | Number | Fastest completion (seconds) |
| `Assist_Count` | Number | Times needed help |

#### Rubric (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Accuracy` | Number | Correctness score (0-100) |
| `Speed` | Number | Efficiency score (0-100) |
| `Independence` | Number | Without help (0-100) |

#### Status (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Mastery_Level` | Formula | Novice → Expert |
| `Needs_Practice` | Formula | Boolean flag |

---

## Database 9: Activities (Exercises)

> **Role**: Individual learning activities and assignments.

### Recommended Properties (14)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Activity title |
| `Description` | Rich Text | Instructions |
| `Type` | Select | Lab, Exercise, Reading, Video, Project |
| `Duration` | Number | Estimated minutes |

#### Relationships (3)
| Property | Type | Links To |
|----------|------|----------|
| `Module` | Relation | Curriculum unit |
| `Concepts` | Relation | Concepts practiced |
| `Skills` | Relation | Critical Skills |

#### Tracking (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Status` | Status | Not Started / In Progress / Complete |
| `Started_At` | Date | When started |
| `Completed_At` | Date | When finished |
| `Time_Spent` | Number | Actual minutes |

#### Scoring (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Graded` | Checkbox | Is graded? |
| `Score` | Number | Points earned |
| `Max_Score` | Number | Maximum points |

---

## Database 10: Projects (NEW - Cortex 2.0)

> **Role**: Learning focus areas for Z-Score project relevance signal P(a).

### Recommended Properties (12)

#### Identity (4)
| Property | Type | Purpose |
|----------|------|---------|
| `Name` | Title | Project name |
| `Description` | Rich Text | Learning goal |
| `Type` | Select | Certification, Skill, Knowledge, Career |
| `Priority` | Number | Weight 1-10 |

#### Relationships (3)
| Property | Type | Links To |
|----------|------|----------|
| `Target_Concepts` | Relation | Concepts |
| `Target_Superconcepts` | Relation | Knowledge areas |
| `Track` | Relation | Learning path |

#### Timeline (3)
| Property | Type | Purpose |
|----------|------|---------|
| `Start_Date` | Date | Project start |
| `Deadline` | Date | Target completion |
| `Status` | Status | Planning / Active / Complete / Paused |

#### Tracking (2)
| Property | Type | Purpose |
|----------|------|---------|
| `Active` | Checkbox | Currently active (for Z-Score) |
| `Progress` | Formula | Rollup of concept mastery |

---

## Views Configuration

### Flashcards Database Views

| View Name | Type | Filter | Sort | Purpose |
|-----------|------|--------|------|---------|
| **Focus Stream** | Table | `Z_Activation = ✓` | Z_Score DESC | Daily study queue |
| **Due Today** | Table | `Next Review ≤ Today` | Next Review ASC | SRS due cards |
| **New Cards** | Table | `Memory_State = NEW` | Created DESC | Unlearned |
| **Struggling** | Table | `PSI < 0.4 OR Lapses ≥ 3` | Lapses DESC | Needs attention |
| **By Module** | Board | Group by `Module` | Order ASC | Curriculum view |
| **Quality Audit** | Table | `Quality Grade IN [D, F]` | Created ASC | Content QA |
| **Force Z Candidates** | Table | `Prerequisites.Memory_State ≠ MASTERED` | - | Backtracking targets |

### Concepts Database Views

| View Name | Type | Filter | Sort | Purpose |
|-----------|------|--------|------|---------|
| **Intervention Required** | Table | `⚠️ Needs Intervention? = ✓` | Weakest Dimension | Priority action |
| **By Dimension** | Board | Group by `Weakest Dimension` | DecScore ASC | Dimension gaps |
| **Learning Stage** | Board | Group by `Learning Stage` | - | Progress flow |
| **By Cluster** | Board | Group by `Superconcept` | Name | Knowledge map |
| **Stale Concepts** | Table | `Is Stale? = ✅` | Staleness DESC | Needs refresh |
| **Mastery Overview** | Table | All | Overall Status DESC | Dashboard |

### Sessions Database Views

| View Name | Type | Filter | Sort | Purpose |
|-----------|------|--------|------|---------|
| **This Week** | Table | `Start_Time ≥ -7d` | Start_Time DESC | Recent activity |
| **Calendar** | Calendar | - | Start_Time | Schedule view |
| **Analytics** | Table | All | Duration DESC | Performance |
| **By Mode** | Board | Group by `Mode` | - | Session types |

---

## Property Naming Conventions

### Emoji Prefixes (Semantic Grouping)
| Prefix | Category | Example |
|--------|----------|---------|
| 🎯 | Score/Target | `🎯 DecScore` |
| ✅ | Status/Gate | `✅ DecScore Status` |
| 💯 | Declarative metric | `💯 Dec: Card Count` |
| 🔧 | Procedural metric | `🔧 Proc: Pass Rate` |
| 🧠 | Application metric | `🧠 App: Quiz Count` |
| ⚠️ | Warning/Flag | `⚠️ Needs Intervention?` |
| 🚩 | Alert | `🚩 Insufficient Data?` |
| 🎖️ | Achievement | `🎖️ Overall Status` |

### Property Type Guidelines
| For This Data | Use This Type |
|---------------|---------------|
| Computed values | Formula |
| Aggregations | Rollup |
| Yes/No | Checkbox |
| Categories | Select |
| Multiple categories | Multi-Select |
| Lifecycle stages | Status |
| Links to other DBs | Relation |
| Counts/Measurements | Number |
| Timestamps | Date |
| Long text | Rich Text |
| Short text | Text |

---

## Implementation Checklist

### Phase 1: Core Setup (Day 1)
- [ ] Add Cortex 2.0 properties to Flashcards (Z_Score, Z_Activation, Memory_State, PSI)
- [ ] Create Projects database with required properties
- [ ] Configure Focus Stream view in Flashcards
- [ ] Share all databases with Notion integration

### Phase 2: Views & Filters (Day 2)
- [ ] Create all recommended views in Flashcards
- [ ] Create all recommended views in Concepts
- [ ] Set up Session tracking views
- [ ] Configure view defaults (sort, visible columns)

### Phase 3: Relations (Day 3)
- [ ] Verify Flashcards → Concepts relation
- [ ] Add Prerequisites self-relation to Flashcards
- [ ] Add Confusables self-relation to Flashcards
- [ ] Connect Projects → Concepts

### Phase 4: Formulas (Day 4)
- [ ] Add Launch_PLM formula
- [ ] Verify all rollups are computing
- [ ] Test Status formulas
- [ ] Validate scoring formulas

---

## Summary Statistics

| Database | Current Props | Recommended | Status |
|----------|--------------|-------------|--------|
| Flashcards | 37 | 45 | Add 8 |
| Concepts | 90 | 94 | Add 4 |
| Superconcepts | ? | 15 | Configure |
| Modules | ? | 18 | Configure |
| Tracks | ? | 14 | Configure |
| Sessions | ? | 22 | Configure |
| Quizzes | ? | 16 | Configure |
| Critical Skills | ? | 18 | Configure |
| Activities | ? | 14 | Configure |
| Projects | NEW | 12 | Create |

**Total Properties Across System**: ~270 properties
**Total Databases**: 14 (10 existing + 4 supporting)
**Total Views**: ~40 recommended views
