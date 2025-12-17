# Adaptive Learning Engine

This document explains how Cortex selects cards and adapts to learner performance.

---

## Overview

The adaptive learning engine combines multiple signals to optimize learning efficiency:

1. **Spaced Repetition**: Review at intervals based on forgetting curve research (Ebbinghaus, 1885; Cepeda et al., 2006)
2. **Prerequisite Ordering**: Foundation before advanced, aligned with knowledge structure research
3. **Difficulty Adaptation**: Adjust based on struggles, implementing desirable difficulties (Bjork, 1994)
4. **Z-Score Prioritization**: Balance multiple factors using a weighted formula

---

## Theoretical Foundation

### Evidence-Based Practices

This engine implements learning strategies rated as highly effective by Dunlosky et al. (2013) in their comprehensive review of learning techniques:

- **Distributed practice** (high utility): Spreading study over time
- **Practice testing** (high utility): Retrieval practice for retention
- **Interleaved practice** (moderate utility): Mixing related topics

### Design Philosophy

Cortex translates learning science principles into practical algorithms. However, the specific parameter values (weights, thresholds, formulas) represent our design choices---informed by research but not directly derived from it.

---

## Card Selection Algorithm

### Step 1: Filter Candidates

```sql
SELECT * FROM clean_atoms
WHERE
    is_atomic = true
    AND needs_review = false
    AND quality_score >= 0.75
    AND (anki_due_date <= CURRENT_DATE OR anki_due_date IS NULL)
```

### Step 2: Compute Priority Score

```
Priority = w_decay * D(t) + w_centrality * C(a) + w_project * P(a) + w_novelty * N(a)
```

Where:
- `D(t)` = Time decay signal (overdue cards score higher)
- `C(a)` = Graph centrality (connected concepts score higher)
- `P(a)` = Project relevance (current focus areas)
- `N(a)` = Novelty (unseen cards)

### Step 3: Apply Prerequisite Constraints

```python
def can_present(card, learner_state):
    for prereq in card.prerequisites:
        if learner_state.get_mastery(prereq.concept_id) < prereq.threshold:
            return False
    return True
```

### Step 4: Rank and Select

Sort by priority score, filter by prerequisites, select top N.

---

## Z-Score System

Cortex 2.0 provides sophisticated card prioritization using a weighted multi-signal approach.

### Components

| Signal | Weight | Description |
|--------|--------|-------------|
| Decay D(t) | 30% | Time since last review |
| Centrality C(a) | 25% | Importance in knowledge graph |
| Project P(a) | 25% | Relevance to current goals |
| Novelty N(a) | 20% | Preference for unseen content |

**Evidence Status**: We chose these weights (30/25/25/20) because they balance urgency (decay), importance (centrality), relevance (project), and exploration (novelty). This is a design choice that can be adjusted. No research specifies optimal weighting for multi-signal card prioritization.

### Decay Function

```python
def compute_decay(days_since_review):
    half_life = 7  # configurable
    return 0.5 ** (days_since_review / half_life)
```

### Centrality Score

Computed from the knowledge graph:
- PageRank of concept node
- Number of prerequisite relationships
- Frequency of cross-references

### Project Relevance

Based on current learning goals:
- Active project keywords
- Module associations
- Explicit priority flags

### Novelty Score

- New cards start with high novelty
- Decreases after first review
- Prevents system from only showing reviews

---

## Prerequisite System

Cortex enforces knowledge prerequisites for proper sequencing.

### Prerequisite Types

| Type | Threshold | Description |
|------|-----------|-------------|
| Foundation | 40% mastery | Basic exposure required |
| Integration | 65% mastery | Solid understanding needed |
| Mastery | 85% mastery | Expert-level required |

**Evidence Status**: Research supports prerequisite sequencing (knowledge structure matters for learning), but the specific thresholds (40/65/85) are design choices. We chose these values because they create an intuitive progression from basic familiarity to deep understanding. The specific numbers are not empirically derived and can be adjusted based on domain and learner needs.

### Gating Modes

**Soft Gating** (default):
- Prerequisites recommended
- Learner can override
- Warning shown when bypassing

**Hard Gating**:
- Prerequisites required
- Card hidden until met
- No bypass option

### Force Z Algorithm

When a learner encounters a card they cannot answer:

1. Identify failed card's prerequisites
2. Check which are below threshold
3. **Backtrack**: Add prerequisite cards to session
4. Maximum depth: 5 levels

```python
def force_z_backtrack(failed_card, learner_state, depth=0):
    if depth > 5:
        return []

    gaps = []
    for prereq in failed_card.prerequisites:
        mastery = learner_state.get_mastery(prereq.concept_id)
        if mastery < prereq.threshold:
            gaps.append(prereq)
            prereq_card = get_card_for_concept(prereq.concept_id)
            if prereq_card:
                gaps.extend(force_z_backtrack(prereq_card, learner_state, depth + 1))
    return gaps
```

---

## Study Modes

### Standard Mode

Balanced selection across due cards:
- Mix of new and review
- Respects prerequisites
- Targets 85-90% correct rate

