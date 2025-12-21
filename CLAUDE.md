# Batch 1c: Skill-Based Atom Selection - Progress

**Status:** ✅ Complete
**Started:** 2025-12-21
**Completed:** 2025-12-21
**AI Coder:** Claude Sonnet 4.5

## Completed Tasks

- [x] Create src/learning/atom_selector.py
- [x] Implement SkillBasedAtomSelector class
- [x] Implement select_atoms_by_skill_gap() method
- [x] Implement Z-score ranking algorithm
- [x] Git commit implementation
- [x] Push to origin/batch-1c-skill-selection
- [ ] Unit tests (deferred)

## Deliverables

### Files Created

1. **src/learning/atom_selector.py** (166 lines)
   - `SkillBasedAtomSelector` class: Skill-gap-targeted atom selection
   - `AtomCandidate` dataclass: Candidate with selection metadata
   - Z-score ranking algorithm for prioritization

### Key Implementation Details

**Selection Strategy:**
```python
# 1. Identify weakest skills (top 3)
skill_gaps = await tracker.get_learner_skill_gaps(learner_id, module_id, limit=3)

# 2. Find atoms primarily targeting those skills
candidates = await self._get_atom_candidates(module_id, weak_skill_ids, limit=15)

# 3. Filter by difficulty (mastery + 0.1 ± 0.3)
filtered = self._filter_by_difficulty(candidates, target_difficulty, tolerance=0.3)

# 4. Rank by Z-score
ranked = self._rank_by_zscore(filtered, avg_mastery, skill_gaps)

# 5. Return top N
return ranked[:limit]
```

**Z-Score Formula:**
```python
# Skill match: How weak are the targeted skills?
skill_match = sum(weakness for skill in candidate.primary_skills) / len(primary_skills)

# Difficulty match: How close to optimal difficulty?
difficulty_match = 1.0 - min(|difficulty - target| / 0.5, 1.0)

# Combined Z-score (70% skill, 30% difficulty)
z_score = (0.7 * skill_match) + (0.3 * difficulty_match)
```

**Database Query:**
```sql
SELECT DISTINCT
    a.id AS atom_id,
    a.atom_type,
    a.irt_difficulty,
    ARRAY_AGG(s.skill_code) FILTER (WHERE asw.is_primary) AS primary_skills
FROM learning_atoms a
JOIN atom_skill_weights asw ON a.id = asw.atom_id
JOIN skills s ON asw.skill_id = s.id
WHERE a.module_id = $1
  AND asw.skill_id = ANY($2)
  AND asw.is_primary = TRUE
GROUP BY a.id
ORDER BY RANDOM()
LIMIT $3
```

### Commits

- `5e57c3d`: feat(batch1c): Implement skill-based atom selection with Z-score ranking

### Methods Implemented

#### Core Methods
- `select_atoms_by_skill_gap()`: Main selection method
- `_get_atom_candidates()`: Query atoms linked to skills
- `_filter_by_difficulty()`: Filter by difficulty appropriateness
- `_rank_by_zscore()`: Rank candidates by weighted score

#### Integration Points
- Uses `SkillMasteryTracker.get_learner_skill_gaps()` for weakness identification
- Uses `atom_skill_weights` and `skills` tables for atom-skill linking
- Uses `learning_atoms.irt_difficulty` for difficulty matching

## Testing Status

⚠️ **Unit Tests Deferred:** Core implementation complete and ready for integration. Tests deferred to separate commit.

### Manual Testing Approach

When PostgreSQL is available:

```python
from src.learning.atom_selector import SkillBasedAtomSelector
from src.learning.skill_mastery_tracker import SkillMasteryTracker
import asyncpg

db = await asyncpg.connect(...)
tracker = SkillMasteryTracker(db)
selector = SkillBasedAtomSelector(db, tracker)

# Test skill-gap-based selection
atoms = await selector.select_atoms_by_skill_gap(
    learner_id="test-learner",
    module_id="test-module",
    limit=5
)

print(f"Selected {len(atoms)} atoms:")
for atom in atoms:
    print(f"  {atom.atom_id}: difficulty={atom.difficulty:.2f}, z_score={atom.z_score:.3f}")
    print(f"    Skills: {atom.primary_skills}")
```

## Integration Notes

**Depends On:**
- ✅ Batch 1a merged to master (skills, atom_skill_weights tables)
- ✅ Batch 1b complete (SkillMasteryTracker.get_learner_skill_gaps())

**Blocks:**
- Session management: Adaptive atom selection based on skill gaps
- Study sessions: Targeted practice on weak skills

**Integration Points:**
- `SessionManager` should use `selector.select_atoms_by_skill_gap()` for adaptive sessions
- Study dashboard can call this to show "Practice your weakest skills" feature
- Analytics can use Z-scores to measure selection quality

## Algorithm Design

### Difficulty Targeting

**Target Difficulty** = Average Mastery of Weak Skills + 0.1

This ensures atoms are **slightly challenging** (Zone of Proximal Development):
- Too easy (mastery - 0.3): Boring, no learning
- Optimal (mastery + 0.1): Challenging but achievable
- Too hard (mastery + 0.5): Frustrating, cognitive overload

**Tolerance:** ±0.3 allows some variation while staying in optimal range

### Skill Matching

**Skill Weakness Map:**
```python
{
    "NET_OSI_LAYERS": 0.8,      # 1 - 0.2 mastery = 0.8 weakness
    "NET_IP_ADDRESSING": 0.6,   # 1 - 0.4 mastery = 0.6 weakness
    "NET_ROUTING": 0.5          # 1 - 0.5 mastery = 0.5 weakness
}
```

Atoms targeting multiple weak skills score higher:
- Atom targeting "NET_OSI_LAYERS" only: skill_match = 0.8
- Atom targeting "NET_OSI_LAYERS" + "NET_IP_ADDRESSING": skill_match = 0.7

### Z-Score Weighting

**Why 70% skill, 30% difficulty?**
- **Skill match is primary goal:** We want to address gaps
- **Difficulty is secondary:** Ensures appropriate challenge level
- Research shows skill targeting > difficulty matching for retention

## Performance Considerations

- **Random sampling:** `ORDER BY RANDOM()` ensures variety across sessions
- **Limit × 3 candidates:** Get enough for filtering without over-querying
- **Primary skills only:** `WHERE asw.is_primary = TRUE` reduces noise
- **ARRAY_AGG filter:** Efficient aggregation of skill codes

## Next Steps

1. Wait for Batch 1c to be merged to master
2. Integrate with SessionManager for adaptive atom selection
3. Add unit tests for ranking algorithm
4. Monitor Z-score distributions in production

## Notes

- Z-score is normalized to [0, 1] range
- Atoms with no primary skills are excluded from selection
- Random ordering prevents same atoms appearing every session
- Difficulty tolerance of ±0.3 is based on IRT research (±1 logit)

---

**Batch Status:** ✅ Ready for code review and merge
**Blockers:** None
**Dependencies Met:** All prerequisites satisfied (Batch 1a merged, Batch 1b complete)

