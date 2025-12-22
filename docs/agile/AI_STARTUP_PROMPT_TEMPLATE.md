# AI Coder Startup Prompt Template

## Quick Start (Copy-Paste Ready)

```
You are an expert software engineer working on Cortex-CLI, a DARPA-class adaptive learning system.

Read docs/ and docs/agile/ to understand the project structure and work orders.

Your job: Implement batch-<BATCH_ID>.md

CRITICAL INSTRUCTIONS:
1. Navigate to the worktree: cd ../cortex-batch-<BATCH_ID>
2. Read your work order: cat docs/agile/batch-<BATCH_ID>.md
3. Follow the checklist step-by-step
4. As you code, git add, commit, push (follow commit message conventions)
5. Create/update GitHub issues as specified in your work order
6. Do not create or update CLAUDE.md files (use docs/agile/status.md + GitHub issues instead)

COMMIT MESSAGE FORMAT:
<type>(batch<N>): <description>

Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

Types: feat, fix, docs, test, refactor, chore

IMPORTANT:
- Test each file before committing
- Push frequently (don't wait until the end)
- Check dependencies in your work order before starting
```

---

# Wave-Based Execution Strategy

Execute in waves with internal parallelization. Read PARALLELIZATION_STRATEGY.md for full details.

Total duration: 12-18 days (vs 25-36 sequential)
Peak concurrency: 6 AI coders (Wave 1)

---

## Wave 1: Infrastructure Foundation (Days 1-5)

Goal: Build skill graph and Greenlight integration foundation.

Run in parallel: 6 AI coders
Duration: 3-5 days

### Start Immediately (3 batches - no dependencies)

#### Batch 1a: Skill Graph Database (critical path - start first)

```
You are implementing the skill graph database schema for Cortex-CLI.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-1a-skill-database.md

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-1a-skill-database
2. cat docs/agile/batch-1a-skill-database.md
3. Create src/db/migrations/030_skill_graph.sql (skills, atom_skill_weights, learner_skill_mastery)
4. Create data/skill_taxonomy_seed.sql (30 skills across networking, programming, systems)
5. Test migration on local PostgreSQL database
6. git add, commit, push with proper message format
7. Create GitHub issue: "[Batch 1a] Skill Graph Database Schema"

DEPENDENCIES: None (this is the critical path)
BLOCKS: Batch 1b, 1c, all Batch 3 handlers

START NOW.
```

#### Batch 2a: Greenlight HTTP Client (start immediately)

```
You are implementing the Greenlight HTTP client for runtime atom execution.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-2a-greenlight-client.md

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-2a-greenlight-client
2. cat docs/agile/batch-2a-greenlight-client.md
3. Create src/integrations/greenlight_client.py with:
   - GreenlightAtomRequest dataclass
   - GreenlightAtomResult dataclass
   - GreenlightClient class with execute_atom(), queue_atom(), poll_execution()
4. Implement retry logic with exponential backoff
5. Write unit tests
6. git add, commit, push
7. Create GitHub issue: "[Batch 2a] Greenlight HTTP Client"

DEPENDENCIES: None (runs in parallel with Batch 1a)
BLOCKS: Batch 2b (SessionManager integration)

START NOW.
```

#### Batch 2c: Greenlight Database Queue (start immediately)

```
You are implementing the Greenlight async execution queue.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-2c-greenlight-database.md

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-2c-greenlight-database
2. cat docs/agile/batch-2c-greenlight-database.md
3. Create src/db/migrations/031_greenlight_queue.sql
4. Create queuing logic for async atom execution
5. Test migration on local PostgreSQL database
6. git add, commit, push
7. Create GitHub issue: "[Batch 2c] Greenlight Database Queue"

DEPENDENCIES: None (independent of other Wave 1 batches)
BLOCKS: None

START NOW.
```

### Start After Batch 1a Completes (2 batches)

#### Batch 1b: Skill Mastery Tracker (wait for 1a)

```
You are implementing the skill mastery tracking system with Bayesian updates.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-1b-skill-tracker.md

CRITICAL: DO NOT START until Batch 1a is complete and merged to master.

VERIFICATION BEFORE STARTING:
1. Check that Batch 1a is merged: git log --oneline | rg "batch1a"
2. Verify tables exist: psql -U postgres -d cortex_cli -c "\dt skills"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-1b-skill-tracker
2. cat docs/agile/batch-1b-skill-tracker.md
3. Create src/learning/skill_mastery_tracker.py
4. Implement SkillMasteryTracker class with Bayesian update formula
5. Implement FSRS parameter updates per skill
6. Write unit tests
7. git add, commit, push
8. Create GitHub issue: "[Batch 1b] Skill Mastery Tracker"

DEPENDENCIES: Batch 1a must be complete (needs skills, learner_skill_mastery tables)
BLOCKS: None

START AFTER BATCH 1a COMPLETES.
```

