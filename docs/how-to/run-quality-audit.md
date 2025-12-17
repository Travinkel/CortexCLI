# How To: Run Quality Audit

Audit and improve learning atom quality using evidence-based criteria.

---

## Quick Quality Check

```bash
nls clean check --limit 100
```

Output:
```
Quality Check (100 atoms)
+-------+-------+------------+
| Grade | Count | Percentage |
+-------+-------+------------+
| A     | 45    | 45.0%      |
| B     | 30    | 30.0%      |
| C     | 15    | 15.0%      |
| D     | 7     | 7.0%       |
| F     | 3     | 3.0%       |
+-------+-------+------------+
```

---

## Quality Grades

### Grade A (Excellent) - Score >= 0.9

- Question: 8-15 words
- Answer: 1-5 words
- Single atomic concept

**Example**:
```
Q: What does TCP stand for?
A: Transmission Control Protocol
```

### Grade B (Good) - Score >= 0.75

- Question: 8-25 words
- Answer: 1-15 words
- Atomic or nearly atomic

### Grade C (Acceptable) - Score >= 0.6

- Minor issues present
- Consider editing for improvement

### Grade D (Needs Work) - Score >= 0.4

- Question too long/short
- Answer verbose (>25 words)
- May contain multiple concepts

**Action**: Flag for review and rewriting.

### Grade F (Unacceptable) - Score < 0.4

- Multiple questions in one card
- Missing content
- Non-atomic (needs splitting)

**Action**: Rewrite or split immediately.

---

## Run Full Quality Pipeline

### Dry Run

```bash
nls clean run --dry-run
```

### Apply Cleaning

```bash
nls clean run
```

Executes:
1. Atomicity validation
2. Prefix normalization
3. Duplicate detection
4. Quality scoring

### With AI Rewriting

```bash
nls clean run --rewrite
```

Targets Grade D/F atoms. Rewritten atoms enter the review queue.

---

## Find Problem Cards

### Verbose Cards

```sql
SELECT card_id, front, back, back_word_count
FROM clean_atoms
WHERE back_word_count > 15
ORDER BY back_word_count DESC
LIMIT 20;
```

### Non-Atomic Cards

```sql
SELECT card_id, front, atomicity_status
FROM clean_atoms
WHERE atomicity_status = 'needs_split'
ORDER BY created_at DESC;
```

### Low-Quality Cards

```sql
SELECT card_id, front, quality_score
FROM clean_atoms
WHERE quality_score < 0.6
ORDER BY quality_score ASC
LIMIT 50;
```

---

## Configure Thresholds

```bash
# Question length (words)
ATOMICITY_FRONT_MAX_WORDS=25

# Answer length
ATOMICITY_BACK_OPTIMAL_WORDS=5
ATOMICITY_BACK_WARNING_WORDS=15
ATOMICITY_BACK_MAX_CHARS=120

# Enforcement mode
ATOMICITY_MODE=relaxed    # or 'strict'
```

### Relaxed vs Strict

| Mode | Behavior |
|------|----------|
| `relaxed` | Warn about violations, allow sync |
| `strict` | Block atoms that violate thresholds |

---

## Evidence-Based Thresholds

### Question Length (8-25 words)

**Source**: Wozniak's 20 Rules of Formulating Knowledge

Questions >25 words are difficult to parse. Questions <8 words often lack context.

### Answer Length (1-15 words, optimal 5)

**Source**: SuperMemo retention research

Answers <=5 words show highest retention. Answers >15 words indicate non-atomic content.

### Character Limit (120 chars)

**Source**: Cognitive Load Theory

Working memory handles ~4 chunks. 120 characters is approximately one chunk.

---

## Duplicate Detection

### Exact Duplicates

```sql
SELECT front, COUNT(*) as count
FROM clean_atoms
GROUP BY front
HAVING COUNT(*) > 1
ORDER BY count DESC;
```

### Near-Duplicates

```bash
python scripts/find_duplicates.py --threshold 0.85
```

Configure threshold:
```bash
SEMANTIC_DUPLICATE_THRESHOLD=0.85
```

---

## Review Queue Workflow

### View Pending

```bash
curl http://localhost:8100/api/review?status=pending
```

### Approve

```bash
curl -X POST http://localhost:8100/api/review/{id}/approve \
  -H "Content-Type: application/json" \
  -d '{"notes": "LGTM"}'
```

### Reject

```bash
curl -X POST http://localhost:8100/api/review/{id}/reject \
  -H "Content-Type: application/json" \
  -d '{"reason": "Lost important context"}'
```

---

## Best Practices

1. **Start with relaxed mode** while building content
2. **Review D/F grades weekly**
3. **Trust the thresholds** - they are evidence-based
4. **Split non-atomic cards** - one concept per card
5. **Prefer shorter answers** - if you can say it in fewer words, do it

---

## See Also

- [Generate Learning Atoms](generate-atoms.md)
- [Configuration Reference](../reference/configuration.md)
- [Cognitive Diagnosis](../explanation/cognitive-diagnosis.md)
