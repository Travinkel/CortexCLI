# Transfer Testing for Memorization Detection

Transfer testing distinguishes genuine understanding from surface-level memorization by measuring performance consistency across different question formats.

---

## The Problem: Illusion of Learning

Learners often perform well on recognition-based questions (True/False, MCQ) while failing procedural questions (Parsons, numeric) on the same content. This pattern indicates:

- **Recognition memory**: Ability to identify correct information when presented
- **Recall/application failure**: Inability to produce or apply that information independently

High recognition accuracy with low procedural accuracy creates an "illusion of learning" where learners believe they understand material they can only recognize.

---

## How Transfer Testing Works

### Data Collection

The system tracks accuracy by question format for each atom:

```json
{
  "true_false": {"correct": 8, "total": 10},
  "mcq": {"correct": 6, "total": 9},
  "parsons": {"correct": 2, "total": 5}
}
```

### Transfer Score Calculation

Transfer score measures consistency across recognition and procedural formats:

1. **Recognition accuracy**: Average of T/F and MCQ accuracy
2. **Procedural accuracy**: Average of Parsons, numeric, and sequence accuracy
3. **Transfer score**: Average of recognition and procedural accuracy

High transfer score (near 1.0) indicates consistent performance across formats, suggesting genuine understanding.

### Memorization Detection

An atom is flagged as a "memorization suspect" when:

```
Recognition accuracy - Procedural accuracy >= 0.35 (35%)
```

This threshold was chosen based on the observation that:
- Small gaps (< 20%) are normal variance
- Medium gaps (20-35%) warrant monitoring
- Large gaps (>= 35%) indicate systematic memorization without understanding

---

## Question Type Classification

### Recognition Types (Test Memory)

| Type | Cognitive Demand | Description |
|------|------------------|-------------|
| **True/False** | Low | Binary recognition; can be guessed |
| **MCQ** | Medium | Recognition from options; distractor analysis |

Recognition questions test whether the learner can identify correct information when presented with choices.

### Procedural Types (Test Understanding)

| Type | Cognitive Demand | Description |
|------|------------------|-------------|
| **Parsons** | High | Sequence ordering; requires integration |
| **Numeric** | High | Calculation; requires procedural knowledge |
| **Matching** | Medium | Association; requires discrimination |

Procedural questions require the learner to produce, construct, or apply knowledge without being given the answer.

---

## Implementation Details

### Database Schema

Migration 019 adds the following columns to `learning_atoms`:

```sql
-- Track which formats have been seen
format_seen JSONB DEFAULT '{}'

-- Queue for next transfer test
transfer_queue TEXT[]

-- Per-format accuracy tracking
accuracy_by_type JSONB DEFAULT '{}'

-- Computed transfer consistency score
transfer_score FLOAT DEFAULT NULL

-- Memorization flag
memorization_suspect BOOLEAN DEFAULT FALSE
```

### Update Logic

After each study interaction, the system:

1. Updates `accuracy_by_type` with the new result
2. Calculates `transfer_score` if sufficient data exists (3+ recognition, 2+ procedural)
3. Sets `memorization_suspect = TRUE` if gap >= 35%
4. Queues procedural follow-up tests for recognition successes

```python
# Example: User answers T/F correctly
if is_correct and atom_type in recognition_types:
    # Queue a procedural test for next session
    target_type = "parsons" if atom_type == "true_false" else "numeric"
    transfer_queue.append(f"{atom_id}:{target_type}")
```

### Transfer Queue Processing

During session setup, the system:

1. Checks `transfer_queue` for pending transfer tests
2. Prioritizes queued atoms in the session
3. Presents the atom in the queued format
4. Clears the queue entry after presentation

---

## Pedagogical Foundation

### Desirable Difficulties (Bjork, 1994)

Transfer testing implements "desirable difficulties" by:

- Varying practice conditions (format switching)
- Requiring retrieval in different contexts
- Exposing gaps that recognition alone misses

### Transfer-Appropriate Processing (Morris et al., 1977)

Learning is most effective when practice matches the target application:

- Procedural questions prepare learners for real-world application
- Recognition questions may not transfer to hands-on tasks
- Mixing formats ensures broader skill development

### Production Effect (MacLeod et al., 2010)

Producing information (Parsons, typing answers) creates stronger memory traces than recognizing information (T/F, MCQ selection).

---

## Using Transfer Data

### For Learners

The signals dashboard reveals:

1. **Which topics are memorized but not understood**
   - Focus procedural practice on these areas
   - Review conceptual explanations before drilling

2. **Which topics show genuine mastery**
   - Transfer score > 0.7 indicates solid understanding
   - Safe to reduce practice frequency

3. **Which topics need varied practice**
   - Low transfer score suggests format-specific learning
   - Deliberately practice multiple formats

### For Study Sessions

The adaptive session algorithm uses transfer data to:

- Prioritize memorization suspects for procedural practice
- Balance question types via quotas (35% MCQ, 25% T/F, 25% Parsons, 15% Matching)
- Queue follow-up tests after recognition successes

---

## Limitations and Considerations

### Data Requirements

Transfer testing requires sufficient data:
- Minimum 3 responses per recognition type
- Minimum 2 responses per procedural type
- Without this data, `transfer_score` remains NULL

### Content Availability

Not all atoms have all question types available. The system:
- Only calculates transfer for atoms with multiple formats
- Skips transfer queue entries when target format unavailable
- Reports "No transfer data" when insufficient coverage exists

### Individual Differences

Some learners may have legitimate reasons for format-specific performance:
- Test anxiety affecting procedural performance
- Reading speed affecting timed recognition questions
- Prior experience with specific formats

Interpret memorization flags as signals for investigation, not definitive diagnoses.

---

## Configuration

Transfer testing is enabled by default. No configuration required.

Detection threshold (35% gap) is hardcoded based on learning science research. To adjust, modify `_update_transfer_testing()` in `src/study/study_service.py`.

---

## See Also

- [Use the Learning Signals Dashboard](../how-to/use-signals-dashboard.md)
- [Configure Question Type Quotas](../how-to/configure-type-quotas.md)
- [Database Schema Reference](../reference/database-schema.md)
- [Cognitive Diagnosis (NCDE)](cognitive-diagnosis.md)

---

## References

- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), Metacognition: Knowing about knowing (pp. 185-205).
- Morris, C. D., Bransford, J. D., & Franks, J. J. (1977). Levels of processing versus transfer appropriate processing. Journal of Verbal Learning and Verbal Behavior, 16(5), 519-533.
- MacLeod, C. M., Gopie, N., Hourihan, K. L., Neary, K. R., & Ozubko, J. D. (2010). The production effect: Delineation of a phenomenon. Journal of Experimental Psychology: Learning, Memory, and Cognition, 36(3), 671-685.