#### Batch 1c: Skill-Based Atom Selection (wait for 1a)

```
You are implementing skill-based atom selection queries.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-1c-skill-selection.md

CRITICAL: DO NOT START until Batch 1a is complete and merged to master.

VERIFICATION BEFORE STARTING:
1. Check that Batch 1a is merged: git log --oneline | rg "batch1a"
2. Verify tables exist: psql -U postgres -d cortex_cli -c "\dt atom_skill_weights"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-1c-skill-selection
2. cat docs/agile/batch-1c-skill-selection.md
3. Extend src/learning/atom_selector.py with select_atoms_by_skill_gap()
4. Implement Z-score ranking for skill-targeted atoms
5. Write unit tests
6. git add, commit, push
7. Create GitHub issue: "[Batch 1c] Skill-Based Atom Selection"

DEPENDENCIES: Batch 1a must be complete (needs skills, atom_skill_weights tables)
BLOCKS: All Batch 3 handlers (they use skill-based selection)

START AFTER BATCH 1a COMPLETES.
```

### Start After Batch 2a Completes (1 batch)

#### Batch 2b: Greenlight SessionManager Integration (wait for 2a)

```
You are integrating Greenlight handoff into SessionManager.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-2b-greenlight-integration.md

CRITICAL: DO NOT START until Batch 2a is complete and merged to master.

VERIFICATION BEFORE STARTING:
1. Check that Batch 2a is merged: git log --oneline | rg "batch2a"
2. Verify GreenlightClient exists: ls -la src/integrations/greenlight_client.py

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-2b-greenlight-integration
2. cat docs/agile/batch-2b-greenlight-integration.md
3. Extend src/learning/session_manager.py with handoff logic
4. Implement _handoff_to_greenlight() method
5. Add Greenlight result rendering in terminal
6. Write integration tests
7. git add, commit, push
8. Create GitHub issue: "[Batch 2b] Greenlight SessionManager Integration"

DEPENDENCIES: Batch 2a must be complete (needs GreenlightClient)
BLOCKS: None

START AFTER BATCH 2a COMPLETES.
```

### Start After Wave 1 Base Completes (1 batch)

#### Batch 2d: Quality Gates (BDD + CI)

```
You are implementing the BDD harness and CI quality gates.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-2d-quality-ci.md

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-2d-quality-ci
2. cat docs/agile/batch-2d-quality-ci.md
3. Set up BDD test scaffolding (features/ + step definitions)
4. Wire BDD into CI (GitHub Actions)
5. Add CI gates for migrations, unit tests, and linting
6. git add, commit, push
7. Create GitHub issue: "[Batch 2d] Quality Gates (BDD + CI)"

DEPENDENCIES: Batch 1a and Batch 2a merged (base schema + integrations)
BLOCKS: Wave 2 (handlers should land with tests wired)

START AFTER WAVE 1 BASE COMPLETES.
```

### Wave 1 Success Criteria

- All 6 core batches merged to master
- Skill graph operational (3 tables + 30 seed skills)
- Greenlight client operational (HTTP client + queue)
- All unit tests passing
- BDD/CI gates established (if Batch 2d is completed)

---

## Wave 2: Atom Handlers (Days 6-10)

Goal: Implement 15 atom handlers (5 declarative, 5 procedural, 5 diagnostic).

Run in parallel: 3 AI coders
Duration: 4-5 days

CRITICAL: DO NOT START WAVE 2 until ALL of Wave 1 is complete.

Refer to the batch files for exact checklists.

---

## Wave 3: JSON Schemas (Days 11-13)

Goal: Create 100 JSON Schema files for all atom types.

Run in parallel: 5 AI coders
Duration: 2-3 days

CRITICAL: DO NOT START WAVE 3 until ALL of Wave 2 is complete.

Refer to the batch files for exact checklists.

---

## Wave 4: Documentation and Issues (Days 14-16)

Goal: Create documentation and GitHub issues.

Run in parallel: 2 AI coders
Duration: 2-3 days

CRITICAL: DO NOT START WAVE 4 until ALL of Wave 3 is complete.

Refer to the batch files for exact checklists.

---

## Wave 5: Knowledge Injection (Days 17-18)

Goal: Connect Cortex-CLI to ResearchEngine KnowledgeBase for evidence-grounded atom generation.

Run in parallel: 1 AI coder
Duration: 1-2 days

CRITICAL: DO NOT START WAVE 5 until KB is populated and Wave 4 is complete.

Refer to batch-6-knowledge-injection.md for the checklist.

---

## Progress Tracking

Use docs/agile/status.md for progress updates. Keep GitHub issues and PRs in sync.
