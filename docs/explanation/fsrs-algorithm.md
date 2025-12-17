# FSRS Algorithm

This document explains the Free Spaced Repetition Scheduler (FSRS) algorithm and how Cortex implements memory scheduling.

---

## Overview

FSRS is a modern spaced repetition algorithm that improves upon SM-2 (classic Anki). It provides:

- Better retention prediction
- Memory stability modeling
- Adaptive parameter optimization
- Forgetting curves based on Ebbinghaus's foundational research

---

## Theoretical Foundation

### The Forgetting Curve

Memory decay follows an approximately exponential function, as first documented by Hermann Ebbinghaus (1885) in his seminal work on memory. Ebbinghaus established that:

- Forgetting is rapid initially, then slows over time
- Retention can be modeled mathematically
- Repeated retrieval strengthens memory traces

Modern research has refined these findings. Cepeda et al. (2006) conducted a meta-analysis of 254 studies on the spacing effect, confirming that distributed practice produces superior long-term retention compared to massed practice.

### The Testing Effect

Roediger & Karpicke (2006) demonstrated that retrieval practice (testing) produces better long-term retention than re-reading, even when re-reading allows more study time. FSRS leverages this by scheduling retrieval attempts rather than passive review.

### Desirable Difficulties

Bjork (1994) introduced the concept of "desirable difficulties"---conditions that make learning more challenging but enhance long-term retention. These include:

- **Spacing**: Longer intervals between reviews (within limits)
- **Interleaving**: Mixing different topics during practice
- **Retrieval practice**: Testing rather than restudying

FSRS implements the spacing principle by scheduling reviews when retrievability drops to a target threshold.

---

## Core Concepts

### Memory Stability (S)

**Definition**: Days until retrievability drops to 90%.

| Stability | Interpretation |
|-----------|----------------|
| S = 1 day | Weak memory, review tomorrow |
| S = 30 days | Stable, can wait a month |
| S = 100+ days | Well-learned, mature |

Stability increases with successful recalls and decreases with lapses.

### Retrievability (R)

**Definition**: Probability of successful recall (0-1).

**Formula**:
```
R(t) = 0.9^(t/S)
```

Where:
- `t` = days since last review
- `S` = stability in days

| Retrievability | Interpretation |
|----------------|----------------|
| R = 0.90 | Optimal review time |
| R = 0.70 | Should review soon |
| R < 0.50 | Likely forgotten |

### Difficulty (D)

**Definition**: How hard the card is for this learner (0-1).

| Difficulty | Interpretation |
|------------|----------------|
| D = 0.0 | Very easy |
| D = 0.3 | Average |
| D = 0.7 | Challenging |
| D = 1.0 | Extremely difficult |

Higher difficulty means slower stability growth.

---

## Forgetting Curve

Memory decays exponentially over time, consistent with Ebbinghaus (1885):

```
Retrievability
    |
1.0 |*
    | *
0.9 |  *  <- Optimal review point
    |   *
0.8 |    *
    |     *
0.7 |      *
    |        *
0.6 |          *
    |            *
0.5 |              * <- 50% recall
    +---------------------------------> Days
    0    S/2     S      1.5S    2S
```

**Note**: The exact shape of the forgetting curve varies across individuals and material types. Research suggests the exponential model is a reasonable approximation for most contexts (Averell & Heathcote, 2011), though some studies indicate power-law decay may fit better in certain conditions.

---

## Scheduling After Review

When you review a card:

1. **Calculate retrievability** at time of review
2. **Update difficulty** based on rating
3. **Update stability** based on success/failure
4. **Schedule next review** when R will reach target

### Rating Effects

| Rating | Meaning | Stability | Difficulty |
|--------|---------|-----------|------------|
| Again (1) | Complete blank | Reset | Increase |
| Hard (2) | Recalled with effort | Small increase | Slight increase |
| Good (3) | Normal recall | Moderate increase | No change |
| Easy (4) | Effortless | Large increase | Decrease |

### Stability Update

```python
def update_stability(S_old, D, R, rating):
    if rating == 1:  # Forgot
        return max(1.0, S_old * 0.2 * (1 - D))

    growth_factor = {2: 1.2, 3: 2.5, 4: 3.5}[rating]
    difficulty_penalty = 1 - (D * 0.5)
    spacing_bonus = 1 + (1 - R) * 0.5  # Spacing effect

    return S_old * growth_factor * difficulty_penalty * spacing_bonus
```

The `spacing_bonus` implements the finding from Cepeda et al. (2006) that reviews at lower retrievability (but not too low) strengthen memory more effectively.

### Next Review Calculation

```python
def schedule_next_review(S, desired_retention=0.9):
    # Solve: 0.9^(t/S) = desired_retention
    import math
    days = S * math.log(desired_retention) / math.log(0.9)
    return max(1, round(days))
```

---

## Cortex Implementation

### Computing Stability from Anki

