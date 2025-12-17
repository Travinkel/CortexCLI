# Cognitive Diagnosis (NCDE)

This document explains the Neuro-Cognitive Diagnosis Engine, which identifies why learners make errors and provides targeted remediation.

---

## Overview

The NCDE pipeline analyzes response patterns to diagnose cognitive error types. Instead of just marking answers wrong, it identifies the underlying learning issue to provide targeted remediation.

**Note on Scientific Grounding**: While this system draws on cognitive psychology research, the specific diagnostic categories and thresholds are design choices informed by---but not directly validated against---empirical data. Individual learners may exhibit error patterns that do not fit neatly into these categories.

---

## Knowledge Taxonomy

Cortex classifies knowledge into four types based on the Revised Bloom's Taxonomy (Anderson & Krathwohl, 2001):

### Factual Knowledge

**Definition**: Discrete, isolated facts.

**Examples**: "OSI has 7 layers", "IPv4 addresses are 32 bits"

**Assessment**: Flashcards, true/false, fill-in-blank

**Error pattern**: Confusion between similar facts (in many cases)

### Conceptual Knowledge

**Definition**: Understanding relationships and principles.

**Examples**: Understanding how TCP ensures reliability

**Assessment**: Explanation questions, concept mapping, MCQ with reasoning

**Error pattern**: Can recall facts but typically cannot explain relationships

### Procedural Knowledge

**Definition**: How to perform tasks and processes.

**Examples**: Configuring a router interface, subnetting an IP address

**Assessment**: Parsons problems, step sequencing

**Error pattern**: Often knows what to do but not the correct order

### Metacognitive Knowledge

**Definition**: Awareness of one's own learning and thinking.

**Examples**: Knowing when to use VLSM vs. fixed subnetting

**Assessment**: Self-evaluation, confidence ratings

**Error pattern**: Overconfidence or underconfidence, as documented by Koriat (2012)

---

## Error Classifications

### Failure Modes

| Code | Name | Description | Remediation |
|------|------|-------------|-------------|
| FM1 | CONFUSIONS | Mixing similar terms/concepts | Discrimination training |
| FM2 | PROCESS | Multi-step procedure errors | Parsons problems |
| FM3 | CALCULATION | Numeric computation errors | Numeric drills |
| FM4 | APPLICATION | Cannot apply to scenarios | Scenario practice |
| FM5 | VOCABULARY | Terminology recall failure | Flashcards, cloze |
| FM6 | COMPARISON | Cannot distinguish related | Compare/contrast exercises |
| FM7 | TROUBLESHOOTING | Cannot diagnose from symptoms | Problem-solving practice |

**Note**: These failure mode categories are heuristic classifications. Actual errors often involve multiple overlapping causes, and individual learners may exhibit idiosyncratic error patterns.

### Cognitive Diagnoses

| Diagnosis | Meaning | Indicator | Remedy |
|-----------|---------|-----------|--------|
| ENCODING_GAP | Never learned properly | First-time failure | Re-read source material |
| PATTERN_CONFUSION | Confusing similar items | Choosing related wrong answer | Discrimination training |
| INTEGRATION_GAP | Cannot connect pieces | Failing multi-concept questions | Step-by-step review |
| TOO_FAST | Impulsive response | Very short response time | Slow down |
| RETRIEVAL_LAPSE | Normal forgetting | Long since review | Continue FSRS schedule |
| COGNITIVE_FATIGUE | Brain tired | Late session, accuracy dropping | Take a break |

---

## Diagnosis Algorithm

### Input Signals

| Signal | Source | Weight |
|--------|--------|--------|
| `is_correct` | Response | Primary |
| `response_time_ms` | Timer | 20% |
| `session_position` | Counter | 10% |
| `stability` | FSRS | 15% |
| `lapse_count` | History | 25% |
| `selected_distractor` | MCQ | 20% |
| `hint_used` | Session | 10% |

**Evidence Status**: We chose these signal weights (20/10/15/25/20/10) based on our judgment about diagnostic utility. This is a design choice that can be adjusted. No research specifies optimal weighting for cognitive error diagnosis.

### Classification Logic

```python
def diagnose(response: AtomResponse) -> Diagnosis:
    if response.is_correct:
        return None

    # Check for impulsivity
    expected_time = estimate_reading_time(response.card.front)
    if response.time_ms < expected_time * 0.5:
        return Diagnosis.TOO_FAST

    # Check for fatigue
    if response.session_position > 30:
        recent_accuracy = get_recent_accuracy(5)
        if recent_accuracy < 0.6:
            return Diagnosis.COGNITIVE_FATIGUE

    # Check for encoding gap
    if response.lapse_count == 0 and response.stability < 2.0:
        return Diagnosis.ENCODING_GAP

    # Check for pattern confusion (MCQ specific)
    if response.atom_type == 'mcq':
        distractor = response.selected_answer
        if is_semantically_related(distractor, response.card.correct_answer):
            return Diagnosis.PATTERN_CONFUSION

    # Check for integration gap
    if response.card.prerequisite_count > 2:
        prereq_mastery = get_prereq_mastery(response.card)
        if prereq_mastery < 0.65:
            return Diagnosis.INTEGRATION_GAP

    # Default: normal forgetting
    return Diagnosis.RETRIEVAL_LAPSE
```

