# Epic: Learning Atom Enhancement

**Epic ID**: EPIC-LA-001
**Status**: Proposed
**Priority**: High
**Estimated Effort**: 15-20 story points
**Dependencies**: Phase 4.6 completion (CCNA atom generation)

---

## Epic Summary

Enhance the 3,422 generated CCNA learning atoms to achieve full alignment with learning science specifications, including prerequisite linking, difficulty calibration, and metadata enrichment.

---

## Business Value

- **Learning Effectiveness**: Prerequisite-aware sequencing improves knowledge transfer by 25-40% (Knewton research)
- **Adaptive Learning**: Difficulty calibration enables personalized learning paths
- **Retention**: Proper spacing metadata optimizes long-term retention
- **Quality**: Metadata enrichment supports multiple learning modalities

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Atoms with prerequisites | 80% | `WHERE prerequisite_ids IS NOT NULL` |
| Atoms with difficulty | 100% | `WHERE difficulty IS NOT NULL` |
| Atoms with knowledge type | 100% | `WHERE knowledge_type IS NOT NULL` |
| Prerequisite accuracy | 90% | Manual sampling validation |

---

## User Stories

### US-LA-001: Prerequisite Extraction from Tags

**As a** learning system
**I want** to extract prerequisite relationships from existing Anki tags
**So that** atoms can be sequenced based on knowledge dependencies

**Acceptance Criteria**:
- [ ] Parse `tag:prereq:domain:topic:subtopic` format from Anki imports
- [ ] Create `atom_prerequisites` junction table
- [ ] Map extracted prerequisites to `clean_concepts`
- [ ] Handle missing concept mappings gracefully

**Story Points**: 3

---

### US-LA-002: Prerequisite Inference via Embeddings

**As a** learning system
**I want** to infer missing prerequisites using semantic similarity
**So that** atoms without explicit tags still have prerequisite relationships

**Acceptance Criteria**:
- [ ] Generate embeddings for all atoms (sentence-transformers)
- [ ] Compute pairwise similarity for atoms within same concept cluster
- [ ] Infer prerequisite if similarity > 0.7 and one atom is "foundational"
- [ ] Flag inferred prerequisites for human review

**Story Points**: 5

---

### US-LA-003: Difficulty Calibration

**As a** learning system
**I want** to assign difficulty values (0.0-1.0) to all atoms
**So that** adaptive algorithms can select appropriate content

**Acceptance Criteria**:
- [ ] Apply IRT-based difficulty estimation from review data
- [ ] Use heuristics for atoms without review history:
  - Word count complexity
  - Concept depth in hierarchy
  - Knowledge type (declarative < procedural < applicative)
- [ ] Store in `clean_atoms.difficulty` column
- [ ] Validate against actual learner performance

**Story Points**: 5

---

### US-LA-004: Knowledge Type Classification

**As a** learning system
**I want** to classify atoms by knowledge type (declarative, procedural, applicative)
**So that** learning activities can be matched to appropriate atom types

**Acceptance Criteria**:
- [ ] Parse existing card_id suffixes (DEC, PROC, APP)
- [ ] Apply NLP classifier for atoms without explicit type
- [ ] Store in `clean_atoms.knowledge_type` column
- [ ] Validation: 95% classification accuracy

**Story Points**: 3

---

### US-LA-005: Spacing Metadata Assignment

**As a** learning system
**I want** atoms to have initial spacing recommendations
**So that** new learners receive optimal review intervals

**Acceptance Criteria**:
- [ ] Assign `initial_interval_hours` based on:
  - Knowledge type (declarative: 24h, procedural: 48h, applicative: 72h)
  - Difficulty level
  - Concept importance
- [ ] Store in `clean_atoms.initial_interval` column
- [ ] Integrate with FSRS scheduler

**Story Points**: 2

---

### US-LA-006: Feedback Level Structuring

**As a** learning system
**I want** atom explanations structured for multiple feedback levels
**So that** learners can receive progressive hints