```python
def compute_stability(card_info):
    interval = card_info.get("interval", 0)
    ease = card_info.get("factor", 2500) / 1000.0
    reviews = card_info.get("reviews", 0)
    lapses = card_info.get("lapses", 0)

    if reviews == 0:
        return 0.0

    lapse_rate = lapses / reviews if reviews > 0 else 0
    return interval * ease * (1 - lapse_rate)
```

### Database Columns

| Column | Description |
|--------|-------------|
| `anki_stability` | FSRS stability (days) |
| `retrievability` | Current recall probability |
| `anki_ease_factor` | Ease from Anki (2.5 = 250%) |
| `anki_interval_days` | Current interval |
| `anki_lapses` | Times forgotten |
| `anki_review_count` | Total reviews |
| `anki_synced_at` | Last sync timestamp |

---

## Optimal Review Timing

### Target Retrievability

Default: 90% (configurable via `FSRS_DESIRED_RETENTION`)

| Target | Trade-off |
|--------|-----------|
| 95% | More reviews, higher retention |
| 90% | Default target |
| 85% | Fewer reviews, lower retention |

**Evidence Status**: The 90% retention target is a reasonable default widely used in spaced repetition systems, but it is not a uniquely optimal value derived from research. No study has established that 90% produces better outcomes than 85% or 92%. We chose 90% because it balances review burden against retention, aligns with FSRS conventions, and represents a conservative starting point. This is a design choice that can be adjusted based on individual goals and observed performance.

### Review Windows

| Status | Retrievability | Action |
|--------|----------------|--------|
| Early | R > 0.95 | Skip |
| Optimal | 0.85-0.95 | Ideal time |
| Due | 0.70-0.85 | Review today |
| Overdue | R < 0.70 | Urgent |

---

## Comparison with SM-2

| Aspect | SM-2 | FSRS |
|--------|------|------|
| Core metric | Interval | Stability |
| Forgetting model | Linear | Exponential |
| Parameters | Fixed | Adaptive |
| Difficulty | Ease factor only | Explicit |
| Spacing effect | Not modeled | Modeled |

### Why FSRS is Better

1. **More accurate**: Exponential forgetting aligns with Ebbinghaus (1885) and subsequent research
2. **Spacing effect**: Low-retrievability reviews strengthen memory more, consistent with Bjork (1994)
3. **Adaptive**: Parameters adjust to individual learner, addressing the individual variation documented by Kornell & Bjork (2008)
4. **Explicit forgetting**: Tracks actual recall probability

---

## Individual Variation

**Important caveat**: Optimal spaced repetition parameters vary substantially across individuals. Research indicates that:

- Memory decay rates differ between people (Averell & Heathcote, 2011)
- Optimal spacing intervals depend on individual learning pace
- The "ideal" retention target varies based on goals, available time, and material importance

Cortex allows parameter adjustment to accommodate individual differences. If default settings feel too aggressive or too lenient, consider adjusting `FSRS_DESIRED_RETENTION` based on your observed performance.

---

## Practical Implications

### For Learners

- Trust the algorithm's scheduling, but monitor your actual retention
- Rate honestly (don't always pick "Easy")
- Don't review too early (wastes time and reduces spacing benefit)
- Overdue cards are priorities
- **Individual calibration**: If you consistently forget cards rated "Good", consider increasing your retention target

### Interpreting Metrics

| Pattern | Meaning |
|---------|---------|
| High S, low R | Long since review, but memory strong |
| Low S, high R | Recently reviewed, memory still weak |
| High lapses, low ease | Struggling card, needs attention |

---

## Configuration

```bash
FSRS_DEFAULT_STABILITY=1.0      # Initial stability (days)
FSRS_DEFAULT_DIFFICULTY=0.3     # Initial difficulty (0-1)
FSRS_DESIRED_RETENTION=0.9      # Target retention rate (design choice)
```

---

## References

### Primary Research

- Ebbinghaus, H. (1885). *Memory: A contribution to experimental psychology*. (Original work establishing the forgetting curve)
- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about knowing* (pp. 185-205). MIT Press.
- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249-255.
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin, 132*(3), 354-380.
- Kornell, N., & Bjork, R. A. (2008). Learning concepts and categories: Is spacing the "enemy of induction"? *Psychological Science, 19*(6), 585-592.
- Averell, L., & Heathcote, A. (2011). The form of the forgetting curve and the fate of memories. *Journal of Mathematical Psychology, 55*(1), 25-35.

### Technical Resources

- [FSRS Algorithm Paper](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm)
- [Spaced Repetition Research Overview](https://www.gwern.net/Spaced-repetition)
- [SuperMemo: Effective Learning](https://supermemo.guru/wiki/Effective_learning)

---

## See Also

- [Adaptive Learning](adaptive-learning.md)
- [Configure Anki Sync](../how-to/configure-anki-sync.md)
- [Database Schema](../reference/database-schema.md)
