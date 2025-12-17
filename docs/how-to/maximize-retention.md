# How To: Maximize Retention

Use Cortex's learning features to support long-term retention through evidence-based practices.

---

## The Science Behind Cortex

Cortex implements learning principles with varying levels of empirical support:

### Well-Supported Practices (Cite with Confidence)

| Practice | Evidence | Citation |
|----------|----------|----------|
| Spaced repetition | Meta-analysis of 254 studies | Cepeda et al. (2006) |
| Retrieval practice | Testing beats re-reading for retention | Roediger & Karpicke (2006) |
| Interleaving | Mixing topics improves discrimination | Rohrer & Taylor (2007) |
| Desirable difficulties | Appropriate challenge enhances retention | Bjork (1994) |
| Prerequisites | Knowledge structure matters for learning | Various |

### Partially Supported (Note Limitations)

| Parameter | Evidence | Limitation |
|-----------|----------|------------|
| 90% retention target | Reasonable default | Not uniquely optimal; design choice |
| 85% accuracy zone | Wilson et al. (2019) | Limited to perceptual learning; generalizability unclear |
| 20-30 item sessions | Attention research | Optimal length varies by individual |

### Design Choices (No Direct Evidence)

These parameters are reasonable but not empirically validated:

- **Priority weights** (30/25/25/20): Balances urgency, importance, relevance, exploration
- **Mastery thresholds** (40/65/85): Creates intuitive progression
- **Passing scores** (70/80/85): Ordering makes sense; specific numbers arbitrary
- **Interleaving ratios** (30-50%): Research supports interleaving but not specific percentages

---

## Daily Study Routine

```bash
# 1. Get personalized suggestions
nls cortex suggest

# 2. Read suggested sections
nls cortex read 11 --section 11.2

# 3. Start optimized session
nls cortex optimize

# 4. Review progress
nls cortex stats
```

---

## Study Commands

### Standard vs Optimize Mode

| Command | Use When | Scheduling |
|---------|----------|------------|
| `nls cortex start` | Daily maintenance | Basic FSRS |
| `nls cortex optimize` | Focused study | Advanced FSRS + interleaving |
| `nls cortex start --mode war` | **EMERGENCY ONLY** | Aggressive cramming |

### Optimized Sessions

```bash
# Full optimization
nls cortex optimize

# Target specific modules
nls cortex optimize --modules 11,12,13

# Preview the plan
nls cortex optimize --plan
```

The `optimize` command applies:
- FSRS-4 algorithm for review scheduling
- Desirable difficulty calibration
- Smart interleaving (concept spacing)
- Struggle module prioritization

---

## Reading Before Testing

Research suggests that initial encoding through reading, followed by retrieval practice, can improve learning outcomes (Roediger & Karpicke, 2006).

### Read Specific Content

```bash
nls cortex read 11              # Module 11
nls cortex read 11 --section 11.2   # Specific section
nls cortex read 11 --toc        # Table of contents
nls cortex read 11 --search "subnet"  # Search
```

### Interactive Navigation

- **n** or **Enter**: Next section
- **p**: Previous section
- **t**: Table of contents
- **q**: Quit

### When to Re-Read

Re-read when `suggest` shows:
- "X lapses" - You've forgotten this content
- "Low stability" - Memory hasn't consolidated
- "Critical" priority - Struggle area with errors

---

## Hint System

Press `h` or `?` during questions for progressive hints:

| Type | Hint Behavior |
|------|---------------|
| MCQ | Eliminates wrong options |
| Numeric | Shows formulas |
| Parsons | Reveals step positions |
| Cloze | First letter, word length |

Using hints marks the response as "Hard" instead of "Good".

---

## Struggle Areas

### View Struggles

```bash
nls cortex struggle --show
```

### Set Struggle Modules

```bash
# Interactive
nls cortex struggle --interactive

# Specific modules
nls cortex struggle --modules 11,12,14
```

Struggle modules receive elevated priority in `optimize` sessions. We chose a 1.5x multiplier because it noticeably elevates struggling content without completely dominating sessions. This is a design choice that can be adjusted.