**Evidence Status**: Wilson et al. (2019) found approximately 85% accuracy may be optimal for learning, but this study focused on perceptual learning tasks. Generalizability to declarative knowledge (facts, concepts) is uncertain. Our 85-90% target represents a reasonable interpretation of desirable difficulties (Bjork, 1994), but the specific range is a design choice that can be adjusted.

### War Mode (Emergency Cramming)

> **WARNING: War Mode produces inferior long-term retention.**
>
> Massed practice (cramming) is well-documented to produce worse long-term retention than distributed practice (Cepeda et al., 2006). War Mode exists as an emergency fallback for imminent deadlines, not as a legitimate study strategy.
>
> **Limitations of cramming:**
> - Roediger & Karpicke (2006) showed massed practice produced 35% worse retention after one week
> - High-stress cramming can impair memory consolidation (Schwabe & Wolf, 2010)
> - Information learned through cramming is typically forgotten rapidly

**Use War Mode only when:**
- Exam is within 24-48 hours
- You have already completed distributed practice
- You need tactical review of specific weak areas

**Never use War Mode as:**
- Your primary study strategy
- A substitute for regular spaced practice
- A way to "catch up" on weeks of missed study

```python
def war_mode_selection(candidates):
    return sorted(candidates, key=lambda c: (
        -c.lapse_count,
        c.ease_factor,
        c.retrievability
    ))
```

War Mode characteristics:
- Focus on struggling cards
- Shorter intervals
- Higher card count
- No "Easy" rating

### Module Focus

Study a specific module:
- Filter cards by module_id
- Maintain prerequisite ordering
- Show completion percentage

---

## Difficulty Adaptation

### Ease Factor Adjustment

| Rating | Effect on Ease |
|--------|----------------|
| 1 (Forgot) | -0.20 |
| 2 (Hard) | -0.15 |
| 3 (Good) | No change |
| 4 (Easy) | +0.15 |

Minimum ease: 1.30 (prevents "ease hell")

### Struggling Card Detection

Cards are flagged as struggling when:
- Lapse count >= 3
- Ease factor < 2.0
- Retrievability < 0.5

**Note**: These thresholds are design choices. Individual learners may benefit from different values---some may need more aggressive intervention earlier, while others may naturally have higher variability.

Struggling cards receive:
- More frequent reviews
- Simplified variations (if available)
- Diagnostic feedback

---

## Session Flow

### Before Session

1. Query due cards
2. Compute Z-Scores
3. Apply prerequisite filtering
4. Build initial queue

### During Session

1. Present top-ranked card
2. User reveals answer
3. User rates recall (1-4)
4. Update scheduling parameters
5. Log response
6. Re-rank queue (if adaptive)
7. Check completion

### After Session

1. Commit updates to database
2. Sync to Anki (if configured)
3. Display summary
4. Log session metrics

---

## Mastery Calculation

Cortex uses two mastery calculation approaches depending on context.

### Concept-Level Mastery

Formula: `combined_mastery = (review_mastery x 0.625) + (quiz_mastery x 0.375)`

| Component | Weight | Source |
|-----------|--------|--------|
| Review mastery | 62.5% | FSRS retrievability from Anki reviews |
| Quiz mastery | 37.5% | Best score from last 3 quiz attempts |

This weighting is aligned with the right-learning project research, emphasizing spaced repetition (review) while incorporating active recall through quizzes.

**Review Mastery Calculation**:
```
review_mastery = weighted_avg(retrievability)
retrievability = e^(-days_since_review / stability)
weight = min(review_count, 20)
```

**Quiz Mastery Calculation**:
- Uses best score from last 3 attempts
- Combines results from `atom_responses` (in-app quizzes) and `session_atom_responses` (adaptive sessions)

### Section-Level Mastery (CCNA)

For CCNA section mastery (`ccna_section_mastery` table), a simpler proxy is used:

```sql
mastery_score = AVG(LEAST(anki_stability / 30.0, 1.0))
```

This uses Anki stability divided by 30 days, capped at 1.0. A stability of 30+ days indicates strong long-term retention.

**Important**: The `mastery_score` column uses a 0.0-1.0 range, not 0-100. A value of 0.675 represents 67.5% mastery.

---

## Analytics

### Per-Session Metrics

- Cards reviewed
- Accuracy percentage
- Average response time
- Streak (consecutive correct)

### Long-Term Metrics

- Retention rate
- Learning velocity (new cards/day)
- Struggling concept identification
- Module completion percentage

### Recommendations

Based on performance:
- "Focus on Module 5 (72% accuracy, below target)"
- "Strong in TCP/IP concepts (94%)"
- "Consider reviewing OSI Model prerequisites"

---

## Individual Differences

**Important**: Optimal learning parameters vary substantially across individuals. Research indicates:

- **Chronotype effects**: Some learners perform better at different times of day (Schmidt et al., 2007)
- **Working memory capacity**: Affects optimal session length and complexity
- **Prior knowledge**: Experienced learners may benefit from longer spacing intervals
- **Learning goals**: Exam preparation vs. long-term mastery require different approaches

