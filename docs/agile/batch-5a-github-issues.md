# Batch 5a: GitHub Issues

**Branch:** `batch-5a-github-issues`
**Priority:** MEDIUM | **Effort:** 1 day | **Status:** Pending

## Objective

Create 135 GitHub issues organized by epic for all batches.

## Issue Structure

### Epic: Skill Graph Foundation (5 issues)
```bash
gh issue create \
  --title "[Batch 1] Skill Graph Database Schema" \
  --body "Create skill taxonomy and atom-skill linking tables.\n\n**Files:**\n- Migration 030_skill_graph.sql\n- Seed data skill_taxonomy_seed.sql\n\n**Status:** See batch-1-skill-graph branch" \
  --label "batch-1,database,skill-graph,enhancement" \
  --milestone "Phase 1: Foundation"
```

Issues:
1. Skill Graph Database Schema
2. SkillMasteryTracker with Bayesian Updates
3. Skill-Based Atom Selection
4. Skill Taxonomy Seed Data
5. Integration Tests

### Epic: Greenlight Integration (6 issues)

Issues:
6. GreenlightClient HTTP Client
7. SessionManager Greenlight Handoff
8. Greenlight Queue Table
9. Terminal Result Rendering
10. Retry/Fallback Strategies
11. Integration Tests with Mock Server

### Epic: Tier 1 Atom Handlers (18 issues)

One issue per handler (15 total) + 3 for batch-level work:
12-26. Individual handlers (cloze_dropdown, short_answer_exact, etc.)
27. Handler Registry Updates
28. Unit Test Suite
29. Skill Linking Integration

### Epic: JSONB Schema & Validation (103 issues)

30. Atom Envelope v2 Schema
31-130. One issue per subschema (100 total)
131. AtomValidator Class Implementation
132. Validation Pipeline Integration
133. Validation Test Suite

### Epic: Documentation (2 issues)

134. Update All Documentation Files
135. Create Implementation Guide

## GitHub CLI Script

Create `scripts/create_gh_issues.sh`:

```bash
#!/bin/bash

# Batch 1 Issues
gh issue create --title "[Batch 1] Skill Graph Database Schema" --body "..." --label "batch-1,database,skill-graph,enhancement" --milestone "Phase 1: Foundation"
gh issue create --title "[Batch 1] SkillMasteryTracker with Bayesian Updates" --body "..." --label "batch-1,mastery-tracking,skill-graph,enhancement" --milestone "Phase 1: Foundation"
# ... (135 total)

echo "Created 135 GitHub issues"
```

## Commit

```bash
git add scripts/create_gh_issues.sh
git commit -m "chore(batch5a): Add GitHub issue creation script (135 issues)"

git push -u origin batch-5a-github-issues
```

## Execution

```bash
cd ../cortex-batch-5a-github-issues
chmod +x scripts/create_gh_issues.sh
./scripts/create_gh_issues.sh
```

---

**Reference:** Plan lines 1262-1293 | **Status:** Pending
## testing and ci

- add or update tests relevant to this batch
- add or update bdd scenarios where applicable
- ensure pr-checks.yml passes before merge
