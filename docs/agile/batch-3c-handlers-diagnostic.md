# Batch 3c: Metacognitive & Diagnostic Handlers

**Branch:** `batch-3c-handlers-diagnostic`
**Priority:** 🟡 HIGH | **Effort:** 2-3 days | **Status:** 🔴 Pending

## Atom Types (5)

1. **confidence_slider** - 0-100% confidence rating
2. **effort_rating** - How hard was this? (1-5 scale)
3. **categorization** - Drag items into categories
4. **script_concordance_test** - "If X, does diagnosis Y become more/less/unchanged useful?"
5. **key_feature_problem** - Select 3 most critical steps to take immediately

## Files to Create

- `src/cortex/atoms/confidence_slider.py` (~60 lines)
- `src/cortex/atoms/effort_rating.py` (~50 lines)
- `src/cortex/atoms/categorization.py` (~140 lines)
- `src/cortex/atoms/script_concordance_test.py` (~180 lines)
- `src/cortex/atoms/key_feature_problem.py` (~120 lines)

## Implementation Notes

**confidence_slider:** Pre/post answer metacognition
```python
# Capture BEFORE showing answer
pre_confidence = Prompt.ask("How confident are you? (0-100)")
# Then show answer and grade
# Capture calibration: |confidence - correctness|
```

**categorization:** Bucket sorting
```python
categories = {"Physical": [], "Data Link": [], "Network": []}
items = ["Ethernet", "IP", "Router", "Switch", "TCP"]
# User drags items into categories
# Grade: set match per category
```

**script_concordance_test:** Medical/diagnostic reasoning
```python
scenario = "Patient has fever + cough"
hypothesis = "Viral infection"
new_info = "White blood cell count elevated"

# Question: Does this make viral infection:
# A) More useful (+2, +1)
# B) Unchanged (0)
# C) Less useful (-1, -2)

# Grade: Expert panel consensus
```

## Commit Strategy

One commit per handler. Total 5 commits + registration.

---

**Status:** 🔴 Pending
