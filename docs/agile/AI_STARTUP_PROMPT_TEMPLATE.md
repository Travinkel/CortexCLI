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
6. Update CLAUDE.md with progress status after each major milestone

COMMIT MESSAGE FORMAT:
<type>(batch<N>): <description>

🤖 Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

Types: feat, fix, docs, test, refactor, chore

IMPORTANT:
- Test each file before committing
- Push frequently (don't wait until the end)
- If blocked, document the blocker in CLAUDE.md and move to next task
- Check dependencies in your work order before starting
```

---

# 🌊 WAVE-BASED EXECUTION STRATEGY

Execute in 4 waves with internal parallelization. **Read PARALLELIZATION_STRATEGY.md for full details.**

**Total Duration:** 12-16 days (vs 25-36 sequential)
**Peak Concurrency:** 6 AI coders (Wave 1)

---

## 🌊 Wave 1: Infrastructure Foundation (Days 1-5)

**Goal:** Build skill graph and Greenlight integration foundation.

**Run in Parallel:** 6 AI coders
**Duration:** 3-5 days

### 🚀 Start Immediately (3 batches - no dependencies)

#### Batch 1a: Skill Graph Database ⚡ **CRITICAL PATH - START FIRST**

```
You are implementing the skill graph database schema for Cortex-CLI.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-1a-skill-database.md

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-1a-skill-database
2. cat docs/agile/batch-1a-skill-database.md
3. Create src/db/migrations/030_skill_graph.sql (3 tables: skills, atom_skill_weights, learner_skill_mastery)
4. Create data/skill_taxonomy_seed.sql (30 skills across networking, programming, systems)
5. Test migration on local PostgreSQL database
6. git add, commit, push with proper message format
7. Create GitHub issue: "[Batch 1a] Skill Graph Database Schema"
8. Update CLAUDE.md with completion status

⚠️ DEPENDENCIES: None (this is the critical path!)
🔒 BLOCKS: Batch 1b, 1c, all Batch 3 handlers

START NOW!
```

#### Batch 2a: Greenlight HTTP Client ⚡ **START IMMEDIATELY**

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
8. Update CLAUDE.md

⚠️ DEPENDENCIES: None (runs in parallel with Batch 1a)
🔒 BLOCKS: Batch 2b (SessionManager integration)

START NOW!
```

#### Batch 2c: Greenlight Database Queue ⚡ **START IMMEDIATELY**

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
8. Update CLAUDE.md

⚠️ DEPENDENCIES: None (independent of other Wave 1 batches)
🔒 BLOCKS: None

START NOW!
```

### ⏳ Start After Batch 1a Completes (2 batches)

#### Batch 1b: Skill Mastery Tracker 🕒 **WAIT FOR 1a**

```
You are implementing the skill mastery tracking system with Bayesian updates.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-1b-skill-tracker.md

⚠️ CRITICAL: DO NOT START until Batch 1a is complete and merged to master!

VERIFICATION BEFORE STARTING:
1. Check that Batch 1a is merged: git log --oneline | grep "batch1a"
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
9. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 1a must be complete (needs skills, learner_skill_mastery tables)
🔒 BLOCKS: None

START AFTER BATCH 1a COMPLETES!
```

#### Batch 1c: Skill-Based Atom Selection 🕒 **WAIT FOR 1a**

```
You are implementing skill-based atom selection queries.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-1c-skill-selection.md

⚠️ CRITICAL: DO NOT START until Batch 1a is complete and merged to master!

VERIFICATION BEFORE STARTING:
1. Check that Batch 1a is merged: git log --oneline | grep "batch1a"
2. Verify tables exist: psql -U postgres -d cortex_cli -c "\dt atom_skill_weights"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-1c-skill-selection
2. cat docs/agile/batch-1c-skill-selection.md
3. Extend src/learning/atom_selector.py with select_atoms_by_skill_gap()
4. Implement Z-score ranking for skill-targeted atoms
5. Write unit tests
6. git add, commit, push
7. Create GitHub issue: "[Batch 1c] Skill-Based Atom Selection"
8. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 1a must be complete (needs skills, atom_skill_weights tables)
🔒 BLOCKS: All Batch 3 handlers (they use skill-based selection)

START AFTER BATCH 1a COMPLETES!
```

### ⏳ Start After Batch 2a Completes (1 batch)

#### Batch 2b: Greenlight SessionManager Integration 🕒 **WAIT FOR 2a**

```
You are integrating Greenlight handoff into SessionManager.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-2b-greenlight-integration.md

⚠️ CRITICAL: DO NOT START until Batch 2a is complete and merged to master!

VERIFICATION BEFORE STARTING:
1. Check that Batch 2a is merged: git log --oneline | grep "batch2a"
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
9. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 2a must be complete (needs GreenlightClient)
🔒 BLOCKS: None

START AFTER BATCH 2a COMPLETES!
```

### ✅ Wave 1 Success Criteria

- [ ] All 6 batches merged to master
- [ ] Skill graph operational (3 tables + 30 seed skills)
- [ ] Greenlight client operational (HTTP client + queue)
- [ ] All unit tests passing

---

## 🌊 Wave 2: Atom Handlers (Days 6-10)

**Goal:** Implement 15 atom handlers (5 declarative, 5 procedural, 5 diagnostic).

**Run in Parallel:** 3 AI coders
**Duration:** 4-5 days

⚠️ **CRITICAL:** DO NOT START WAVE 2 until ALL of Wave 1 is complete!

### 🚀 Start After Wave 1 Complete (3 batches)

#### Batch 3a: Declarative Memory Handlers

```
You are implementing 5 atom handlers for declarative memory types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-3a-handlers-declarative.md

⚠️ CRITICAL: DO NOT START until Wave 1 is complete (Batches 1a, 1b, 1c merged)!

VERIFICATION BEFORE STARTING:
1. Check Wave 1 complete: git log --oneline | grep -E "batch1[abc]"
2. Verify skill tables exist: psql -U postgres -d cortex_cli -c "\dt skills"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-3a-handlers-declarative
2. cat docs/agile/batch-3a-handlers-declarative.md
3. Implement 5 handlers:
   - cloze_dropdown.py
   - short_answer_exact.py
   - short_answer_regex.py
   - list_recall.py
   - ordered_list_recall.py
4. Each handler must implement AtomHandler interface
5. Add Rich UI rendering
6. Link to skills (from Batch 1)
7. Write unit tests for each handler
8. Register in src/cortex/atoms/__init__.py
9. git add, commit (one commit per handler), push
10. Create GitHub issue: "[Batch 3a] Declarative Memory Handlers (5 types)"
11. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 1a, 1b, 1c must be complete (for skill linking)
🔒 BLOCKS: Batch 4a (schemas need handlers to validate against)

START AFTER WAVE 1 COMPLETES!
```

#### Batch 3b: Procedural/Sequential Handlers

```
You are implementing 5 atom handlers for procedural/sequential types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-3b-handlers-procedural.md

⚠️ CRITICAL: DO NOT START until Wave 1 is complete!

VERIFICATION BEFORE STARTING:
1. Check Wave 1 complete: git log --oneline | grep -E "batch1[abc]"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-3b-handlers-procedural
2. cat docs/agile/batch-3b-handlers-procedural.md
3. Implement 5 handlers:
   - faded_parsons.py
   - distractor_parsons.py
   - timeline_ordering.py
   - sql_query_builder.py
   - process_flow.py
4. Each handler must implement AtomHandler interface
5. Add Rich UI rendering
6. Link to skills
7. Write unit tests
8. Register in src/cortex/atoms/__init__.py
9. git add, commit, push
10. Create GitHub issue: "[Batch 3b] Procedural Handlers (5 types)"
11. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 1a, 1b, 1c must be complete
🔒 BLOCKS: Batch 4b (procedural schemas)

START AFTER WAVE 1 COMPLETES!
```

#### Batch 3c: Metacognitive/Diagnostic Handlers

```
You are implementing 5 atom handlers for metacognitive/diagnostic types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-3c-handlers-diagnostic.md

⚠️ CRITICAL: DO NOT START until Wave 1 is complete!

VERIFICATION BEFORE STARTING:
1. Check Wave 1 complete: git log --oneline | grep -E "batch1[abc]"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-3c-handlers-diagnostic
2. cat docs/agile/batch-3c-handlers-diagnostic.md
3. Implement 5 handlers:
   - script_concordance_test.py
   - key_feature_problem.py
   - boundary_value_analysis.py
   - confidence_slider.py
   - effort_rating.py
4. Each handler must implement AtomHandler interface
5. Add Rich UI rendering
6. Link to skills
7. Write unit tests
8. Register in src/cortex/atoms/__init__.py
9. git add, commit, push
10. Create GitHub issue: "[Batch 3c] Diagnostic Handlers (5 types)"
11. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 1a, 1b, 1c must be complete
🔒 BLOCKS: Batch 4c (diagnostic schemas)

START AFTER WAVE 1 COMPLETES!
```

### ✅ Wave 2 Success Criteria

- [ ] All 3 batches merged to master
- [ ] 15 new atom handlers implemented
- [ ] All handlers linked to skills
- [ ] Unit tests passing
- [ ] Registered in handler registry

---

## 🌊 Wave 3: JSON Schemas (Days 11-13)

**Goal:** Create 100 JSON Schema files for all atom types.

**Run in Parallel:** 5 AI coders
**Duration:** 2-3 days

⚠️ **CRITICAL:** DO NOT START WAVE 3 until ALL of Wave 2 is complete!

### 🚀 Start After Wave 2 Complete (5 batches)

#### Batch 4a: Declarative Memory Schemas

```
You are creating JSON Schema validation files for 12 declarative memory atom types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-4a-schemas-declarative.md

⚠️ CRITICAL: DO NOT START until Wave 2 is complete (Batches 3a, 3b, 3c merged)!

VERIFICATION BEFORE STARTING:
1. Check Wave 2 complete: git log --oneline | grep -E "batch3[abc]"
2. Verify handlers exist: ls -la src/cortex/atoms/cloze_dropdown.py

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-4a-schemas-declarative
2. cat docs/agile/batch-4a-schemas-declarative.md
3. Create 12 JSON Schema files in docs/reference/atom-subschemas/:
   - flashcard.schema.json
   - reverse_flashcard.schema.json
   - image_to_term.schema.json
   - audio_to_term.schema.json
   - cloze_deletion.schema.json
   - cloze_dropdown.schema.json
   - cloze_bank.schema.json
   - symbolic_cloze.schema.json
   - short_answer_exact.schema.json
   - short_answer_regex.schema.json
   - list_recall.schema.json
   - ordered_list_recall.schema.json
4. Each schema must follow JSON Schema draft-07 format
5. Test each schema with sample atom data
6. git add all schemas, commit, push
7. Create GitHub issue: "[Batch 4a] Declarative Memory Schemas (12 types)"
8. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 3a should be complete (to validate handler behavior)
🔒 BLOCKS: Batch 5a, 5b (documentation needs schemas complete)

START AFTER WAVE 2 COMPLETES!
```

#### Batch 4b: Procedural/Sequential Schemas

```
You are creating JSON Schema validation files for 11 procedural/sequential atom types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-4b-schemas-procedural.md

⚠️ CRITICAL: DO NOT START until Wave 2 is complete!

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-4b-schemas-procedural
2. cat docs/agile/batch-4b-schemas-procedural.md
3. Create 11 JSON Schema files (parsons variants, timeline_ordering, etc.)
4. Follow JSON Schema draft-07 format
5. Test schemas
6. git add, commit, push
7. Create GitHub issue: "[Batch 4b] Procedural Schemas (11 types)"
8. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 3b should be complete
🔒 BLOCKS: Batch 5a, 5b

START AFTER WAVE 2 COMPLETES!
```

#### Batch 4c: Diagnostic/Reasoning Schemas

```
You are creating JSON Schema validation files for 9 diagnostic/reasoning atom types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-4c-schemas-diagnostic.md

⚠️ CRITICAL: DO NOT START until Wave 2 is complete!

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-4c-schemas-diagnostic
2. cat docs/agile/batch-4c-schemas-diagnostic.md
3. Create 9 JSON Schema files
4. Follow JSON Schema draft-07 format
5. Test schemas
6. git add, commit, push
7. Create GitHub issue: "[Batch 4c] Diagnostic Schemas (9 types)"
8. Update CLAUDE.md

⚠️ DEPENDENCIES: Batch 3c should be complete
🔒 BLOCKS: Batch 5a, 5b

START AFTER WAVE 2 COMPLETES!
```

#### Batch 4d: Generative/Creative Schemas

```
You are creating JSON Schema validation files for 8 generative/creative atom types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-4d-schemas-generative.md

⚠️ CRITICAL: DO NOT START until Wave 2 is complete!

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-4d-schemas-generative
2. cat docs/agile/batch-4d-schemas-generative.md
3. Create 8 JSON Schema files
4. Follow JSON Schema draft-07 format
5. Test schemas
6. git add, commit, push
7. Create GitHub issue: "[Batch 4d] Generative Schemas (8 types)"
8. Update CLAUDE.md

⚠️ DEPENDENCIES: Wave 2 should be complete (can start earlier if needed)
🔒 BLOCKS: Batch 5a, 5b

START AFTER WAVE 2 COMPLETES!
```

#### Batch 4e: Advanced/CS-Specific Schemas

```
You are creating JSON Schema validation files for 60 advanced/CS-specific atom types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-4e-schemas-advanced.md

⚠️ CRITICAL: DO NOT START until Wave 2 is complete!
⚠️ NOTE: This is the largest batch (60 schemas) - may take longer than others

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-4e-schemas-advanced
2. cat docs/agile/batch-4e-schemas-advanced.md
3. Create 60 JSON Schema files (matching, categorization, hierarchy, CS-specific types)
4. Follow JSON Schema draft-07 format
5. Test schemas
6. git add, commit, push
7. Create GitHub issue: "[Batch 4e] Advanced Schemas (60 types)"
8. Update CLAUDE.md

⚠️ DEPENDENCIES: Wave 2 should be complete
🔒 BLOCKS: Batch 5a, 5b

START AFTER WAVE 2 COMPLETES!
```

### ✅ Wave 3 Success Criteria

- [ ] All 5 batches merged to master
- [ ] 100 JSON Schema files created
- [ ] All schemas validate correctly
- [ ] AtomValidator class implemented

---

## 🌊 Wave 4: Documentation & Issues (Days 14-16)

**Goal:** Create comprehensive documentation and GitHub issues.

**Run in Parallel:** 2 AI coders
**Duration:** 2-3 days

⚠️ **CRITICAL:** DO NOT START WAVE 4 until ALL of Wave 3 is complete!

### 🚀 Start After Wave 3 Complete (2 batches)

#### Batch 5a: GitHub Issues

```
You are creating 135 GitHub issues for all batches.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-5a-github-issues.md

⚠️ CRITICAL: DO NOT START until Wave 3 is complete (all schemas merged)!

VERIFICATION BEFORE STARTING:
1. Check Wave 3 complete: git log --oneline | grep -E "batch4[abcde]"
2. Verify schemas exist: ls -la docs/reference/atom-subschemas/ | wc -l

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-5a-github-issues
2. cat docs/agile/batch-5a-github-issues.md
3. Create scripts/create_gh_issues.sh with all 135 issue creation commands
4. Organize issues by epic:
   - Skill Graph Foundation (5 issues)
   - Greenlight Integration (6 issues)
   - Tier 1 Atom Handlers (18 issues)
   - JSONB Schema & Validation (103 issues)
   - Documentation (2 issues)
5. Use proper labels and milestones
6. git add, commit, push
7. Execute the script to create all issues
8. Update CLAUDE.md with issue numbers

⚠️ DEPENDENCIES: All previous waves complete (for accurate issue creation)
🔒 BLOCKS: None

START AFTER WAVE 3 COMPLETES!
```

#### Batch 5b: Documentation

```
You are creating/updating 6 documentation files.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-5b-documentation.md

⚠️ CRITICAL: DO NOT START until Wave 3 is complete!

VERIFICATION BEFORE STARTING:
1. Check Wave 3 complete: git log --oneline | grep -E "batch4[abcde]"

CRITICAL INSTRUCTIONS:
1. cd ../cortex-batch-5b-documentation
2. cat docs/agile/batch-5b-documentation.md
3. Create/update 6 documentation files:
   - docs/reference/atom-taxonomy-v2.md (100+ taxonomy)
   - docs/explanation/skill-graph-architecture.md
   - docs/how-to/implement-new-atom-type.md
   - docs/how-to/validate-atom-quality.md
   - docs/reference/greenlight-handoff-v2.md
   - README.md (update with 100+ taxonomy)
4. git add, commit (one commit per doc), push
5. Create GitHub issue: "[Batch 5b] Documentation"
6. Update CLAUDE.md

⚠️ DEPENDENCIES: All previous waves complete (for accurate documentation)
🔒 BLOCKS: None

START AFTER WAVE 3 COMPLETES!
```

### ✅ Wave 4 Success Criteria

- [ ] All 2 batches merged to master
- [ ] 135 GitHub issues created
- [ ] 6 documentation files updated
- [ ] README reflects 100+ taxonomy

---

## 📊 Wave Execution Summary

| Wave | Batches | AI Coders | Duration | Start Condition |
|------|---------|-----------|----------|-----------------|
| **Wave 1** | 1a, 1b, 1c, 2a, 2b, 2c | 6 | Days 1-5 | Immediate |
| **Wave 2** | 3a, 3b, 3c | 3 | Days 6-10 | After Wave 1 complete |
| **Wave 3** | 4a, 4b, 4c, 4d, 4e | 5 | Days 11-13 | After Wave 2 complete |
| **Wave 4** | 5a, 5b | 2 | Days 14-16 | After Wave 3 complete |

**Total:** 16 batches, 12-16 days

---

## Environment Setup Checklist

Before starting ANY batch, verify:

- [x] PostgreSQL database running (for Batch 1, 2)
- [x] Python environment activated
- [x] Git configured (user.name, user.email)
- [x] GitHub CLI installed and authenticated (`gh auth status`)
- [x] Current working directory is the worktree
- [x] Master branch is up to date

## Progress Tracking

Update `CLAUDE.md` in your worktree after each milestone:

```markdown
# Batch <N> Progress

**Status:** 🟡 In Progress
**Started:** 2025-12-21 14:30
**AI Coder:** Claude Sonnet 4.5

## Completed
- [x] Task 1
- [x] Task 2

## In Progress
- [ ] Task 3 (50% complete)

## Blocked
- [ ] Task 4 (waiting for Batch X to complete)

## Commits
- abc1234: feat(batch<N>): Task 1 description
- def5678: feat(batch<N>): Task 2 description

## GitHub Issues
- #42: [Batch <N>] Feature X (created)
- #43: [Batch <N>] Feature Y (updated)

## Notes
- Migration tested successfully
- All unit tests passing
- Ready for code review
```

## Tips for AI Coders

1. **Read the work order FIRST** - Don't skip the checklist
2. **Test frequently** - Don't wait until the end
3. **Commit small** - One logical change per commit
4. **Push early** - Don't accumulate 10 commits before pushing
5. **Update issues** - Keep GitHub in sync with progress
6. **Document blockers** - If stuck, write it down and move on
7. **Follow conventions** - Commit messages, code style, file naming
8. **Validate dependencies** - Check if prerequisite batches are complete
9. **Respect wave boundaries** - DO NOT start next wave until previous complete

## Troubleshooting

### "Branch already exists"
```bash
git worktree list  # Check if already created
cd ../cortex-batch-<N>  # Navigate to existing worktree
```

### "Database connection failed"
```bash
psql -U postgres -d cortex_cli -c "SELECT 1;"  # Test connection
```

### "Migration already applied"
```bash
psql -U postgres -d cortex_cli -c "\dt"  # Check existing tables
# If tables exist, skip migration or create rollback
```

### "Pre-commit hook failing"
```bash
git commit --no-verify -m "..."  # Skip hooks temporarily
# Better: Fix the issue or activate virtualenv
```

### "Dependency not met"
```bash
# Check if prerequisite batch is merged
git log --oneline | grep "batch<N>"

# If not merged, wait or switch to a different batch
# Update your CLAUDE.md with blocker status
```

---

**Last Updated:** 2025-12-21
**Total Batches:** 16 (across 4 waves)
**Strategy:** Wave-based parallelization with dependency management
