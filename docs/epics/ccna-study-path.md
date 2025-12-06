# Epic: CCNA CLI Study Path

**Epic ID**: EPIC-SP-001
**Status**: In Progress
**Priority**: Critical
**Estimated Effort**: 25-30 story points
**Dependencies**: Phase 4.6 CCNA atom generation (COMPLETE), Anki bidirectional sync (COMPLETE)

---

## Epic Summary

Build a comprehensive CLI-based study path system for CCNA certification that provides:
1. **Daily study sessions** with today's due cards + recommended next concepts
2. **Full path overview** showing complete CCNA journey with progress % per module/subchapter
3. **Adaptive remediation** that automatically recommends revisiting chapters when performance drops
4. **Hierarchical tracking** with 103 main sections (X.Y) and 469 subsections (X.Y.Z)

---

## Business Value

- **Structured Learning**: Complete learning path through all 17 CCNA modules with measurable progress
- **Adaptive Remediation**: Automatic interleaving of struggling content prevents knowledge gaps
- **Evidence-Based**: Uses FSRS metrics (retrievability, stability, lapses) + MCQ/quiz scores for decisions
- **Daily Workflow**: Efficient "what to study today" command for consistent daily practice

---

## User Requirements (Gathered)

| Requirement | Selection | Details |
|-------------|-----------|---------|
| Primary workflow | Both + remediation | Daily view + full path + automatic recommendations |
| Remediation trigger | Combined signals | Anki FSRS + MCQ scores + all learning atom types |
| Tracking granularity | Both levels | 103 main sections (X.Y) + 469 subsections (X.Y.Z) |
| Initial progress | Start fresh | Assume moderate familiarity, let Anki calibrate |
| Atom types for remediation | Including Parsons | Flashcards + MCQ + True/False + Matching + Cloze + Parsons |
| Recommendation style | Adaptive interleaving | Mix remediation cards with new content automatically |
| Mastery threshold | 90% + low lapses | 90% retrievability AND <2 lapses per atom average |
| Study cadence | Daily | Need efficient "what to study today" command |

### User Context
- User has READ all 17 CCNA chapters
- User has COMPLETED exercises only for Chapter 1
- User will NOT have time to do exercises for chapters 2-17
- System should calibrate actual knowledge through Anki reviews

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Section tracking | 100% | All 103 main sections + 469 subsections have mastery scores |
| Daily command latency | <2s | `nls study today` response time |
| Adaptive interleaving | 70/30 | 70% new content, 30% remediation when struggling |
| Mastery accuracy | 85% | Predicted vs actual quiz performance correlation |
| Coverage | 100% | All 3,422 atoms linked to subchapters |

---

## User Stories

### US-SP-001: Daily Study Command

**As a** CCNA student
**I want** to run `nls study today` to see my daily study session
**So that** I know exactly what to study each day

**Acceptance Criteria**:
- [ ] Shows count of due Anki reviews
- [ ] Shows recommended new concepts to learn
- [ ] Shows any remediation recommendations (chapters to revisit)
- [ ] Displays estimated study time
- [ ] Respects adaptive interleaving (mixes remediation with new content)

**Story Points**: 5

**Example Output**:
```
┌─────────────────────────────────────────────────────────────┐
│                   CCNA Study Session                        │
│                   December 4, 2025                          │
├─────────────────────────────────────────────────────────────┤
│ 📚 Due Reviews: 47 cards (est. 15 min)                      │
│ 🆕 New Concepts: 12 atoms from Module 3.2 (IP Addressing)   │
│ ⚠️  Remediation: 8 cards from 1.6 Reliable Networks         │
│    (retrievability dropped to 68%)                          │
├─────────────────────────────────────────────────────────────┤
│ Today's Focus: Module 3 - Protocols and Models              │
│ Progress: Module 1 ████████░░ 82% | Module 2 ██████░░░░ 61% │
└─────────────────────────────────────────────────────────────┘

Run `nls study start` to begin session
Run `nls study path` to see full learning path
```

---

### US-SP-002: Full Path Overview

**As a** CCNA student
**I want** to run `nls study path` to see my complete CCNA journey
**So that** I can track my overall progress and identify weak areas

