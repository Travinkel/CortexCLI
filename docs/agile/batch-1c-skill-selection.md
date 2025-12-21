# Batch 1c: Skill-Based Atom Selection

**Branch:** `batch-1c-skill-selection`
**Worktree:** `../cortex-batch-1c-skill-selection`
**Priority:** 🟡 HIGH (Infrastructure - Depends on Batch 1a)
**Estimated Effort:** 2 days
**Status:** 🔴 Pending

## Objective

Extend AtomSelector with skill-based queries to target learner's weakest skills and enable adaptive atom selection based on skill gaps.

## Dependencies

**Required:**
- ✅ Batch 1a complete (needs `skills`, `atom_skill_weights` tables)
- ✅ Existing `src/learning/atom_selector.py`

**Blocks:**
- All Batch 3 handlers (they will use skill-based selection)

## Files to Modify

### 1. src/learning/atom_selector.py (extend existing)

**Add these methods to the existing `AtomSelector` class:**

```python
async def select_atoms_by_skill_gap(
    self,
    learner_id: str,
    module_id: str,
    limit: int = 5
) -> List[Atom]:
    """
    Select atoms targeting learner's weakest skills.

    Strategy:
    1. Find skills with lowest mastery for this module
    2. Find atoms primarily targeting those skills
    3. Filter by difficulty appropriate to mastery level
    4. Return top N by Z-score ranking

    Args:
        learner_id: Learner UUID
        module_id: Module UUID
        limit: Number of atoms to return

    Returns:
        List of Atom objects targeting skill gaps
    """
    # Query weakest skills
    weak_skills_query = """
    SELECT
        s.id AS skill_id,
        s.skill_code,
        s.name,
        COALESCE(lsm.mastery_level, 0.0) AS mastery_level,
        COALESCE(lsm.retrievability, 0.0) AS retrievability,
        COUNT(DISTINCT a.id) AS available_atoms
    FROM skills s
    JOIN atom_skill_weights asw ON s.id = asw.skill_id AND asw.is_primary = TRUE
    JOIN learning_atoms a ON asw.atom_id = a.id
    LEFT JOIN learner_skill_mastery lsm ON s.id = lsm.skill_id AND lsm.learner_id = :learner_id
    WHERE a.module_id = :module_id AND s.is_active = TRUE
    GROUP BY s.id, s.skill_code, s.name, lsm.mastery_level, lsm.retrievability
    HAVING COUNT(DISTINCT a.id) > 0
    ORDER BY
        COALESCE(lsm.mastery_level, 0.0) ASC,  -- Lowest mastery first
        COALESCE(lsm.retrievability, 0.0) ASC  -- Most forgotten first
    LIMIT 3
    """

    weak_skills = await self.db.execute(
        weak_skills_query,
        {"learner_id": learner_id, "module_id": module_id}
    )
    weak_skills = weak_skills.fetchall()

    if not weak_skills:
        logger.warning(f"No skill data for learner {learner_id} - falling back to random selection")
        return await self.select_random_atoms(module_id, limit)

    # Get atoms for these skills
    skill_ids = [s["skill_id"] for s in weak_skills]

    candidates_query = """
    SELECT DISTINCT a.*
    FROM learning_atoms a
    JOIN atom_skill_weights asw ON a.id = asw.atom_id
    WHERE asw.skill_id = ANY(:skill_ids)
      AND asw.is_primary = TRUE
      AND a.module_id = :module_id
    ORDER BY RANDOM()
    LIMIT :limit_mult
    """

    candidates = await self.db.execute(
        candidates_query,
        {
            "skill_ids": skill_ids,
            "module_id": module_id,
            "limit_mult": limit * 3  # Get 3x candidates for filtering
        }
    )
    candidates = candidates.fetchall()

    if not candidates:
        return []

    # Filter by difficulty appropriateness
    # (Mastery 0.3 → difficulty 0.4, Mastery 0.7 → difficulty 0.8, etc.)
    filtered = []
    for atom in candidates:
        # Get target skills for this atom
        atom_skills = [s for s in weak_skills if s["skill_id"] in self._get_atom_skill_ids(atom)]

        if atom_skills:
            avg_mastery = sum(s["mastery_level"] for s in atom_skills) / len(atom_skills)
            target_difficulty = avg_mastery + 0.1  # Slightly above current mastery

            # Accept if within tolerance
            if abs(atom.irt_difficulty - target_difficulty) < 0.3:
                filtered.append(atom)

    # Return top N
    return filtered[:limit]

async def select_atoms_by_skills(
    self,
    learner_id: str,
    module_id: str,
    target_skills: List[str],  # skill_codes
    limit: int = 5
) -> List[Atom]:
    """
    Select atoms targeting specific skills.

    Args:
        learner_id: Learner UUID
        module_id: Module UUID
        target_skills: List of skill_codes to target
        limit: Number of atoms to return

    Returns:
        List of Atom objects targeting specified skills
    """
    query = """
    SELECT DISTINCT a.*
    FROM learning_atoms a
    JOIN atom_skill_weights asw ON a.id = asw.atom_id
    JOIN skills s ON asw.skill_id = s.id
    WHERE s.skill_code = ANY(:skill_codes)
      AND asw.is_primary = TRUE
      AND a.module_id = :module_id
    ORDER BY asw.weight DESC, RANDOM()
    LIMIT :limit
    """

    result = await self.db.execute(
        query,
        {
            "skill_codes": target_skills,
            "module_id": module_id,
            "limit": limit
        }
    )

    atoms = result.fetchall()
    return [self._row_to_atom(row) for row in atoms]

async def get_skill_coverage_for_module(
    self,
    module_id: str
) -> dict:
    """
    Get skill coverage statistics for a module.

    Returns:
        dict with skill_code → atom_count mapping
    """
    query = """
    SELECT
        s.skill_code,
        s.name AS skill_name,
        COUNT(DISTINCT asw.atom_id) AS atom_count,
        COUNT(DISTINCT CASE WHEN asw.is_primary = TRUE THEN asw.atom_id END) AS primary_atom_count
    FROM skills s
    LEFT JOIN atom_skill_weights asw ON s.id = asw.skill_id
    LEFT JOIN learning_atoms a ON asw.atom_id = a.id AND a.module_id = :module_id
    WHERE s.is_active = TRUE
    GROUP BY s.skill_code, s.name
    ORDER BY atom_count DESC
    """

    result = await self.db.execute(query, {"module_id": module_id})
    rows = result.fetchall()

    return {
        row["skill_code"]: {
            "skill_name": row["skill_name"],
            "total_atoms": row["atom_count"],
            "primary_atoms": row["primary_atom_count"]
        }
        for row in rows
    }

def _get_atom_skill_ids(self, atom: Atom) -> List[str]:
    """
    Extract skill IDs from atom's content_json or metadata.

    This is a helper method to get skill IDs already linked to the atom.
    """
    # Implementation depends on how skills are stored in atom
    # For now, query from atom_skill_weights
    # This should be refactored to avoid N+1 queries
    return []  # Placeholder - implement based on schema
```