---

## Response Time Analysis

### Expected Times

| Card Type | Minimum | Expected | Maximum |
|-----------|---------|----------|---------|
| Flashcard (short) | 2s | 5s | 30s |
| Flashcard (long) | 5s | 15s | 60s |
| MCQ (4 options) | 10s | 30s | 120s |
| Numeric | 15s | 45s | 180s |
| Parsons | 20s | 60s | 300s |

**Design Note**: We chose these time thresholds (2s minimum, 5s expected for short flashcards, etc.) based on estimated reading and processing times. These are approximations---individual reading speeds, familiarity with material, and cognitive processing rates vary substantially.

**Important**: Response time interpretation should account for individual differences:
- Fast readers may legitimately respond in less time
- Non-native language learners may need more time
- Complex technical content may require additional processing

### Time-Based Signals

| Condition | Interpretation |
|-----------|----------------|
| < 0.5x expected | Possibly impulsive (but may indicate high fluency) |
| 0.5-1.5x expected | Typical range |
| 1.5-3x expected | May indicate difficulty (or careful deliberation) |
| > 3x expected | Likely significant difficulty |

---

## Remediation Strategies

### For Retrieval Failure

Research on retrieval practice (Roediger & Karpicke, 2006) suggests:

1. **Increase review frequency** (reduce interval)
2. **Add retrieval cues** (context, mnemonics)
3. **Interleave practice** (mix with similar content)

### For Knowledge Gap

1. **Backtrack to prerequisites** (Force Z algorithm)
2. **Provide explicit instruction** (link to resources)
3. **Use simpler examples first**

### For Interference (Pattern Confusion)

Research on interference suggests (Rohrer & Taylor, 2007):

1. **Contrast training** (present confusables together)
2. **Highlight differences** (explicit discrimination)
3. **Space similar items** (avoid back-to-back presentation)

### For Application Failure

1. **Worked examples** (show step-by-step)
2. **Faded scaffolding** (gradually remove support)
3. **Practice variation** (different problem types)

---

## Confusable Detection

### Semantic Similarity

```python
def find_confusables(card, threshold=0.75):
    card_embedding = get_embedding(card.front + " " + card.back)
    similar_cards = []
    for other_card in all_cards:
        similarity = cosine_similarity(card_embedding, get_embedding(other_card))
        if similarity > threshold:
            similar_cards.append((other_card, similarity))
    return sorted(similar_cards, key=lambda x: -x[1])
```

### Error Co-occurrence

Cards where learners frequently make errors on both:

```sql
SELECT c1.card_id as card_a, c2.card_id as card_b,
       COUNT(*) as error_co_occurrences
FROM quiz_responses r1
JOIN quiz_responses r2 ON r1.session_id = r2.session_id
WHERE r1.is_correct = false AND r2.is_correct = false
GROUP BY c1.card_id, c2.card_id
HAVING COUNT(*) > 3;
```

---

## Session Feedback

### During Session

After each wrong answer:
```
Incorrect. The answer is: TCP

[NCDE] Diagnosis: PATTERN_CONFUSION
       You may be confusing TCP with UDP.
       Suggestion: Focus on distinguishing reliable vs unreliable transport.
```

**Note**: Diagnoses are probabilistic inferences, not definitive assessments. The actual cause of an error may differ from the diagnosed category.

### End of Session

```
Session Analysis
================

Cognitive Patterns (probable):
  - ENCODING_GAP: 3 cards (Module 11)
  - PATTERN_CONFUSION: 2 cards (OSI layers)

Recommendations:
  1. Re-read Module 11 Section 11.3 before next session
  2. Practice OSI layer discrimination exercises
```

---

## Passing Thresholds by Knowledge Type

| Knowledge Type | Passing Threshold | Rationale |
|----------------|-------------------|-----------|
| Factual | 70% | Basic recall |
| Conceptual | 80% | Understanding required |
| Procedural | 85% | Must execute correctly |
| Metacognitive | 75% | Self-awareness |

**Evidence Status**: We chose these thresholds (70/80/85/75) because the ordering makes intuitive sense---procedural knowledge requires higher precision than factual recall. However, the specific numbers are design choices, not empirically derived. No research establishes that 80% is the correct threshold for conceptual knowledge versus 78% or 82%. These can be adjusted based on domain requirements and observed outcomes.

---

## Metacognition and Confidence

Koriat (2012) documented common patterns of miscalibration between confidence and accuracy:

- **Overconfidence**: Believing you know material you will forget
- **Underconfidence**: Doubting knowledge you have actually mastered
- **Illusion of knowing**: Feeling of familiarity mistaken for understanding

