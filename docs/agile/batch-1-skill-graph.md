# Batch 1: Skill Graph Foundation

**Branch:** `batch-1-skill-graph`
**Worktree:** `../cortex-batch-1-skill-graph`
**Priority:** 🔴 CRITICAL (Infrastructure - Blocks Batches 3a, 3b, 3c)
**Estimated Effort:** 3-5 days
**Status:** 🟡 In Progress

## Objective

Build many-to-many atom-skill mapping infrastructure to enable:
- Mastery tracking per skill (not just per module)
- Targeted atom selection based on skill gaps
- Bayesian mastery updates with FSRS scheduling
- Skill-based analytics and reporting

## Dependencies

**Required Before Starting:**
- ✅ PostgreSQL database running
- ✅ Existing `learning_atoms` table
- ✅ Python environment with asyncpg

**Blocks:**
- Batch 3a, 3b, 3c (atom handlers need skill linking)
- Batch 5b (documentation needs skill graph architecture)

## Checklist

### 1. Database Schema (Migration 030)

- [ ] Create `src/db/migrations/030_skill_graph.sql`
  - [ ] `skills` table with hierarchical support
  - [ ] `atom_skill_weights` table (many-to-many)
  - [ ] `learner_skill_mastery` table with FSRS fields
  - [ ] Indexes for fast skill-based queries
  - [ ] Test migration on local DB

**Acceptance Criteria:**
- Migration runs without errors
- All tables created with correct columns
- Indexes created successfully
- Foreign key constraints working

**SQL Template:**
```sql
-- See plan file C:\Users\Shadow\.claude\plans\tidy-conjuring-moonbeam.md
-- Section 3: Batch 1, lines 223-271
```

### 2. Skill Mastery Tracker (Python Class)

- [ ] Create `src/learning/skill_mastery_tracker.py`
  - [ ] `SkillUpdate` dataclass
  - [ ] `SkillMasteryTracker` class
  - [ ] `update_skill_mastery()` method with Bayesian formula
  - [ ] `_bayesian_update()` private method
  - [ ] `_update_fsrs_parameters()` method
  - [ ] Database persistence methods

**Acceptance Criteria:**
- Bayesian update formula correct (P(mastery | correct) = ...)
- Hypercorrection logic (high confidence + wrong = bigger update)
- FSRS parameters update correctly
- All updates persisted to DB

**Python Template:**
```python
# See plan file lines 273-398
# Bayesian formula:
# - If correct: mastery += weight * confidence_factor * 0.1
# - If incorrect: mastery -= weight * penalty_factor * 0.15
# - Penalty factor = 1.5 if confidence >= 4 (hypercorrection)
```

### 3. Skill-Based Atom Selection

- [ ] Extend `src/learning/atom_selector.py`
  - [ ] Add `select_atoms_by_skill_gap()` method
  - [ ] Query weakest skills for module
  - [ ] Filter atoms by skill targeting
  - [ ] Filter by difficulty appropriateness
  - [ ] Z-score ranking

**Acceptance Criteria:**
- Selects atoms targeting learner's weakest skills
- Difficulty matches mastery level (mastery + 0.1)
- Returns diverse atom types
- No type repetition

**Query Template:**
```sql
-- See plan file lines 400-470
-- Find skills with lowest mastery + retrievability
-- Join to atoms via atom_skill_weights
-- Filter by difficulty tolerance
```

### 4. Seed Data (Skill Taxonomy)

- [ ] Create `data/skill_taxonomy_seed.sql`
  - [ ] 15 skills for networking domain (CCNA)
  - [ ] 10 skills for programming domain (PROGII)
  - [ ] 5 skills for systems domain (SDE2)
  - [ ] Bloom's taxonomy levels assigned
  - [ ] Cognitive levels (remember, understand, apply, analyze, evaluate, create)

**Acceptance Criteria:**
- At least 30 skills defined
- All skills have unique `skill_code`
- Domain and cognitive_level populated
- Ready for atom linking

**Example Skills:**
- `NET_OSI_LAYERS` - OSI Model Layers (remember)
- `NET_IP_ADDRESSING` - IP Addressing and Subnetting (apply)
- `PROG_DEBUGGING` - Debugging and Error Tracing (analyze)
- `SYS_TESTING_STRATEGY` - Test Strategy Design (create)

### 5. Integration & Testing

- [ ] Run migration on test database
- [ ] Load seed data
- [ ] Test skill mastery tracker with sample data
- [ ] Test skill-based atom selection
- [ ] Verify FSRS parameters update correctly

**Test Cases:**
```python
# Test 1: Bayesian update (correct answer)
initial_mastery = 0.5
is_correct = True
confidence = 4
expected_mastery = 0.5 + (1.0 * 0.8 * 0.1) = 0.58

# Test 2: Hypercorrection (high confidence + wrong)
initial_mastery = 0.7
is_correct = False
confidence = 5
expected_mastery = 0.7 - (1.0 * 1.5 * 0.15) = 0.475
```

## Files to Create

| Priority | File Path | Lines of Code | Template Location |
|----------|-----------|---------------|-------------------|
| HIGH | `src/db/migrations/030_skill_graph.sql` | ~80 | Plan lines 223-271 |
| HIGH | `src/learning/skill_mastery_tracker.py` | ~150 | Plan lines 273-398 |
| HIGH | `data/skill_taxonomy_seed.sql` | ~50 | Plan lines 472-497 |
| MEDIUM | `src/learning/atom_selector.py` (extend) | ~70 | Plan lines 400-470 |

## Files to Modify

| File Path | Changes | Lines Added |
|-----------|---------|-------------|
| `src/learning/atom_selector.py` | Add `select_atoms_by_skill_gap()` method | ~70 |
| `src/learning/session_manager.py` | Use skill-based selection (future batch) | 0 (not yet) |