## Checklist

- [ ] Read existing `src/learning/atom_selector.py`
- [ ] Add `select_atoms_by_skill_gap()` method
- [ ] Add `select_atoms_by_skills()` method
- [ ] Add `get_skill_coverage_for_module()` method
- [ ] Add helper method `_get_atom_skill_ids()`
- [ ] Write unit tests for new methods
- [ ] Test against database with Batch 1a tables
- [ ] Verify skill-based selection returns correct atoms

## Testing

### Manual Validation

```bash
# Unit tests
pytest tests/learning/test_atom_selector.py::test_select_atoms_by_skill_gap -v
pytest tests/learning/test_atom_selector.py::test_select_atoms_by_skills -v

# Integration test
python -c "
from src.learning.atom_selector import AtomSelector
import asyncio

async def test():
    selector = AtomSelector(db)

    # Test skill gap selection
    atoms = await selector.select_atoms_by_skill_gap(
        learner_id='test-learner',
        module_id='ccna-module-1',
        limit=5
    )
    print(f'Selected {len(atoms)} atoms targeting skill gaps')

    # Test specific skill targeting
    atoms = await selector.select_atoms_by_skills(
        learner_id='test-learner',
        module_id='ccna-module-1',
        target_skills=['NET_IP_ADDRESSING', 'NET_ROUTING_PROTOCOLS'],
        limit=3
    )
    print(f'Selected {len(atoms)} atoms for specified skills')

    # Test skill coverage
    coverage = await selector.get_skill_coverage_for_module('ccna-module-1')
    print(f'Module has {len(coverage)} skills with atom coverage')

asyncio.run(test())
"
```



### BDD Testing Requirements

**See:** [BDD Testing Strategy](../explanation/bdd-testing-strategy.md)

Create tests appropriate for this batch:
- Unit tests for all new classes/functions
- Integration tests for database interactions
- Property-based tests for complex logic (use hypothesis)

### CI Checks

**See:** [CI/CD Pipeline](../explanation/ci-cd-pipeline.md)

This batch must pass:
- Linting (ruff check)
- Type checking (mypy --strict)
- Security scan (bandit)
- Unit tests (85% coverage minimum)
- Integration tests (all critical paths)

## Commit Strategy

```bash
cd ../cortex-batch-1c-skill-selection

git add src/learning/atom_selector.py
git commit -m "feat(batch1c): Add skill-based atom selection queries

Added methods:
- select_atoms_by_skill_gap(): Target weakest skills
- select_atoms_by_skills(): Target specific skills
- get_skill_coverage_for_module(): Coverage statistics

🤖 Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git add tests/learning/test_atom_selector.py
git commit -m "test(batch1c): Add tests for skill-based atom selection

🤖 Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push -u origin batch-1c-skill-selection
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 1c] Skill-Based Atom Selection" \
  --body "Extend AtomSelector with skill-based queries.\\n\\n**File:** src/learning/atom_selector.py\\n\\n**Features:**\\n- Select atoms by skill gap\\n- Select atoms by specific skills\\n- Skill coverage statistics\\n\\n**Status:** ✅ Complete" \
  --label "batch-1c,skill-graph,enhancement" \
  --milestone "Phase 1: Foundation"
```

## Success Metrics

- [ ] All unit tests passing
- [ ] Skill gap queries return atoms for weakest skills
- [ ] Specific skill queries work correctly
- [ ] Skill coverage statistics accurate
- [ ] Integration test succeeds

## Reference

### Strategy Documents
- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md) - Testing approach for cognitive validity
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md) - Automated quality gates and deployment
- [Atom Type Taxonomy](../reference/atom-type-taxonomy.md) - 100+ atom types with ICAP classification
- [Schema Migration Plan](../explanation/schema-migration-plan.md) - Migration to polymorphic JSONB atoms

### Work Orders
- **Master Plan:** `C:\\Users\\Shadow\\.claude\\plans\\tidy-conjuring-moonbeam.md` lines 406-500
- **Parent Work Order:** `docs/agile/batch-1-skill-graph.md`
- **Depends On:** `batch-1a-skill-database.md` (tables must exist)


---

**Status:** 🔴 Pending
**AI Coder:** Ready for assignment
**Start Condition:** ⏳ Wait for Batch 1a to complete and merge to master
