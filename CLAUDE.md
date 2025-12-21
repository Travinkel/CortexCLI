# Batch 3a: Declarative Memory Handlers

You are an expert software engineer working on Cortex-CLI, a DARPA-class adaptive learning system.

## Your Assignment

Implement 5 atom handlers for declarative memory types (factual recall, recognition).

## Atom Types to Implement

1. **cloze_dropdown** - Cloze deletion with dropdown selection
2. **short_answer_exact** - Exact string match grading
3. **short_answer_regex** - Regex pattern match for typo tolerance
4. **list_recall** - Order-independent set recall
5. **ordered_list_recall** - Order-dependent sequence recall

## Quick Start

```bash
# You are already in the worktree
# Read the full work order:
cat ../cortex-cli/docs/agile/batch-3a-handlers-declarative.md

# Check existing handler structure:
ls -la src/cortex/atoms/
cat src/cortex/atoms/__init__.py
```

## Files to Create

```
src/cortex/atoms/
- cloze_dropdown.py        (~100 lines)
- short_answer_exact.py    (~80 lines)
- short_answer_regex.py    (~120 lines)
- list_recall.py           (~150 lines)
- ordered_list_recall.py   (~160 lines)
```

## Handler Interface

Each handler must implement:
- `validate()` - Validate atom schema
- `present()` - Rich CLI presentation
- `grade()` - Score user response
- Partial credit logic where applicable

## Commit Strategy

```bash
# One commit per handler
git add src/cortex/atoms/cloze_dropdown.py tests/test_cloze_dropdown.py
git commit -m "feat(batch3a): Add cloze_dropdown handler with dropdown selection

Generated with Claude Code

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Repeat for each handler, then:
git push -u origin batch-3a-handlers-declarative
```

## Success Criteria

- [ ] All 5 handlers implemented
- [ ] Unit tests pass (>80% coverage)
- [ ] Registered in handler registry (`__init__.py`)
- [ ] Rich UI rendering works

## Dependencies

- Wave 1 complete (skill graph, Greenlight) - VERIFIED
- Existing `AtomHandler` base class

## Reference

Full work order: `../cortex-cli/docs/agile/batch-3a-handlers-declarative.md`