Consider adjusting:
- Session length based on when you notice fatigue
- Review times based on your personal alertness patterns
- Thresholds based on your observed retention rates

---

## Configuration

```bash
# Z-Score weights (design choices, not empirically derived)
ZSCORE_WEIGHT_DECAY=0.30
ZSCORE_WEIGHT_CENTRALITY=0.25
ZSCORE_WEIGHT_PROJECT=0.25
ZSCORE_WEIGHT_NOVELTY=0.20

# Thresholds (may need personal calibration)
ZSCORE_ACTIVATION_THRESHOLD=0.5
ZSCORE_DECAY_HALFLIFE_DAYS=7

# Force Z
FORCE_Z_MASTERY_THRESHOLD=0.65
FORCE_Z_MAX_DEPTH=5

# Prerequisites (design choices)
PREREQUISITE_FOUNDATION_THRESHOLD=0.40
PREREQUISITE_INTEGRATION_THRESHOLD=0.65
PREREQUISITE_MASTERY_THRESHOLD=0.85
```

---

## References

### Primary Research

- Ebbinghaus, H. (1885). *Memory: A contribution to experimental psychology*.
- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about knowing* (pp. 185-205). MIT Press.
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin, 132*(3), 354-380.
- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249-255.
- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students' learning with effective learning techniques. *Psychological Science in the Public Interest, 14*(1), 4-58.
- Schmidt, C., Collette, F., Cajochen, C., & Peigneux, P. (2007). A time to think: Circadian rhythms in human cognition. *Cognitive Neuropsychology, 24*(7), 755-789.
- Schwabe, L., & Wolf, O. T. (2010). Learning under stress impairs memory formation. *Neurobiology of Learning and Memory, 93*(2), 183-188.
- Wilson, R. C., Shenhav, A., Straccia, M., & Cohen, J. D. (2019). The eighty five percent rule for optimal learning. *Nature Communications, 10*(1), 4646.

---

## What's Actually Evidence-Based?

This section provides an honest assessment of the evidence supporting each component of the adaptive learning engine.

### Well-Supported by Research

These practices have strong empirical support from multiple studies:

| Practice | Evidence | Key Citation |
|----------|----------|--------------|
| Spaced repetition | Meta-analysis of 254 studies confirms distributed practice superiority | Cepeda et al. (2006) |
| Testing/retrieval practice | Testing produces better retention than re-reading | Roediger & Karpicke (2006) |
| Interleaving | Mixing related topics improves discrimination and transfer | Rohrer & Taylor (2007) |
| Desirable difficulties | Conditions that challenge learners enhance long-term retention | Bjork (1994) |
| Prerequisites matter | Knowledge structure research supports sequenced instruction | Various |

These principles form the foundation of Cortex and can be cited with confidence.

### Partially Supported (Note Limitations)

These parameters have some research support but with important caveats:

| Parameter | Evidence | Limitation |
|-----------|----------|------------|
| 90% retention target | Reasonable default used by FSRS | Not uniquely optimal; no research establishes 90% beats 85% or 92% |
| 85% accuracy zone | Wilson et al. (2019) found ~85% accuracy optimal for learning | Study was on perceptual learning; generalizability to declarative knowledge unclear |
| 20-30 item sessions | Attention research supports manageable session lengths | Optimal length varies by individual and task type |

When citing these, acknowledge the limitations.

### Design Choices (No Direct Evidence)

These parameters are informed by reasoning but not empirically validated:

| Parameter | Our Choice | Rationale |
|-----------|------------|-----------|
| Priority weights (30/25/25/20) | Decay 30%, Centrality 25%, Project 25%, Novelty 20% | Balances urgency, importance, relevance, and exploration. Reasonable but arbitrary. |
| Mastery calculation weights | 62.5% review, 37.5% quiz | Aligned with right-learning project research. See [Mastery Calculation](#mastery-calculation). |
| Mastery thresholds (40/65/85) | Foundation, Integration, Mastery | Creates intuitive progression. Specific values arbitrary. |
| Passing scores (70/80/85) | Factual 70%, Conceptual 80%, Procedural 85% | Ordering makes sense (procedures need precision), but specific numbers arbitrary. |
| Interleaving ratios (30-50%) | Percentage of items from different topics | Research supports interleaving but does not specify optimal ratios. |

When documenting these, state: "We chose X because [reasoning]. This is a design choice that can be adjusted."

### Implications for Users

1. **Trust the principles**: Spaced repetition, testing, and interleaving work.
2. **Experiment with parameters**: Specific numbers may need calibration for your context.
3. **Monitor outcomes**: If retention is poor or review burden too high, adjust thresholds.
4. **Report what works**: User feedback helps us refine design choices over time.

---

## See Also

- [FSRS Algorithm](fsrs-algorithm.md)
- [Cognitive Diagnosis](cognitive-diagnosis.md)
- [Struggle-Aware System](struggle-aware-system.md) - Dynamic struggle tracking
- [Architecture Overview](architecture.md)
