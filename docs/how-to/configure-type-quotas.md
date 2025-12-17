# Configure Question Type Quotas

Balance question types in adaptive study sessions to ensure cognitive diversity and prevent over-representation of any single format.

---

## Overview

CORTEX uses question type quotas to ensure each study session includes a balanced mix of question formats. This prevents:

- Over-reliance on easy recognition questions (T/F)
- Insufficient procedural practice (Parsons)
- Cognitive monotony from repeated question types

---

## Default Quotas

The default configuration in `src/adaptive/models.py`:

```python
TYPE_QUOTAS: dict[str, float] = {
    "mcq": 0.35,           # 35% conceptual thinking
    "true_false": 0.25,    # 25% factual recall
    "parsons": 0.25,       # 25% procedural (Cisco commands)
    "matching": 0.15,      # 15% discrimination
}
```

### Quota Rationale

| Type | Quota | Cognitive Purpose |
|------|-------|-------------------|
| MCQ | 35% | Conceptual reasoning, distractor analysis |
| True/False | 25% | Quick factual verification |
| Parsons | 25% | Procedural sequencing, command syntax |
| Matching | 15% | Discrimination between similar concepts |

---

## Minimum Guarantees

To prevent sessions with missing question types, the system enforces minimums:

```python
TYPE_MINIMUM: dict[str, int] = {
    "mcq": 2,
    "true_false": 2,
    "parsons": 2,
    "matching": 1,
}
```

A session always includes at least 2 MCQ, 2 T/F, 2 Parsons, and 1 Matching question (if available in the content pool).

---

## How Quotas Are Applied

### Session Setup

1. System retrieves candidate atoms from database
2. Groups atoms by type
3. Calculates target count per type: `target = session_limit * quota`
4. Selects up to target for each type
5. Fills shortfall from remaining atoms (preferring MCQ)

### Example Calculation

For a 20-question session:
- MCQ target: `20 * 0.35 = 7`
- T/F target: `20 * 0.25 = 5`
- Parsons target: `20 * 0.25 = 5`
- Matching target: `20 * 0.15 = 3`

If only 2 Parsons questions available, the shortfall (3) is filled from other types.

---

## Modifying Quotas

### Option 1: Edit Source Code

Modify `src/adaptive/models.py`:

```python
# Increase procedural focus for hands-on practice
TYPE_QUOTAS: dict[str, float] = {
    "mcq": 0.25,
    "true_false": 0.15,
    "parsons": 0.45,       # Increased from 25%
    "matching": 0.15,
}
```

Ensure quotas sum to 1.0.

### Option 2: Environment Variables (Future)

Environment-based configuration is planned but not yet implemented. Track progress in the project roadmap.

---

## Interleaving

After quota-based selection, atoms are interleaved by type to prevent consecutive same-type questions:

```python
# Type presentation order
type_order = ["mcq", "matching", "true_false", "parsons"]

# Round-robin interleaving
# Session: MCQ, Matching, T/F, Parsons, MCQ, Matching, T/F, Parsons, ...
```

This ensures cognitive variety throughout the session rather than clustering by type.

---

## Verifying Quota Distribution

After a session, check the distribution in logs:

```
INFO: Type-balanced session: {'mcq': 7, 'true_false': 5, 'parsons': 5, 'matching': 3}
```

Or query the database for historical distribution:

```sql
SELECT
    atom_type,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as pct
FROM atom_responses
WHERE responded_at > NOW() - INTERVAL '7 days'
GROUP BY atom_type
ORDER BY count DESC;
```

---

## Special Cases

### War Mode

War mode prioritizes high-cognitive-load types:
1. Numeric (highest priority)
2. Parsons
3. MCQ
4. True/False

Quotas are not applied; selection is based on weakness indicators.

### Manual Mode

Manual mode (`nls cortex manual --sections X --types Y`) bypasses quotas entirely. Specify types explicitly:

```bash
# Only Parsons questions
nls cortex manual --sections 11.3 --types parsons

# MCQ and Matching only
nls cortex manual --sections 14.2,14.3 --types mcq,matching
```

---

## Troubleshooting

### "Not enough Parsons questions"

Content pool lacks sufficient Parsons problems. Generate more:

```bash
nls generate atoms --module 11 --type parsons
```

Or reduce Parsons quota temporarily.

### Session feels unbalanced

Check available content per type:

```sql
SELECT atom_type, COUNT(*)
FROM learning_atoms
WHERE ccna_section_id IS NOT NULL
GROUP BY atom_type;
```

If certain types are underrepresented, quotas cannot be fully satisfied.

### Want more challenging sessions

Increase Parsons and reduce T/F:

```python
TYPE_QUOTAS = {
    "mcq": 0.30,
    "true_false": 0.15,    # Reduced
    "parsons": 0.40,       # Increased
    "matching": 0.15,
}
```

---

## See Also

- [Transfer Testing Explanation](../explanation/transfer-testing.md)
- [Use the Learning Signals Dashboard](use-signals-dashboard.md)
- [Adaptive Learning](../explanation/adaptive-learning.md)
- [Database Schema Reference](../reference/database-schema.md)
