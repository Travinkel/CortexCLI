# Batch 3b: Procedural & Sequential Handlers

You are an expert software engineer working on Cortex-CLI, a DARPA-class adaptive learning system.

## Your Assignment

Implement 5 atom handlers for procedural/sequential knowledge (step ordering, process building).

## Atom Types to Implement

1. **faded_parsons** - Reorder lines + fill in 1-2 blanks (hybrid parsons + cloze)
2. **distractor_parsons** - Reorder lines, discard 3 fake lines
3. **timeline_ordering** - Drag events into chronological order
4. **sql_query_builder** - Drag blocks (SELECT, FROM, WHERE) to form query
5. **equation_balancing** - Adjust coefficients to balance equations

## Quick Start

```bash
# You are already in the worktree
# Read the full work order:
cat ../cortex-cli/docs/agile/batch-3b-handlers-procedural.md

# Check existing handler structure:
ls -la src/cortex/atoms/
cat src/cortex/atoms/__init__.py

# Reference the existing parsons handler:
cat src/cortex/atoms/parsons.py
```

## Files to Create

```
src/cortex/atoms/
- faded_parsons.py         (~180 lines)
- distractor_parsons.py    (~200 lines)
- timeline_ordering.py     (~120 lines)
- sql_query_builder.py     (~150 lines)
- equation_balancing.py    (~140 lines)
```

## Implementation Notes

**faded_parsons:** Hybrid of parsons + cloze
```python
lines = ["config terminal", "___ ospf 1", "network 10.1.1.0 0.0.0.255 ___"]
blanks = {"1": "router", "2": "area 0"}
```

**distractor_parsons:** Parsons + invalid lines
```python
correct_lines = [...]  # n correct lines
distractors = [...]    # 3 fake lines to discard
```

**timeline_ordering:** Date-based sorting
```python
events = [
    {"year": 1969, "event": "ARPANET created"},
    {"year": 1989, "event": "WWW invented"},
]
```

## Commit Strategy

```bash
# One commit per handler
git add src/cortex/atoms/faded_parsons.py tests/test_faded_parsons.py
git commit -m "feat(batch3b): Add faded_parsons handler with hybrid parsons+cloze

Generated with Claude Code

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Repeat for each handler, then:
git push -u origin batch-3b-handlers-procedural
```

## Success Criteria

- [ ] All 5 handlers implemented
- [ ] Unit tests pass (>80% coverage)
- [ ] Registered in handler registry
- [ ] Grading logic handles partial credit

## Dependencies

- Wave 1 complete (skill graph, Greenlight) - VERIFIED
- Existing parsons handler for reference

## Reference

Full work order: `../cortex-cli/docs/agile/batch-3b-handlers-procedural.md`
