# Use the Learning Signals Dashboard

View transfer testing results, memorization suspects, and note effectiveness metrics through the CORTEX CLI signals dashboard.

---

## Prerequisites

- CORTEX CLI installed and configured
- PostgreSQL database with migration 019 applied
- Some study session data (accuracy metrics)

---

## Access the Dashboard

### Via Interactive Hub

```bash
nls cortex start
```

1. Select option **8** from the main menu: "Learning signals dashboard"
2. The dashboard renders immediately with current data

### Interpreting the Dashboard

The signals dashboard displays four sections:

---

## Section 1: Transfer Testing

Shows per-section accuracy broken down by question format.

```
Section         T/F     MCQ   Parsons  Transfer
11.2            85%     72%     45%      67%
14.3            90%     65%     40%      65%
```

**Columns**:
- **Section**: CCNA section identifier
- **T/F**: True/False accuracy (recognition-based)
- **MCQ**: Multiple choice accuracy (conceptual)
- **Parsons**: Parsons problem accuracy (procedural)
- **Transfer**: Overall transfer score (consistency across formats)

**What to look for**:
- Large gaps between T/F and Parsons indicate surface-level memorization
- Consistent scores across formats indicate genuine understanding
- Transfer score below 50% warrants deeper practice

---

## Section 2: Memorization Suspects

Lists atoms flagged as memorization suspects.

```
[!] 11.3.2        T/F: 90% vs Procedural: 45% (gap: +45%)
```

**Detection criteria**: An atom is flagged when True/False accuracy exceeds procedural (Parsons/numeric) accuracy by 35% or more.

**Interpretation**: High recognition accuracy with low procedural accuracy suggests the learner can recognize correct answers but cannot apply the knowledge.

**Remediation**:
- Practice Parsons problems for the flagged sections
- Use the note generation feature to review underlying concepts
- Focus on "why" and "how" rather than "what"

---

## Section 3: Note Effectiveness

Shows pre/post error rate improvements for study notes.

```
[+] IPv4 Subnetting Basics    +18% improvement (3 reads)
[-] OSI Layer Functions       -5% change (1 read)
```

**Metrics**:
- **Improvement**: Pre-error-rate minus post-error-rate (positive = improvement)
- **Reads**: Number of times the note was read

**What to look for**:
- Notes with positive improvement are working
- Notes with negative change may need regeneration
- Notes with low read counts need more data

---

## Section 4: Recommended Actions

Prioritized actions based on signal analysis.

```
[!!!] M11: Deep practice needed - Recognition without understanding
[!! ] M14: Vary question types - Low transfer score
[!  ] M08: Focus session - Struggle weight: 0.8
```

**Priority levels**:
- `[!!!]` High: Immediate attention required
- `[!! ]` Medium: Address in next study session
- `[!  ]` Low: Monitor and address when convenient

---

## Taking Action on Signals

### For Memorization Suspects

1. Navigate to the struggle map (option 3)
2. Generate study notes for affected modules (sub-option 1)
3. Start a manual session targeting Parsons problems:
   ```bash
   nls cortex manual --sections 11.3 --types parsons
   ```

### For Low Transfer Scores

1. Review the relevant section content:
   ```bash
   nls cortex read 11 --section 11.3
   ```
2. Generate elaborative notes:
   ```bash
   # Use the study notes browser (option 7)
   # Select "Generate notes for weak sections"
   ```
3. Practice with varied question types

### For Ineffective Notes

1. Check note quality in the notes browser (option 7)
2. Rate notes to provide feedback
3. Regenerate notes with different note types:
   - Use **contrastive** for discrimination errors
   - Use **procedural** for integration errors
   - Use **elaborative** for encoding errors

---

## Database Requirements

The signals dashboard requires migration 019 (`019_transfer_testing.sql`) which adds:

| Column | Purpose |
|--------|---------|
| `format_seen` | Tracks which question formats have been presented |
| `accuracy_by_type` | Per-format accuracy statistics |
| `transfer_score` | Consistency score across formats |
| `memorization_suspect` | Boolean flag for memorization detection |

Run pending migrations:
```bash
nls db migrate
```

---

## Troubleshooting

### "Transfer view not available"

Migration 019 has not been applied. Run:
```bash
nls db migrate
```

### "No transfer data yet"

Complete more study sessions with varied question types. The system needs:
- At least 3 responses per recognition type (T/F, MCQ)
- At least 2 responses per procedural type (Parsons, numeric)

### Dashboard shows no recommendations

This indicates:
- No memorization suspects detected
- No low transfer scores
- No configured struggle weights

Continue studying normally; signals will populate as data accumulates.

---

## See Also

- [Transfer Testing Explanation](../explanation/transfer-testing.md)
- [Configure Question Type Quotas](configure-type-quotas.md)
- [Database Schema Reference](../reference/database-schema.md)
- [Use Study Notes](use-study-notes.md)
