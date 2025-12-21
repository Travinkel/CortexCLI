# Batch 3b: Procedural & Sequential Handlers

**Branch:** `batch-3b-handlers-procedural`
**Priority:** 🟡 HIGH | **Effort:** 3-4 days | **Status:** 🔴 Pending

## Atom Types (5)

1. **faded_parsons** - Reorder lines + fill in 1-2 blanks
2. **distractor_parsons** - Reorder lines, discard 3 fake lines
3. **timeline_ordering** - Drag historical events into chronological order
4. **sql_query_builder** - Drag blocks (SELECT, FROM, WHERE) to form query
5. **equation_balancing** - Adjust coefficients to balance chemical reaction

## Files to Create

- `src/cortex/atoms/faded_parsons.py` (~180 lines)
- `src/cortex/atoms/distractor_parsons.py` (~200 lines)
- `src/cortex/atoms/timeline_ordering.py` (~120 lines)
- `src/cortex/atoms/sql_query_builder.py` (~150 lines)
- `src/cortex/atoms/equation_balancing.py` (~140 lines)

## Implementation Notes

**faded_parsons:** Hybrid of parsons + cloze
```python
# Lines to order + blank positions
lines = ["config terminal", "___ ospf 1", "network 10.1.1.0 0.0.0.255 ___"]
blanks = {"1": "router", "2": "area 0"}
```

**distractor_parsons:** Parsons + invalid lines
```python
correct_lines = [...] # n lines
distractors = [...] # 3 fake lines
all_lines = shuffle(correct_lines + distractors)
```

**timeline_ordering:** Date-based sorting
```python
events = [
    {"year": 1969, "event": "ARPANET created"},
    {"year": 1989, "event": "WWW invented"},
    {"year": 1991, "event": "First website"}
]
# User must sort by year
```

## Commit Strategy

One commit per handler + final registration commit.

## Reference

Plan lines 894-1079 (Tier 1 handlers section)

---

**Status:** 🔴 Pending
