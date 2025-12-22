# Parallelization Strategy: Sequential vs Parallel Execution

## Recommended Approach

Wave-based parallelization. Respect dependencies, parallelize within waves.

Total time: 12-18 days (vs 25-36 sequential)
Peak concurrency: 6 AI coders (Wave 1)

---

## Wave Structure

### Wave 1: Infrastructure Foundation (Days 1-5)

Run in parallel (6 AI coders):
- Batch 1a: Skill Graph Database
- Batch 1b: Skill Mastery Tracker (waits for 1a)
- Batch 1c: Skill-Based Atom Selection (waits for 1a)
- Batch 2a: Greenlight HTTP Client
- Batch 2b: Greenlight SessionManager Integration (waits for 2a)
- Batch 2c: Greenlight Database Queue

Dependencies:
- Batch 1b depends on Batch 1a (tables must exist)
- Batch 1c depends on Batch 1a (tables must exist)
- Batch 2b depends on Batch 2a (client must exist)
- Batch 2c is independent

Merge strategy:
```bash
cd E:\Repo\cortex-cli
git checkout master
git merge batch-1a-skill-database
git merge batch-1b-skill-tracker
git merge batch-1c-skill-selection
git merge batch-2a-greenlight-client
git merge batch-2b-greenlight-integration
git merge batch-2c-greenlight-database
git push
```

### Wave 1.5: Quality Gates (BDD + CI)

Run in parallel (1 AI coder):
- Batch 2d: Quality Gates (BDD + CI)

Dependencies:
- Batch 1a merged (schema exists)
- Batch 2a merged (integration hooks exist)

### Wave 2: Atom Handlers (Days 6-10)

Run in parallel (3 AI coders):
- Batch 3a: Declarative Memory Handlers
- Batch 3b: Procedural/Sequential Handlers
- Batch 3c: Metacognitive/Diagnostic Handlers

Dependencies:
- Wave 1 complete (skill linking)

### Wave 3: JSON Schemas (Days 11-13)

Run in parallel (5 AI coders):
- Batch 4a: Declarative Memory Schemas (12 types)
- Batch 4b: Procedural/Sequential Schemas (11 types)
- Batch 4c: Diagnostic/Reasoning Schemas (9 types)
- Batch 4d: Generative/Creative Schemas (8 types)
- Batch 4e: Advanced/CS-Specific Schemas (60 types)

Dependencies:
- Ideally Wave 2 complete (to validate against handlers)

### Wave 4: Documentation and Issues (Days 14-16)

Run in parallel (2 AI coders):
- Batch 5a: GitHub Issues
- Batch 5b: Documentation

Dependencies:
- Ideally Wave 3 complete (accurate documentation)

### Wave 5: Knowledge Injection (Days 17-18)

Run in parallel (1 AI coder):
- Batch 6: Knowledge Injection Pipeline

Dependencies:
- KnowledgeBase populated
- Wave 4 complete

---

## Monitoring Progress

Use docs/agile/status.md for progress updates. Keep GitHub issues and PRs in sync.

---

Last Updated: 2025-12-21
Recommended Approach: Wave-based parallelization
Expected Completion: 12-18 days (vs 25-36 sequential)
