# Database Schema Migration Plan: From Flashcard Legacy to Polymorphic Atoms

## Overview

This document outlines the architectural migration from the current "flashcard legacy" schema (front/back text columns) to a polymorphic JSONB-based schema that supports 100+ atom types as documented in the [atom type taxonomy](../reference/atom-type-taxonomy.md).

## Problem Statement

### Current Architecture (Bottleneck)

```python
# src/db/models/canonical.py
class CleanAtom(Base):
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str | None] = mapped_column(Text)
```

**Issues:**

1. **Type Blindness**: Database cannot query atom internals (e.g., "find all MCQ with difficulty > 0.8")
2. **Parsing Overhead**: Every atom handler must parse JSON from text fields
3. **Schema Violations**: No validation—malformed JSON accepted by database
4. **Misconception Linkage**: Distractors stored as JSON strings, not linked to misconception_library table
5. **ICAP Classification Missing**: No engagement_mode or element_interactivity fields

### Current Workaround (Anti-Pattern)

```python
# src/cortex/atoms/mcq.py
data = json.loads(back)  # Unsafe: no schema validation
if isinstance(data, dict) and "options" in data:
    # Handler must defensively check structure
```

This forces cognitive science logic into application code instead of database constraints.

## Target Architecture (Polymorphic JSONB)

### Proposed Schema

```python
# src/db/models/canonical.py (refactored)
class LearningAtom(Base):
    """Universal atom container supporting 100+ types."""

    __tablename__ = "learning_atoms"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    atom_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # POLYMORPHIC CONTENT (replaces front/back)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    grading_logic: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ICAP Framework (replaces Bloom's taxonomy)
    engagement_mode: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("engagement_mode IN ('passive', 'active', 'constructive', 'interactive')")
    )

    # Cognitive Load Theory
    element_interactivity: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        CheckConstraint("element_interactivity BETWEEN 0.0 AND 1.0")
    )

    # Knowledge Dimension (Krathwohl, 2002)
    knowledge_dimension: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("knowledge_dimension IN ('factual', 'conceptual', 'procedural', 'metacognitive')")
    )

    # IRT Parameters
    irt_difficulty: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0.5)
    irt_discrimination: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=1.0)

    # Psychometric Data
    response_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    skills = relationship("AtomSkillWeight", back_populates="atom")
    response_options = relationship("AtomResponseOption", back_populates="atom")
```

### Misconception Linking (SQL-Level)

```python
class AtomResponseOption(Base):
    """
    Individual answer choices for recognition atoms (MCQ, matching).
    Links wrong answers to specific misconceptions at database level.
    """

    __tablename__ = "atom_response_options"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    atom_id: Mapped[UUID] = mapped_column(ForeignKey("learning_atoms.id"))
    option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)

    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    # CRITICAL: Hard-link to misconception
    misconception_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("misconception_library.id")
    )

    # Psychometric tracking
    selection_count: Mapped[int] = mapped_column(Integer, default=0)
    selection_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    discrimination_index: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Relationships
    atom = relationship("LearningAtom", back_populates="response_options")
    misconception = relationship("MisconceptionLibrary")
```

## Migration Strategy

### Phase 1: Add New Columns (Non-Breaking)

**Migration:** `src/db/migrations/040_add_polymorphic_columns.sql`

```sql
-- Add new JSONB columns (nullable initially)
ALTER TABLE learning_atoms
ADD COLUMN content JSONB,
ADD COLUMN grading_logic JSONB,
ADD COLUMN engagement_mode VARCHAR(20),
ADD COLUMN element_interactivity NUMERIC(3,2),
ADD COLUMN knowledge_dimension VARCHAR(20);

-- Add constraints (will be enforced after backfill)
ALTER TABLE learning_atoms
ADD CONSTRAINT check_engagement_mode
    CHECK (engagement_mode IN ('passive', 'active', 'constructive', 'interactive')),
ADD CONSTRAINT check_element_interactivity
    CHECK (element_interactivity BETWEEN 0.0 AND 1.0),
ADD CONSTRAINT check_knowledge_dimension
    CHECK (knowledge_dimension IN ('factual', 'conceptual', 'procedural', 'metacognitive'));
```

**Impact:** No downtime. Old code continues using front/back.

### Phase 2: Backfill Data

**Script:** `scripts/migrate_front_back_to_jsonb.py`

