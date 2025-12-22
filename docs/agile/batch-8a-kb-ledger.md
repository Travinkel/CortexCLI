# Batch 8a: Knowledge Base Ledger Upgrade

**Branch:** `batch-8a-kb-ledger`
**Repo:** `E:\Repo\project-astartes\ResearchEngine`
**Priority:** HIGH | **Effort:** 2-3 days | **Status:** Pending

## Overview

Upgrade the Master Knowledge Ledger to Cochrane-class systematic review standards. This batch implements the "write path" - all modifications to the knowledge graph happen here.

## Prerequisites

- Wave 3 (Schemas) complete - atom types have validated JSON Schemas
- Wave 4 (Documentation) complete
- ResearchEngine alembic_kb migrations functional

## Schema Changes

### 1. Add `tech_sources.license`

```sql
ALTER TABLE tech_sources ADD COLUMN license VARCHAR(100);
-- Values: MIT, Apache-2.0, CC-BY-4.0, proprietary, fair-use, etc.
```

### 2. Add `clean_atoms.knowledge_item_id`

```sql
ALTER TABLE clean_atoms
ADD COLUMN knowledge_item_id UUID REFERENCES knowledge_items(id);
-- Direct FK for audit queries without joining through knowledge_bridge
```

### 3. Ensure Full Provenance Chain

```
tech_sources (book/document)
    └── tech_nodes (chapter/section/paragraph with offsets)
            └── knowledge_bridge (links tech_node to knowledge_item)
                    └── clean_atoms (ICAP-classified learning units)
                            ├── provenance_tech_ref → tech_node.id
                            └── justification_science_ref → knowledge_item.id
```

## Audit Upgrade: Expert Blind Spots

**File:** `services/knowledge_base/services/ledger.py`

Upgrade the pedagogical audit to detect:

| Heuristic | Detection Logic | Deficit Score Impact |
|-----------|-----------------|---------------------|
| Prerequisite Assumptions | References to undefined terms | +0.2 per undefined term |
| Dense Symbol Ratio | Math symbols / total chars > 0.3 | +0.3 |
| Concept Jumps | Topic changes without transitions | +0.2 per jump |
| Passive Walls | >500 words without interaction markers | +0.4 |
| Expert Blind Spots | Implicit knowledge assumptions | +0.3 |

```python
def compute_expert_blind_spot_score(node: TechNode) -> float:
    """
    Detect where authors assume knowledge that creates cognitive load spikes.

    Markers:
    - "Obviously...", "Clearly...", "It follows that..."
    - Undefined acronyms on first use
    - Proof steps that skip intermediate reasoning
    - Code without comments in complex sections
    """
```

## Systematic Review: Edge-Aware Synthesis

**File:** `services/knowledge_base/services/systematic_review.py`

Upgrade to traverse `knowledge_edges` for evidence linking:

```python
async def edge_aware_synthesis(tech_node_id: UUID) -> List[EvidenceLink]:
    """
    1. Get concepts from tech_node content
    2. Find knowledge_items matching those concepts
    3. Traverse knowledge_edges to find supporting evidence
    4. Rank by edge weight and evidence quality
    5. Return ranked evidence links for knowledge_bridge
    """
```

**Edge Types to Traverse:**
- `supports` - Evidence directly supports the concept
- `refines` - Evidence provides nuanced understanding
- `contradicts` - Evidence challenges the concept (flag for review)
- `prerequisite` - Evidence required for understanding

## Lifting Pipeline: ETL-Based

**File:** `services/knowledge_base/services/lifting.py`

Route lifting through proper ETL architecture:

```python
class LiftingPipeline:
    """
    Transform high-deficit tech_nodes into clean_atoms.

    Flow:
    1. Select top-N nodes by pedagogical_deficit_score
    2. Fetch evidence from knowledge_bridge
    3. Route through ICAP classifier
    4. Apply grading strategy based on atom type
    5. Generate clean_atom with full provenance
    """

    def lift_node(self, node: TechNode, evidence: List[KnowledgeItem]) -> CleanAtom:
        # Determine optimal atom type from evidence
        atom_type = self.select_atom_type(node, evidence)

        # Apply ICAP classification
        icap_level = self.icap_classifier.classify(node.content, atom_type)

        # Generate with grading strategy
        grading_logic = self.grading_registry.get_strategy(atom_type)

        return CleanAtom(
            content=self.generate_content(node, atom_type),
            grading_logic=grading_logic.to_json(),
            icap_level=icap_level,
            lifting_model_version="v1.0",
            provenance_tech_ref=node.id,
            justification_science_ref=evidence[0].id if evidence else None,
            knowledge_item_id=evidence[0].id if evidence else None
        )
```

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `alembic_kb/versions/20251222_0003_ledger_upgrade.py` | Schema changes |
| `services/knowledge_base/services/blind_spot_detector.py` | Expert blind spot heuristics |

### Modified Files

| File | Changes |
|------|---------|
| `services/knowledge_base/services/ledger.py` | Add blind spot scoring |
| `services/knowledge_base/services/systematic_review.py` | Edge-aware synthesis |
| `services/knowledge_base/services/lifting.py` | ETL-based pipeline |
| `services/knowledge_base/models/tech_source.py` | Add license field |
| `services/knowledge_base/models/clean_atom.py` | Add knowledge_item_id |

## Commit Strategy

```bash
# Migration
git add alembic_kb/versions/20251222_0003_ledger_upgrade.py
git commit -m "feat(batch8a): Add license and knowledge_item_id to ledger schema"

# Audit upgrade
git add services/knowledge_base/services/ledger.py services/knowledge_base/services/blind_spot_detector.py
git commit -m "feat(batch8a): Add expert blind spot detection to pedagogical audit"

# Systematic review
git add services/knowledge_base/services/systematic_review.py
git commit -m "feat(batch8a): Implement edge-aware systematic review synthesis"

# Lifting pipeline
git add services/knowledge_base/services/lifting.py
git commit -m "feat(batch8a): Route lifting through ETL with ICAP classification"

git push -u origin batch-8a-kb-ledger
```

## Success Criteria

- [ ] Migration runs successfully (`alembic -c alembic_kb.ini upgrade head`)
- [ ] Blind spot detector identifies passive walls in test corpus
- [ ] Edge-aware synthesis finds evidence for algorithm/networking nodes
- [ ] Lifting pipeline produces valid clean_atoms with provenance
- [ ] All writes stay in ResearchEngine (no writes from CortexCLI)

## Testing

```bash
# Run audit on test corpus
python -m pytest tests/test_blind_spot_detector.py

# Test systematic review
python -m pytest tests/test_systematic_review.py

# Test lifting pipeline
python -m pytest tests/test_lifting_pipeline.py
```

---

**Reference:** Wave 5 Knowledge Integration | **Depends On:** Wave 3, Wave 4