**Acceptance Criteria**:
- [ ] Shows all 17 modules with completion percentage
- [ ] Shows subchapter breakdown (1.2, 1.4, etc.) with mastery status
- [ ] Color-codes: mastered (green), learning (yellow), struggling (red)
- [ ] Shows estimated time to completion
- [ ] Indicates which subchapters need remediation

**Story Points**: 5

**Example Output**:
```
CCNA Learning Path Progress
═══════════════════════════════════════════════════════════════

Module 1: Networking Today                              [82%]
  ├── 1.2 Network Components                     ████████░░ 85% ✓
  ├── 1.4 Common Types of Networks               ████████░░ 81% ✓
  ├── 1.5 Internet Connections                   ███████░░░ 72%
  ├── 1.6 Reliable Networks                      ██████░░░░ 68% ⚠️
  ├── 1.7 Network Trends                         █████████░ 92% ✓
  └── 1.8 Network Security                       ████████░░ 84% ✓

Module 2: Basic Switch and End Device Config            [61%]
  ├── 2.1 Cisco IOS Access                       ███████░░░ 74%
  ├── 2.2 IOS Navigation                         ██████░░░░ 65%
  ├── 2.3 Command Structure                      █████░░░░░ 58% ⚠️
  ...

[13 more modules...]

═══════════════════════════════════════════════════════════════
Overall: 34% complete | 3,422 atoms | Est. 6 weeks remaining
Mastered: 412 atoms | Learning: 1,847 atoms | Struggling: 89 atoms
```

---

### US-SP-003: Hierarchical Section Mastery Tracking

**As a** learning system
**I want** to track mastery at both main section (X.Y) and subsection (X.Y.Z) levels
**So that** I can provide both overview and drill-down progress views

**Acceptance Criteria**:
- [ ] Parse all 103 main sections (X.Y) and 469 subsections (X.Y.Z)
- [ ] Build parent-child relationships (1.2 is parent of 1.2.1, 1.2.2, etc.)
- [ ] Link atoms to their source section
- [ ] Calculate mastery per section: 90% retrievability + <2 lapses
- [ ] Aggregate subsection mastery up to main section level
- [ ] Store in `ccna_sections` and `ccna_section_mastery` tables
- [ ] Update on each Anki sync

**Story Points**: 8

**Content Inventory**:
- 17 Modules (top level)
- 103 Main Sections (X.Y format)
- 469 Subsections (X.Y.Z format)
- 3,422 Learning Atoms

**Database Schema**:
```sql
-- Hierarchical section structure
CREATE TABLE ccna_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_number INTEGER NOT NULL,
    section_id TEXT NOT NULL UNIQUE,  -- "1.2", "1.4.1", "2.1.3"
    title TEXT NOT NULL,
    level INTEGER NOT NULL,  -- 1=module, 2=main section, 3=subsection
    parent_section_id TEXT REFERENCES ccna_sections(section_id),
    atom_count INTEGER DEFAULT 0,
    display_order INTEGER,  -- For correct ordering in UI
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Mastery tracking per section
CREATE TABLE ccna_section_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id TEXT REFERENCES ccna_sections(section_id),
    user_id TEXT DEFAULT 'default',  -- For future multi-user
    mastery_score DECIMAL(5,2),  -- 0-100 (aggregated)
    avg_retrievability DECIMAL(5,4),  -- 0-1
    avg_lapses DECIMAL(5,2),
    atoms_total INTEGER DEFAULT 0,
    atoms_mastered INTEGER DEFAULT 0,  -- 90%+ retrievability, <2 lapses
    atoms_learning INTEGER DEFAULT 0,   -- 50-89% retrievability
    atoms_struggling INTEGER DEFAULT 0, -- <50% retrievability or >3 lapses
    atoms_new INTEGER DEFAULT 0,        -- Never reviewed
    last_review_date TIMESTAMPTZ,
    needs_remediation BOOLEAN DEFAULT false,
    remediation_reason TEXT,  -- 'low_retrievability', 'high_lapses', 'low_mcq'
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(section_id, user_id)
);

-- Link atoms to their source section
ALTER TABLE clean_atoms ADD COLUMN IF NOT EXISTS
    ccna_section_id TEXT REFERENCES ccna_sections(section_id);

-- Indexes
CREATE INDEX idx_sections_module ON ccna_sections(module_number);
CREATE INDEX idx_sections_parent ON ccna_sections(parent_section_id);
CREATE INDEX idx_sections_level ON ccna_sections(level);
CREATE INDEX idx_mastery_section ON ccna_section_mastery(section_id);
CREATE INDEX idx_mastery_remediation ON ccna_section_mastery(needs_remediation);
CREATE INDEX idx_atoms_section ON clean_atoms(ccna_section_id);

-- View for aggregated module mastery
CREATE OR REPLACE VIEW v_module_mastery AS
SELECT
    s.module_number,
    COUNT(DISTINCT s.section_id) as total_sections,
    AVG(m.mastery_score) as avg_mastery,
    SUM(m.atoms_mastered) as total_mastered,
    SUM(m.atoms_learning) as total_learning,
    SUM(m.atoms_struggling) as total_struggling,
    SUM(m.atoms_new) as total_new,
    COUNT(CASE WHEN m.needs_remediation THEN 1 END) as sections_needing_remediation
FROM ccna_sections s
LEFT JOIN ccna_section_mastery m ON s.section_id = m.section_id
WHERE s.level = 2  -- Main sections only
GROUP BY s.module_number
ORDER BY s.module_number;
```

