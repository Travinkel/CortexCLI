# Batch 5b: Documentation

**Branch:** `batch-5b-documentation`
**Priority:** 🟢 MEDIUM | **Effort:** 2-3 days | **Status:** 🔴 Pending

## Objective

Create/update 6 documentation files with 100+ taxonomy, skill graph, and Greenlight integration.

## Files to Create

1. **docs/reference/atom-taxonomy-v2.md**
   - Full 100+ taxonomy organized by cognitive subsystem
   - Each atom type with description, UI pattern, grading mode
   - ~500 lines

2. **docs/explanation/skill-graph-architecture.md**
   - Skill linking and mastery tracking architecture
   - Bayesian update formula explanation
   - FSRS integration
   - ~300 lines

3. **docs/how-to/implement-new-atom-type.md**
   - Step-by-step guide for adding new atom types
   - Handler implementation
   - Schema creation
   - Testing
   - ~200 lines

4. **docs/how-to/validate-atom-quality.md**
   - Research-grade validation procedures
   - Psychometric analysis (p-value, discrimination)
   - Distractor effectiveness
   - ~150 lines

5. **docs/reference/greenlight-handoff-v2.md**
   - Updated handoff protocol
   - API specification
   - Request/response formats
   - Error handling
   - ~250 lines

## Files to Update

6. **README.md**
   - Add 100+ taxonomy overview
   - Add skill graph section
   - Add Greenlight integration section
   - Update architecture diagram
   - ~100 lines added

## Content Structure

### atom-taxonomy-v2.md

```markdown
# 100+ Atom Taxonomy: Cognitive Subsystem Organization

## I. Discrimination & Perception (10 types)

### visual_hotspot
**Description:** Click the [organ/component] in this diagram
**Cognitive Target:** Visual cortex, spatial recognition
**UI Pattern:** `image_with_clickable_regions`
**Grading Mode:** `coordinate_match`
**Owner:** cortex
**Difficulty Range:** 1-3

### visual_search
**Description:** Find all [defects] in high-res image
**Cognitive Target:** Visual cortex, attention
**UI Pattern:** `image_with_multi_select`
**Grading Mode:** `set_match`
...
```

### skill-graph-architecture.md

```markdown
# Skill Graph Architecture

## Overview

The skill graph enables many-to-many mapping between atoms and skills for targeted mastery tracking.

## Database Schema

### skills Table
- Hierarchical skill taxonomy
- Bloom's taxonomy levels
- Cognitive levels

### atom_skill_weights Table
- Many-to-many linking
- Weight (0-1): How much this atom measures this skill
- is_primary flag

### learner_skill_mastery Table
- Per-skill mastery state
- FSRS parameters (retrievability, difficulty, stability)
- Confidence intervals

## Bayesian Mastery Updates

Formula:
P(mastery | correct) = ...

## FSRS Integration

Retrievability scheduling:
R(t) = e^(-t/S)
...
```

## Commit Strategy

```bash
git add docs/reference/atom-taxonomy-v2.md
git commit -m "docs(batch5b): Add 100+ atom taxonomy organized by cognitive subsystem"

git add docs/explanation/skill-graph-architecture.md
git commit -m "docs(batch5b): Add skill graph architecture documentation"

git add docs/how-to/implement-new-atom-type.md
git commit -m "docs(batch5b): Add guide for implementing new atom types"

git add docs/how-to/validate-atom-quality.md
git commit -m "docs(batch5b): Add atom quality validation guide"

git add docs/reference/greenlight-handoff-v2.md
git commit -m "docs(batch5b): Update Greenlight handoff protocol documentation"

git add README.md
git commit -m "docs(batch5b): Update README with 100+ taxonomy and skill graph"

git push -u origin batch-5b-documentation
```

---

**Reference:** Plan lines 1262-1293 | **Status:** 🔴 Pending
