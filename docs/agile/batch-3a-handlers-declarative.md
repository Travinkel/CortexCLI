# Batch 3a: Declarative Memory Handlers

**Branch:** `batch-3a-handlers-declarative`
**Worktree:** `../cortex-batch-3a-handlers-declarative`
**Priority:** 🟡 HIGH (Content - 5 new atom types)
**Estimated Effort:** 3-4 days
**Status:** 🔴 Pending

## Objective

Implement 5 atom handlers for declarative memory types (factual recall, recognition).

## Atom Types

1. **cloze_dropdown** - Cloze deletion with dropdown selection (lower difficulty)
2. **short_answer_exact** - String match
3. **short_answer_regex** - Fuzzy match (accepts typos/variations)
4. **list_recall** - Order-independent recall
5. **ordered_list_recall** - Order-dependent recall

## Dependencies

- ✅ Existing `AtomHandler` base class
- ✅ Batch 1 complete (for skill linking)

## Checklist

### For Each Handler:

- [ ] Create `src/cortex/atoms/<type>.py`
- [ ] Implement `AtomHandler` interface
- [ ] Add `validate()` method
- [ ] Add `present()` method with Rich UI
- [ ] Add grading logic
- [ ] Add hint/partial-credit logic
- [ ] Link to skills (from Batch 1)
- [ ] Create unit tests
- [ ] Register in `src/cortex/atoms/__init__.py`

## File Structure

```
src/cortex/atoms/
├── cloze_dropdown.py        (~100 lines)
├── short_answer_exact.py    (~80 lines)
├── short_answer_regex.py    (~120 lines)
├── list_recall.py           (~150 lines)
├── ordered_list_recall.py   (~160 lines)
└── __init__.py              (update)
```

## Implementation Guide

### cloze_dropdown.py

**UI Pattern:**
```
The OSI model has ___ layers.

Options:
 1. five
 2. seven  ✓
 3. nine
 4. twelve

Your answer: _
```

**Code Template:** Plan lines 982-1079

### short_answer_exact.py

**Grading:** Exact string match (case-insensitive by default)

```python
def _grade(self, user_answer: str, correct: str, case_sensitive: bool) -> bool:
    if not case_sensitive:
        return user_answer.lower().strip() == correct.lower().strip()
    return user_answer.strip() == correct.strip()
```

### short_answer_regex.py

**Grading:** Regex pattern match

```python
import re

def _grade(self, user_answer: str, pattern: str) -> bool:
    return bool(re.fullmatch(pattern, user_answer, re.IGNORECASE))
```

**Example:** Pattern `router\s*ospf\s*\d+` matches "router ospf 1", "router  ospf  10", etc.

### list_recall.py

**Grading:** Set match (order doesn't matter)

```python
def _grade(self, user_answers: list[str], correct: list[str]) -> dict:
    user_set = {a.lower().strip() for a in user_answers}
    correct_set = {c.lower().strip() for c in correct}

    return {
        "is_correct": user_set == correct_set,
        "partial_score": len(user_set & correct_set) / len(correct_set),
        "missing": list(correct_set - user_set),
        "extra": list(user_set - correct_set)
    }
```

### ordered_list_recall.py

**Grading:** Sequence match (order matters)

```python
def _grade(self, user_answers: list[str], correct: list[str]) -> dict:
    correct_count = sum(1 for u, c in zip(user_answers, correct) if u.lower().strip() == c.lower().strip())

    return {
        "is_correct": user_answers == correct,
        "partial_score": correct_count / len(correct),
        "correct_positions": [i for i, (u, c) in enumerate(zip(user_answers, correct)) if u.lower().strip() == c.lower().strip()]
    }
```

## Commit Strategy

```bash
git add src/cortex/atoms/cloze_dropdown.py tests/test_cloze_dropdown.py
git commit -m "feat(batch3a): Add cloze_dropdown handler with dropdown selection"

git add src/cortex/atoms/short_answer_exact.py tests/test_short_answer_exact.py
git commit -m "feat(batch3a): Add short_answer_exact handler with string match"

git add src/cortex/atoms/short_answer_regex.py tests/test_short_answer_regex.py
git commit -m "feat(batch3a): Add short_answer_regex handler with pattern match"

git add src/cortex/atoms/list_recall.py tests/test_list_recall.py
git commit -m "feat(batch3a): Add list_recall handler with set-based grading"

git add src/cortex/atoms/ordered_list_recall.py tests/test_ordered_list_recall.py
git commit -m "feat(batch3a): Add ordered_list_recall handler with sequence grading"

git add src/cortex/atoms/__init__.py
git commit -m "feat(batch3a): Register 5 declarative memory handlers"

git push -u origin batch-3a-handlers-declarative
```

## Testing

```python
# Test cloze_dropdown
atom = ClozeDropdownAtom(
    cloze_text="The OSI model has {{c1::seven}} layers.",
    options=["five", "seven", "nine", "twelve"],
    correct_answer="seven"
)
result = handler.present(atom, console)
assert result.is_correct == True  # if selected index 2

# Test list_recall
atom = ListRecallAtom(
    prompt="Name all 7 OSI layers",
    correct=["Physical", "Data Link", "Network", "Transport", "Session", "Presentation", "Application"]
)
result = handler.present(atom, console)
# User enters: "Application, Physical, Network, Transport, Data Link, Session, Presentation"
assert result.partial_score == 1.0  # Order doesn't matter
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 3a] Declarative Memory Handlers (5 types)" \
  --body "Implement cloze_dropdown, short_answer_exact, short_answer_regex, list_recall, ordered_list_recall\n\n**Status:** ✅ Complete" \
  --label "batch-3a,atom-handlers,declarative-memory,enhancement"
```

## Success Metrics

- [ ] All 5 handlers implemented
- [ ] Unit tests pass (>80% coverage)
- [ ] Registered in handler registry
- [ ] Linked to skills (Batch 1)
- [ ] Rich UI rendering works

---

**Reference:** Plan lines 894-1079
**Status:** 🔴 Pending