---

## Session Persistence

Sessions auto-save every 5 questions.

```bash
# Save: Press Ctrl+C during session
# Resume later:
nls cortex resume
```

Sessions expire after 24 hours.

---

## Cognitive Diagnosis

Cortex analyzes errors using the NCDE pipeline to generate probable diagnoses:

| Diagnosis | Meaning | Remedy |
|-----------|---------|--------|
| ENCODING GAP | Possibly never learned properly | Re-read source |
| PATTERN CONFUSION | May be confusing similar items | Discrimination training |
| INTEGRATION GAP | Possibly can't connect pieces | Step-by-step review |
| TOO FAST | May have answered impulsively | Slow down |
| RETRIEVAL LAPSE | Normal forgetting | Keep reviewing |
| COGNITIVE FATIGUE | Possible mental fatigue | Take a break |

**Note**: These diagnoses are probabilistic inferences. The actual cause of errors may differ.

---

## Optimal Study Patterns

### Recommended Schedule

| Time | Activity | Command |
|------|----------|---------|
| Morning | Optimized review | `nls cortex optimize` |
| Afternoon | Light reading | `nls cortex read` |
| Evening | Targeted review if needed | `nls cortex start --struggle-focus` |

**Individual variation**: Optimal study times depend on your chronotype and schedule. Research by Schmidt et al. (2007) indicates cognitive performance varies with time of day, but the direction of this effect differs between individuals. Experiment to find your best study windows.

### Session Length

- **Typical effective range**: 20-30 questions (~15-20 minutes)
- **Consider stopping at**: 50 questions or when accuracy drops
- **Take breaks**: Research suggests breaks improve sustained attention

**Evidence Status**: Attention research supports manageable session lengths, but optimal duration varies by individual and task. We chose 20-30 items because it represents approximately 15-20 minutes of focused work, a reasonable attention span for most learners. This is a design choice that can be adjusted based on your observed performance.

### Spaced Practice vs. Cramming

Research consistently shows distributed practice produces superior long-term retention compared to massed practice (Cepeda et al., 2006; Dunlosky et al., 2013):

- **Study daily** (even 10 questions helps)
- **Trust the scheduler** for review timing
- **Avoid cramming** except as last resort

---

## Critical Warning: War Mode and Cramming

> **WARNING: Massed practice (cramming) produces inferior long-term retention.**

### Research Evidence Against Cramming

- **Cepeda et al. (2006)**: Meta-analysis of 254 studies confirmed spacing effect superiority
- **Roediger & Karpicke (2006)**: Massed practice produced 35% worse retention after one week
- **Kornell (2009)**: Even when learners felt massed practice was more effective, spaced practice produced better outcomes
- **Schwabe & Wolf (2010)**: High stress during learning can impair memory consolidation

### War Mode Is an Emergency Fallback

War Mode (`nls cortex start --mode war`) exists only for:
- Exams within 24-48 hours where distributed practice is no longer possible
- Tactical review of specific weak areas identified through prior study
- Supplementing (not replacing) existing spaced practice

### War Mode Is NOT:
- A legitimate primary study strategy
- A way to "catch up" on weeks of missed study
- As effective as distributed practice for long-term retention
- A sustainable approach to learning

### If You're Tempted to Cram

Consider:
1. **Adjust expectations**: Cramming may help pass an immediate exam but knowledge will fade rapidly
2. **Prioritize ruthlessly**: Focus only on highest-yield material
3. **Sleep matters**: Sleep deprivation impairs both learning and recall (Walker, 2017)
4. **Plan better next time**: Use this experience to establish consistent daily practice

---

## Understanding FSRS Grades

| Grade | Meaning | Next Interval |
|-------|---------|---------------|
| Again (1) | Failed | Short (relearn) |
| Hard (2) | Struggled | Reduced growth |
| Good (3) | Normal | Standard growth |
| Easy (4) | Quick | Accelerated growth |

Grades are assigned automatically based on correctness, response time, and hint usage.