```python
import json
from sqlalchemy import select
from src.db.models.canonical import CleanAtom

async def migrate_atoms():
    """Migrate front/back to content/grading_logic."""

    atoms = await db.execute(select(CleanAtom))

    for atom in atoms.scalars():
        # Parse current JSON from back field
        try:
            back_data = json.loads(atom.back) if atom.back else {}
        except json.JSONDecodeError:
            # Malformed JSON: skip and log
            logger.error(f"Malformed JSON in atom {atom.id}: {atom.back}")
            continue

        # Determine atom type from existing logic
        if "options" in back_data:
            atom_type = "mcq"
            content = {
                "prompt": atom.front,
                "options": back_data["options"]
            }
            grading_logic = {
                "type": "exact_match",
                "correct_index": back_data.get("correct_index", 0)
            }
            engagement_mode = "active"
            element_interactivity = 0.35
            knowledge_dimension = "factual"

        elif "blocks" in back_data:
            atom_type = "parsons"
            content = {
                "prompt": atom.front,
                "blocks": back_data["blocks"]
            }
            grading_logic = {
                "type": "sequence_match",
                "correct_order": back_data.get("correct_order", [])
            }
            engagement_mode = "constructive"
            element_interactivity = 0.7
            knowledge_dimension = "procedural"

        else:
            # Default: flashcard
            atom_type = "flashcard"
            content = {
                "front": atom.front,
                "back": atom.back
            }
            grading_logic = {
                "type": "exact_match",
                "correct_answer": atom.back
            }
            engagement_mode = "active"
            element_interactivity = 0.1
            knowledge_dimension = "factual"

        # Update atom
        atom.atom_type = atom_type
        atom.content = content
        grading_logic = grading_logic
        atom.engagement_mode = engagement_mode
        atom.element_interactivity = element_interactivity
        atom.knowledge_dimension = knowledge_dimension

    await db.commit()
```

**Validation:**

```sql
-- Verify all atoms migrated
SELECT COUNT(*) FROM learning_atoms WHERE content IS NULL;
-- Expected: 0

-- Verify JSONB structure
SELECT atom_type, COUNT(*)
FROM learning_atoms
GROUP BY atom_type;
-- Expected: mcq: 500, parsons: 200, flashcard: 1000, etc.
```

### Phase 3: Create AtomResponseOption Table

**Migration:** `src/db/migrations/041_create_response_options.sql`

```sql
CREATE TABLE atom_response_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID NOT NULL REFERENCES learning_atoms(id) ON DELETE CASCADE,
    option_index INTEGER NOT NULL,
    option_text TEXT NOT NULL,

    is_correct BOOLEAN DEFAULT FALSE,

    misconception_id UUID REFERENCES misconception_library(id),

    selection_count INTEGER DEFAULT 0,
    selection_rate NUMERIC(5,4),
    discrimination_index NUMERIC(5,4),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(atom_id, option_index)
);

CREATE INDEX idx_response_options_atom ON atom_response_options(atom_id);
CREATE INDEX idx_response_options_misconception ON atom_response_options(misconception_id);
```

**Backfill Script:** `scripts/extract_response_options.py`

```python
async def extract_response_options():
    """Extract MCQ options from JSONB to separate table."""

    mcq_atoms = await db.execute(
        select(LearningAtom).where(LearningAtom.atom_type == "mcq")
    )

    for atom in mcq_atoms.scalars():
        options = atom.content.get("options", [])

        for idx, option in enumerate(options):
            # Create response option record
            response_option = AtomResponseOption(
                atom_id=atom.id,
                option_index=idx,
                option_text=option["text"],
                is_correct=(idx == option.get("correct_index", 0)),
                misconception_id=option.get("misconception_id")  # If tagged
            )
            db.add(response_option)

    await db.commit()
```

### Phase 4: Update Application Code

**Refactor Handlers:** `src/cortex/atoms/mcq.py`

```python
# OLD (parsing JSON from text)
class MCQHandler:
    def grade(self, atom, response):
        data = json.loads(atom.back)  # REMOVE THIS
        options = data["options"]
        # ...

# NEW (using JSONB fields)
class MCQHandler:
    def grade(self, atom: LearningAtom, response):
        options = atom.content["options"]  # Direct access
        # ...

    def get_distractors(self, atom: LearningAtom):
        """Get wrong answers with misconception links."""
        return atom.response_options.filter_by(is_correct=False).all()
```

**Schema Validation:** Add pydantic models for content/grading_logic

```python
# src/cortex/validation/atom_schemas.py
from pydantic import BaseModel, Field

class MCQContent(BaseModel):
    """Schema for MCQ content field."""
    prompt: str
    options: list[str] = Field(min_length=2, max_length=6)

class MCQGradingLogic(BaseModel):
    """Schema for MCQ grading_logic field."""
    type: Literal["exact_match"] = "exact_match"
    correct_index: int = Field(ge=0)

# Validate before insert
def validate_mcq_atom(content: dict, grading_logic: dict):
    MCQContent(**content)  # Raises ValidationError if invalid
    MCQGradingLogic(**grading_logic)
```

### Phase 5: Deprecate Old Columns

**Migration:** `src/db/migrations/042_drop_front_back_columns.sql`

```sql
-- After all code migrated, drop old columns
ALTER TABLE learning_atoms
DROP COLUMN front,
DROP COLUMN back;

-- Make new columns NOT NULL
ALTER TABLE learning_atoms
ALTER COLUMN content SET NOT NULL,
ALTER COLUMN grading_logic SET NOT NULL,
ALTER COLUMN engagement_mode SET NOT NULL,
ALTER COLUMN element_interactivity SET NOT NULL,
ALTER COLUMN knowledge_dimension SET NOT NULL;
```