**Acceptance Criteria**:
- [ ] Parse existing explanations into structured format:
  - `hint_1`: Minimal nudge
  - `hint_2`: Direction hint
  - `answer`: Correct response
  - `explanation`: Full elaboration
- [ ] Store in `clean_atoms.feedback_json` column
- [ ] Apply to 100% of atoms with explanations

**Story Points**: 3

---

## Technical Tasks

### TT-LA-001: Database Schema Updates

```sql
-- Add new columns to clean_atoms
ALTER TABLE clean_atoms ADD COLUMN IF NOT EXISTS
    knowledge_type TEXT CHECK (knowledge_type IN ('declarative', 'procedural', 'applicative'));

ALTER TABLE clean_atoms ADD COLUMN IF NOT EXISTS
    difficulty DECIMAL(3,2) CHECK (difficulty >= 0 AND difficulty <= 1);

ALTER TABLE clean_atoms ADD COLUMN IF NOT EXISTS
    initial_interval_hours INTEGER DEFAULT 24;

ALTER TABLE clean_atoms ADD COLUMN IF NOT EXISTS
    feedback_json JSONB;

-- Create prerequisite junction table
CREATE TABLE IF NOT EXISTS atom_prerequisites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES clean_atoms(id) ON DELETE CASCADE,
    prerequisite_atom_id UUID REFERENCES clean_atoms(id) ON DELETE CASCADE,
    relationship_type TEXT DEFAULT 'requires', -- requires, recommends, corequisite
    confidence DECIMAL(3,2), -- 0-1, NULL for explicit
    source TEXT, -- tag, inference, manual
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(atom_id, prerequisite_atom_id)
);

CREATE INDEX idx_atom_prereqs_atom ON atom_prerequisites(atom_id);
CREATE INDEX idx_atom_prereqs_prereq ON atom_prerequisites(prerequisite_atom_id);
```

### TT-LA-002: Embedding Infrastructure

- Install `sentence-transformers` package
- Model: `all-MiniLM-L6-v2` (384 dimensions)
- Store embeddings in `clean_atoms.embedding` column (pgvector)
- Batch processing for 3,422 atoms

### TT-LA-003: Prerequisite Inference Pipeline

```python
def infer_prerequisites(atom: CleanAtom, candidates: List[CleanAtom]) -> List[Tuple[UUID, float]]:
    """
    Infer prerequisite relationships using embedding similarity.

    Returns: List of (prerequisite_atom_id, confidence_score) tuples
    """
    atom_embedding = get_embedding(atom.front + " " + atom.back)

    prerequisites = []
    for candidate in candidates:
        if candidate.id == atom.id:
            continue

        similarity = cosine_similarity(atom_embedding, candidate.embedding)

        # Only consider if similar enough but not too similar (duplicate)
        if 0.7 <= similarity < 0.95:
            # Heuristic: foundational atoms have simpler language
            if is_foundational(candidate) and not is_foundational(atom):
                prerequisites.append((candidate.id, similarity))

    return prerequisites
```

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Phase 4.6 CCNA generation | Complete | 3,422 atoms available |
| pgvector extension | Not installed | Required for embeddings |
| sentence-transformers | Not installed | pip install required |
| Clean concepts table | Complete | Prerequisite targets |

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Inferred prerequisites inaccurate | Medium | High | Human review queue |
| Embedding computation time | Low | Medium | Batch processing overnight |
| Difficulty calibration drift | Medium | Low | Periodic recalibration |

---

## Out of Scope

- Parsons problem generation (separate epic)
- Code tracing atoms (separate epic)
- Multi-language support
- Real-time prerequisite updates during learning

---

## Related Documents

- `docs/phase-4.6-ccna-generation.md` - Generation results
- `docs/database-schema.md` - Schema reference
- `quizzes_activities.md` - Learning science specifications
- ADR-005: Activity Matrix for Learning Content