---

### US-SP-004: Adaptive Interleaving Algorithm

**As a** learning system
**I want** to mix remediation cards with new content automatically
**So that** the learner addresses weak areas without disrupting forward progress

**Acceptance Criteria**:
- [ ] Default ratio: 70% new content, 30% remediation when struggling areas exist
- [ ] Identify struggling subchapters: retrievability <70% OR lapses >3 OR MCQ <80%
- [ ] Interleave cards from struggling areas into daily queue
- [ ] Increase remediation ratio if multiple areas are struggling
- [ ] Cap remediation at 50% to maintain progress motivation

**Story Points**: 8

**Algorithm**:
```python
def calculate_daily_queue(user_stats: UserStats) -> StudyQueue:
    # 1. Get due Anki reviews (highest priority)
    due_reviews = get_due_reviews()

    # 2. Identify struggling subchapters
    struggling = get_struggling_subchapters(
        min_retrievability=0.70,
        max_lapses=3,
        min_mcq_score=0.80
    )

    # 3. Calculate remediation ratio
    if len(struggling) == 0:
        remediation_ratio = 0.0
    elif len(struggling) <= 2:
        remediation_ratio = 0.30
    elif len(struggling) <= 5:
        remediation_ratio = 0.40
    else:
        remediation_ratio = 0.50  # Cap at 50%

    # 4. Get new content from next subchapter in path
    new_content = get_next_subchapter_atoms(
        count=int(30 * (1 - remediation_ratio))
    )

    # 5. Get remediation cards from struggling areas
    remediation = get_remediation_cards(
        subchapters=struggling,
        count=int(30 * remediation_ratio)
    )

    # 6. Interleave (not blocked)
    return interleave_cards(due_reviews, new_content, remediation)
```

---

### US-SP-005: Remediation Detection

**As a** learning system
**I want** to detect when a subchapter needs remediation from multiple signals
**So that** I can recommend revisiting before knowledge gaps compound

**Acceptance Criteria**:
- [ ] Signal 1: FSRS retrievability <70% for majority of atoms
- [ ] Signal 2: Lapses >3 average per atom in subchapter
- [ ] Signal 3: MCQ score <80% for subchapter quiz questions
- [ ] Signal 4: Parsons problem failures (for procedural knowledge)
- [ ] Combined score: weighted average of all signals
- [ ] Threshold: remediation triggered at combined score <75%

**Story Points**: 5

**Weighting**:
```
Remediation Score =
    (0.40 × Anki_Retrievability) +
    (0.25 × (1 - Lapse_Rate)) +
    (0.25 × MCQ_Score) +
    (0.10 × Parsons_Score)
```

---

### US-SP-006: Mastery Threshold Validation

**As a** CCNA student
**I want** a subchapter marked as "mastered" only when I truly know it
**So that** I don't skip content I haven't actually learned