**Deployment:** Requires coordinated deploy (schema + code simultaneously).

## Query Examples (Before vs After)

### Finding Atoms by Difficulty

**Before (Impossible):**

```sql
-- Cannot query JSON inside text field
SELECT * FROM learning_atoms WHERE ???  -- No way to access difficulty
```

**After:**

```sql
-- Direct JSONB queries
SELECT *
FROM learning_atoms
WHERE content->>'difficulty' > '0.8'
  AND atom_type = 'mcq';
```

### Finding Misconceptions

**Before (Slow):**

```python
# Must load ALL atoms and parse JSON in Python
atoms = db.query(CleanAtom).all()
for atom in atoms:
    data = json.loads(atom.back)
    for option in data.get("options", []):
        if option.get("misconception_id") == target_id:
            results.append(atom)
```

**After (Fast):**

```sql
-- SQL join at database level
SELECT DISTINCT a.*
FROM learning_atoms a
JOIN atom_response_options aro ON a.id = aro.atom_id
WHERE aro.misconception_id = 'uuid-here';
```

### Finding ICAP Levels

**Before (Impossible):**

```sql
-- No engagement_mode column
```

**After:**

```sql
-- Find all constructive atoms (high retention)
SELECT *
FROM learning_atoms
WHERE engagement_mode = 'constructive'
  AND element_interactivity > 0.7
ORDER BY irt_difficulty;
```

## Performance Impact

### Storage

**Before:** 2 TEXT columns per atom (front + back JSON string)

**After:** 2 JSONB columns + separate response_options table

**Impact:** +15% storage (JSONB binary format), but enables indexing

### Query Speed

**Before:** Full table scan + Python JSON parsing

**After:** JSONB index scan (10-100x faster for complex queries)

**Example:**

```sql
-- Create GIN index on JSONB
CREATE INDEX idx_atoms_content ON learning_atoms USING GIN (content);

-- Query using index
SELECT * FROM learning_atoms WHERE content @> '{"difficulty": 0.8}';
-- Uses index, millisecond response
```

## Rollback Plan

If migration fails, rollback is simple during Phase 1-2:

```sql
-- Drop new columns
ALTER TABLE learning_atoms
DROP COLUMN content,
DROP COLUMN grading_logic,
DROP COLUMN engagement_mode,
DROP COLUMN element_interactivity,
DROP COLUMN knowledge_dimension;

-- Old code continues using front/back
```

After Phase 5, rollback requires restoring from backup.

## Testing Strategy

See [BDD Testing Strategy](bdd-testing-strategy.md) for full test plan.

**Migration Tests:**

```python
# tests/migration/test_front_back_to_jsonb.py

def test_mcq_migration():
    """Verify MCQ atoms migrate correctly."""
    # Before
    old_atom = CleanAtom(
        front="What is TCP?",
        back='{"options": ["UDP", "TCP", "ICMP"], "correct_index": 1}'
    )

    # Migrate
    migrated = migrate_atom(old_atom)

    # After
    assert migrated.atom_type == "mcq"
    assert migrated.content["prompt"] == "What is TCP?"
    assert len(migrated.content["options"]) == 3
    assert migrated.grading_logic["correct_index"] == 1
    assert migrated.engagement_mode == "active"

def test_response_options_extracted():
    """Verify MCQ options become separate records."""
    mcq_atom = create_mcq_with_options()

    extract_response_options()

    options = db.query(AtomResponseOption).filter_by(atom_id=mcq_atom.id).all()
    assert len(options) == 3
    assert options[1].is_correct is True
    assert options[0].misconception_id is not None
```

## Timeline

**Week 1:** Deploy migration 040 (add columns), run backfill script
**Week 2:** Deploy migration 041 (create response_options table), run extraction script
**Week 3:** Refactor handlers to use new schema, deploy code
**Week 4:** Validate all queries working, monitor performance
**Week 5:** Deploy migration 042 (drop old columns)

**Total:** 5-week migration with no downtime.

## Related Documentation

- [Atom Type Taxonomy](../reference/atom-type-taxonomy.md): Full 100+ atom catalog
- [BDD Testing Strategy](bdd-testing-strategy.md): How to test migrated atoms
- [CI/CD Pipeline](ci-cd-pipeline.md): Automated migration validation

## Scientific References

- **ICAP Framework:** Chi, M. T., & Wylie, R. (2014). The ICAP framework
- **Cognitive Load Theory:** Sweller, J. (1988). Cognitive load during problem solving
- **Misconception-Based Learning:** Sadler, P. M. (2006). The role of misconceptions in learning

## Open Questions

1. **Backward Compatibility:** Should we maintain a `front` property as a view for legacy code?
   - **Decision:** No. Clean break forces proper adoption.

2. **JSONB Schema Versioning:** How to handle schema evolution for content/grading_logic?
   - **Decision:** Add `schema_version` field, validate on read.

3. **Response Options for Non-MCQ:** Should Parsons blocks also be separate records?
   - **Decision:** Phase 2 feature. Start with MCQ only.