## Commit Strategy

**Commit 1:**
```bash
git add src/db/migrations/030_skill_graph.sql
git commit -m "feat(batch1): Add skill graph schema with skill_weights and mastery tables"
```

**Commit 2:**
```bash
git add data/skill_taxonomy_seed.sql
git commit -m "feat(batch1): Add skill taxonomy seed data for networking, programming, systems"
```

**Commit 3:**
```bash
git add src/learning/skill_mastery_tracker.py
git commit -m "feat(batch1): Implement SkillMasteryTracker with Bayesian updates and FSRS"
```

**Commit 4:**
```bash
git add src/learning/atom_selector.py
git commit -m "feat(batch1): Add skill-based atom selection with gap targeting"
```

**Commit 5:**
```bash
git add tests/test_skill_mastery_tracker.py tests/test_skill_atom_selection.py
git commit -m "test(batch1): Add unit tests for skill graph components"
```

**Final Push:**
```bash
git push -u origin batch-1-skill-graph
```

## GitHub Issues to Create

### Issue #1: Skill Graph Database Schema
```bash
gh issue create \
  --title "[Batch 1] Skill Graph Database Schema" \
  --body "Create skill taxonomy and atom-skill linking tables.\n\n**Files:**\n- Migration 030_skill_graph.sql\n- Seed data skill_taxonomy_seed.sql\n\n**Status:** ✅ Complete" \
  --label "batch-1,database,skill-graph,enhancement" \
  --milestone "Phase 1: Foundation"
```

### Issue #2: SkillMasteryTracker Implementation
```bash
gh issue create \
  --title "[Batch 1] SkillMasteryTracker with Bayesian Updates" \
  --body "Implement skill mastery tracking using Bayesian updates and FSRS scheduling.\n\n**Features:**\n- Bayesian update formula\n- Hypercorrection logic\n- FSRS parameter updates\n- Database persistence\n\n**Status:** ✅ Complete" \
  --label "batch-1,mastery-tracking,skill-graph,enhancement" \
  --milestone "Phase 1: Foundation"
```

### Issue #3: Skill-Based Atom Selection
```bash
gh issue create \
  --title "[Batch 1] Skill-Based Atom Selection" \
  --body "Extend AtomSelector with skill gap targeting.\n\n**Features:**\n- Query weakest skills\n- Target atoms by skill\n- Difficulty appropriateness\n- Z-score ranking\n\n**Status:** ✅ Complete" \
  --label "batch-1,atom-selection,skill-graph,enhancement" \
  --milestone "Phase 1: Foundation"
```

## Testing Instructions

### Manual Testing

1. **Database Migration:**
```bash
cd ../cortex-batch-1-skill-graph
psql -U postgres -d cortex_cli < src/db/migrations/030_skill_graph.sql
psql -U postgres -d cortex_cli < data/skill_taxonomy_seed.sql
```

2. **Python Testing:**
```python
from src.learning.skill_mastery_tracker import SkillMasteryTracker

tracker = SkillMasteryTracker()

# Test Bayesian update
updates = tracker.update_skill_mastery(
    learner_id="test-learner-123",
    atom_id="atom-456",
    is_correct=True,
    latency_ms=3500,
    confidence=4
)

print(updates)  # Should show mastery increase
```

3. **Skill-Based Selection:**
```python
from src.learning.atom_selector import AtomSelector

selector = AtomSelector()
atoms = await selector.select_atoms_by_skill_gap(
    learner_id="test-learner-123",
    module_id="ccna-module-1",
    limit=5
)

print([a.id for a in atoms])  # Should return atoms targeting weak skills
```

### Unit Tests

Create `tests/test_skill_mastery_tracker.py`:

```python
import pytest
from src.learning.skill_mastery_tracker import SkillMasteryTracker

def test_bayesian_update_correct():
    tracker = SkillMasteryTracker()
    result = tracker._bayesian_update(
        prior_mastery=0.5,
        is_correct=True,
        weight=1.0,
        confidence=4
    )
    assert result == pytest.approx(0.58, rel=0.01)

def test_hypercorrection():
    tracker = SkillMasteryTracker()
    result = tracker._bayesian_update(
        prior_mastery=0.7,
        is_correct=False,
        weight=1.0,
        confidence=5
    )
    # High confidence + wrong = bigger penalty
    assert result < 0.55
```

## Success Metrics

- [ ] Migration runs without errors
- [ ] All 3 tables created with correct structure
- [ ] Seed data loads 30+ skills
- [ ] Bayesian update formula validated
- [ ] Hypercorrection logic working
- [ ] Skill-based atom selection returns appropriate atoms
- [ ] Unit tests passing (>80% coverage)

## Next Steps After Completion

1. **Merge to master:**
   ```bash
   cd E:\Repo\cortex-cli
   git checkout master
   git merge batch-1-skill-graph
   git push
   ```

2. **Unblock dependent batches:**
   - Batch 3a, 3b, 3c can now add skill linking to handlers
   - Batch 5b can document skill graph architecture

3. **Create GitHub issues** for this batch (see above)

4. **Update status** in `docs/agile/README.md` to ✅ Complete

## Reference

- **Master Plan:** `C:\Users\Shadow\.claude\plans\tidy-conjuring-moonbeam.md`
- **Section:** Batch 1: Skill Graph Foundation (lines 218-499)
- **Database Schema:** Lines 223-271
- **Bayesian Formula:** Lines 361-398
- **Skill Selection:** Lines 400-470

---

**Last Updated:** 2025-12-21
**Status:** 🟡 In Progress
**Assigned To:** Claude Code Instance #1