Cortex attempts to detect these patterns, but accurate metacognitive diagnosis typically requires:
- Multiple data points over time
- Explicit confidence ratings before answers
- Comparison of predicted vs. actual performance

---

## Individual Differences

**Important caveat**: Cognitive diagnosis accuracy varies across individuals due to:

- **Reading speed variation**: Affects interpretation of response time signals
- **Test anxiety**: May produce patterns resembling other error types
- **Prior domain knowledge**: Affects baseline expectations
- **Cultural and linguistic background**: Affects interpretation of semantic similarity

The NCDE provides probabilistic diagnoses that should be interpreted as hypotheses, not definitive assessments. If diagnosed patterns do not match your experience, trust your own metacognitive awareness.

---

## Configuration

```bash
# Response time thresholds (design choices, may need calibration)
NCDE_MIN_RESPONSE_TIME_MS=2000
NCDE_EXPECTED_WPM_READING=200

# Fatigue detection
NCDE_FATIGUE_THRESHOLD_POSITION=30
NCDE_FATIGUE_ACCURACY_TRIGGER=0.6

# Knowledge type thresholds (design choices)
KNOWLEDGE_FACTUAL_PASSING=0.70
KNOWLEDGE_CONCEPTUAL_PASSING=0.80
KNOWLEDGE_PROCEDURAL_PASSING=0.85
KNOWLEDGE_METACOGNITIVE_PASSING=0.75

# Confusable detection
SEMANTIC_DUPLICATE_THRESHOLD=0.85
```

---

## References

### Primary Research

- Anderson, L. W., & Krathwohl, D. R. (Eds.). (2001). *A taxonomy for learning, teaching, and assessing: A revision of Bloom's taxonomy of educational objectives*. Longman.
- Koriat, A. (2012). The self-consistency model of subjective confidence. *Psychological Review, 119*(1), 80-113.
- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249-255.
- Rohrer, D., & Taylor, K. (2007). The shuffling of mathematics problems improves learning. *Instructional Science, 35*(6), 481-498.
- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students' learning with effective learning techniques. *Psychological Science in the Public Interest, 14*(1), 4-58.
- Wilson, R. C., Shenhav, A., Straccia, M., & Cohen, J. D. (2019). The eighty five percent rule for optimal learning. *Nature Communications, 10*(1), 4646.

---

## NCDE Pipeline Integration

### Struggle Weight Updates

The NCDE pipeline now integrates with the Dynamic Struggle Tracking system (Migration 020). After each diagnosis, the system updates struggle weights:

```python
# src/adaptive/ncde_pipeline.py
diagnosis, strategy = pipeline.process(raw_event, context)

# Prepare and execute struggle update
update_data = prepare_struggle_update(
    diagnosis=diagnosis,
    module_number=module,
    section_id=section,
    is_correct=raw_event.is_correct,
    atom_id=raw_event.atom_id,
    session_id=context.session_id,
)
await update_struggle_weight_async(db_session, update_data)
```

### StruggleUpdateData

Data structure for passing diagnosis results to the database:

| Field | Type | Description |
|-------|------|-------------|
| `module_number` | int | CCNA module (1-17) |
| `section_id` | str or None | Section ID or None for module-level |
| `failure_mode` | str | Detected failure mode name |
| `accuracy` | float | 0.0 for incorrect, 1.0 for correct |
| `atom_id` | str or None | UUID of atom being studied |
| `session_id` | str or None | UUID of current study session |

### Failure Mode to Database Mapping

| NCDE FailMode | Database Value | Weight Multiplier |
|---------------|----------------|-------------------|
| `ENCODING_ERROR` | `encoding` | 0.25 |
| `INTEGRATION_ERROR` | `integration` | 0.20 |
| `RETRIEVAL_ERROR` | `retrieval` | 0.15 |
| `DISCRIMINATION_ERROR` | `discrimination` | 0.15 |
| `EXECUTIVE_ERROR` | `executive` | 0.05 |
| `FATIGUE_ERROR` | `fatigue` | 0.02 |

### Pipeline Hooks

The NCDE pipeline supports extensibility via hooks:

```python
pipeline = NCDEPipeline()

# Add pre-diagnosis hook (e.g., for logging)
pipeline.add_pre_diagnosis_hook(lambda raw, telemetry, ctx: log_telemetry(raw))

# Add post-diagnosis hook (e.g., for struggle updates)
pipeline.add_post_diagnosis_hook(lambda diagnosis, ctx: update_struggles(diagnosis))
```

---

## See Also

- [Adaptive Learning](adaptive-learning.md)
- [Session Remediation](session-remediation.md) - Hints, retry logic, and Anki suggestions
- [FSRS Algorithm](fsrs-algorithm.md)
- [Maximize Retention](../how-to/maximize-retention.md)
- [Struggle-Aware System](struggle-aware-system.md) - Dynamic struggle tracking integration
