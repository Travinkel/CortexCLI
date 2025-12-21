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

## Batch-Specific Prompts

### Batch 1a: Skill Graph Database

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

DEPENDENCIES: None (this is the critical path!)
BLOCKS: Batch 1b, 1c, all Batch 3 handlers

START NOW!
```

### Batch 2a: Greenlight Client

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

DEPENDENCIES: None (runs in parallel with Batch 1)
BLOCKS: Batch 2b (SessionManager integration)

START NOW!
```

### Batch 3a: Declarative Memory Handlers

```
You are implementing 5 atom handlers for declarative memory types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-3a-handlers-declarative.md

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

DEPENDENCIES: Batch 1 must be complete (for skill linking)
BLOCKS: None (can run in parallel with 3b, 3c)

START NOW!
```

### Batch 4a: Declarative Memory Schemas

```
You are creating JSON Schema validation files for 12 declarative memory atom types.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-4a-schemas-declarative.md

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

DEPENDENCIES: Batch 3a should be complete (to validate handler behavior)
BLOCKS: None

START NOW!
```

### Batch 5a: GitHub Issues

```
You are creating 135 GitHub issues for all batches.

Read docs/ and docs/agile/ for context.

Your job: Implement batch-5a-github-issues.md

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

DEPENDENCIES: None (can run anytime)
BLOCKS: None

START NOW!
```

## Environment Setup Checklist

Before starting ANY batch, verify:

- [ ] PostgreSQL database running (for Batch 1, 2)
- [ ] Python environment activated
- [ ] Git configured (user.name, user.email)
- [ ] GitHub CLI installed and authenticated (`gh auth status`)
- [ ] Current working directory is the worktree
- [ ] Master branch is up to date

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

---

**Last Updated:** 2025-12-21
**Total Batches:** 21 (15 original + 6 subbatches)