---

## Pre-Exam Strategy

### One Week Out

```bash
nls cortex optimize --modules 11,12,14 --limit 30
nls cortex suggest
```

At this point, you still have time for distributed practice. Use standard optimize mode.

### 2-3 Days Before

```bash
nls cortex optimize --struggle-focus --limit 40
```

Focus on identified weak areas through targeted spaced practice.

### Day Before

```bash
# Light review only - NOT intensive cramming
nls cortex start --limit 20
```

**Evidence-based recommendation**: Light review (not cramming) the day before an exam. Prioritize:
- Sleep (critical for memory consolidation)
- Confidence (reviewing strengths, not cramming weaknesses)
- Reducing stress (which impairs performance)

### Exam Day

Light review only (10-15 questions maximum). Focus on confidence, not cramming.

> Research suggests sleep-dependent memory consolidation occurs in the hours after learning (Walker, 2017). Intensive studying the night before may actually impair performance by reducing sleep.

---

## Metrics to Track

### Good Progress Indicators

- **Accuracy 75-85%**: Research suggests this range may be optimal for learning (Wilson et al., 2019, though generalizability is limited)
- **Avg stability > 7 days**: Memory consolidating
- **Lapses decreasing over time**: Encoding improving
- **Consistent daily practice**: Distributed practice outperforms massed practice (Cepeda et al., 2006)

### Warning Signs

- **Accuracy < 60%**: Material may be too difficult; consider re-reading first
- **Accuracy > 95%**: May indicate material is too easy; consider raising difficulty
- **High lapses on same cards**: Possible encoding issues
- **Fatigue warnings**: Take breaks
- **Skipping days**: Consistency typically matters more than session length

---

## Individual Differences

**Important**: Optimal learning parameters vary substantially across individuals.

### Factors Affecting Your Optimal Settings

- **Prior knowledge**: Experienced learners may benefit from longer spacing
- **Chronotype**: Morning vs. evening alertness affects optimal study times
- **Working memory capacity**: Affects optimal session length
- **Test anxiety**: May require adjusted success rate targets
- **Learning goals**: Exam preparation vs. long-term mastery differ

### Calibration Recommendations

1. **Monitor your actual retention**: If you consistently forget cards marked "Good", increase your retention target
2. **Track performance by time of day**: Identify your optimal study windows
3. **Adjust session length**: Stop before accuracy drops significantly
4. **Trust your metacognition**: If system recommendations feel wrong, experiment with alternatives

---

## References

### Primary Research

- Ebbinghaus, H. (1885). *Memory: A contribution to experimental psychology*.
- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about knowing* (pp. 185-205). MIT Press.
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin, 132*(3), 354-380.
- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249-255.
- Rohrer, D., & Taylor, K. (2007). The shuffling of mathematics problems improves learning. *Instructional Science, 35*(6), 481-498.
- Kornell, N. (2009). Optimising learning using flashcards: Spacing is more effective than cramming. *Applied Cognitive Psychology, 23*(9), 1297-1317.
- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). Improving students' learning with effective learning techniques. *Psychological Science in the Public Interest, 14*(1), 4-58.
- Schmidt, C., Collette, F., Cajochen, C., & Peigneux, P. (2007). A time to think: Circadian rhythms in human cognition. *Cognitive Neuropsychology, 24*(7), 755-789.
- Schwabe, L., & Wolf, O. T. (2010). Learning under stress impairs memory formation. *Neurobiology of Learning and Memory, 93*(2), 183-188.
- Walker, M. P. (2017). *Why we sleep: Unlocking the power of sleep and dreams*. Scribner.
- Wilson, R. C., Shenhav, A., Straccia, M., & Cohen, J. D. (2019). The eighty five percent rule for optimal learning. *Nature Communications, 10*(1), 4646.

---

## See Also

- [CLI Reference](../reference/cli-commands.md)
- [FSRS Algorithm](../explanation/fsrs-algorithm.md)
- [First Study Session Tutorial](../tutorials/first-study-session.md)