**Acceptance Criteria**:
- [ ] Mastery requires: 90% average retrievability across subchapter atoms
- [ ] Mastery requires: <2 average lapses per atom
- [ ] Mastery requires: At least 3 successful reviews per atom
- [ ] Visual indicator changes from learning (yellow) to mastered (green)
- [ ] Mastered subchapters excluded from remediation queue

**Story Points**: 3

---

### US-SP-007: Chapter 1 Baseline

**As a** CCNA student who has read and done exercises for Chapter 1
**I want** the system to recognize my Chapter 1 familiarity
**So that** it calibrates appropriately without making me re-read everything

**Acceptance Criteria**:
- [ ] Mark all Chapter 1 atoms as "read but not reviewed"
- [ ] Initial retrievability estimate: 0.50 (moderate familiarity)
- [ ] First Anki review will calibrate actual knowledge
- [ ] Chapters 2-17: initial retrievability 0.30 (read but no exercises)

**Story Points**: 2

---

## CLI Command Structure

```
nls study
├── today       # Daily study session summary
├── start       # Launch interactive study session
├── path        # Full learning path overview
├── module <n>  # Detailed view of module n
├── stats       # Personal learning statistics
├── sync        # Sync Anki reviews and update mastery
└── remediation # Show all areas needing remediation
```

### Command Details

**`nls study today`**
- Shows daily study summary
- Due reviews + new concepts + remediation
- Estimated time

**`nls study path`**
- Full 17-module overview
- Subchapter breakdown
- Color-coded mastery status

**`nls study module 3`**
- Deep dive into Module 3
- All subchapters with individual stats
- Weak atoms highlighted

**`nls study stats`**
- Total atoms mastered/learning/struggling
- Study streak
- Estimated completion date
- Performance trends

**`nls study sync`**
- Pull latest Anki stats
- Recalculate mastery scores
- Update remediation flags

---

## Technical Tasks

### TT-SP-001: Database Schema Migration

Create `017_ccna_study_path.sql`:
- `ccna_subchapters` table
- `ccna_subchapter_mastery` table
- Views for efficient querying

### TT-SP-002: Subchapter Parser Enhancement

Enhance `src/ccna/content_parser.py`:
- Extract section IDs (1.2, 1.4.1, etc.)
- Build subchapter hierarchy
- Link atoms to subchapters during generation

### TT-SP-003: Mastery Calculator Service

Create `src/study/mastery_calculator.py`:
- Aggregate Anki stats by subchapter
- Apply mastery threshold logic
- Calculate remediation scores

### TT-SP-004: Adaptive Interleaver

Create `src/study/interleaver.py`:
- Implement interleaving algorithm
- Respect ratio caps
- Randomize within constraints

### TT-SP-005: CLI Study Commands

Extend `src/cli/main.py`:
- Add `study` command group
- Implement all subcommands
- Rich table formatting

### TT-SP-006: Anki Sync Enhancement

Extend `src/anki/pull_service.py`:
- Aggregate stats by subchapter
- Update mastery table on sync
- Flag remediation needs

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Phase 4.6 CCNA atoms | COMPLETE | 3,422 atoms available |
| Anki bidirectional sync | COMPLETE | Push/pull working |
| FSRS stat extraction | COMPLETE | Retrievability, stability, lapses |
| Content parser | COMPLETE | Section extraction working |
| Quiz system | COMPLETE | MCQ, True/False, Matching |
| Parsons problems | COMPLETE | Code arrangement available |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Subchapter linking accuracy | Medium | High | Manual review of atom-subchapter mapping |
| Mastery threshold too strict | Medium | Medium | Configurable thresholds |
| Interleaving disrupts flow | Low | Medium | User preference for pure new vs interleaved |
| Anki sync latency | Low | Low | Background sync option |

---

## Out of Scope

- Multi-user support (future phase)
- Mobile app (CLI only for now)
- AI-generated explanations for struggling content
- Peer comparison/leaderboards
- Integration with Cisco NetAcad

---

## Related Documents

- `docs/phase-4.6-ccna-generation.md` - CCNA atom generation
- `docs/epics/learning-atom-enhancement.md` - Prerequisite system
- `docs/anki-integration.md` - Anki sync documentation
- `docs/cli-quiz-compatibility.md` - Quiz types
