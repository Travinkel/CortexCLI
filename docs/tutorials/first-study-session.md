# Tutorial: Your First Study Session

This tutorial walks you through running your first adaptive study session with the Cortex CLI.

**Time required**: 10 minutes

**Prerequisites**:
- Completed the [Getting Started](getting-started.md) tutorial
- At least 10 learning atoms in your database

---

## Step 1: Check Your Study Queue

```bash
nls cortex today
```

Output:
```
CCNA Study Session - December 9, 2025
=====================================

Today's Overview:
  Due cards: 45
  New cards: 12
  Review cards: 33

Module Progress:
  M01 Networking Today.......... 85% mastery
  M02 Basic Switch Config....... 72% mastery
  M03 Protocols and Models...... 65% mastery
```

---

## Step 2: Start a Study Session

```bash
nls cortex start
```

You enter the interactive study interface:
```
=== CORTEX STUDY SESSION ===
Mode: Adaptive | Target: 20 cards | Streak: 0

[Card 1/20] Module 3: Protocols and Models

What protocol provides reliable, connection-oriented data delivery?

Press [Space] to reveal answer...
```

---

## Step 3: Review a Flashcard

1. **Think** about the answer before revealing
2. Press **Space** to show the answer
3. **Rate** your recall quality

After pressing Space:
```
Answer: TCP (Transmission Control Protocol)

Rate your recall:
  [1] Forgot - Complete blank
  [2] Hard   - Significant effort to recall
  [3] Good   - Correct with some effort
  [4] Easy   - Instant recall

Your rating (1-4):
```

---

## Step 4: Understand the Rating Scale

| Rating | Meaning | Effect on Schedule |
|--------|---------|-------------------|
| **1 - Forgot** | Complete blank | Card repeats soon |
| **2 - Hard** | Recalled with difficulty | Interval decreases |
| **3 - Good** | Recalled correctly | Interval maintained |
| **4 - Easy** | Instant recall | Interval increased |

Rate honestly. Rating "Easy" when you struggled causes forgetting later.

---

## Step 5: Answer Multiple Choice Questions

```
[Card 5/20] Module 5: Number Systems

Which layer of the OSI model handles logical addressing?

  A) Physical Layer
  B) Data Link Layer
  C) Network Layer
  D) Transport Layer

Your answer (A/B/C/D): C

Correct! The Network Layer (Layer 3) handles IP addressing and routing.
```

---

## Step 6: Track Your Progress

The header updates with progress:
```
=== CORTEX STUDY SESSION ===
Mode: Adaptive | Progress: 5/20 | Streak: 4 | Accuracy: 80%
```

---

## Step 7: Complete the Session

```
=== SESSION COMPLETE ===

Session Summary
  Duration: 12 minutes
  Cards reviewed: 20
  Accuracy: 85%
  Longest streak: 8

Performance by Module:
  M03 Protocols and Models... 90% (9/10 correct)
  M05 Number Systems........ 80% (4/5 correct)

Recommendations:
  Focus on: Number Systems (80% - needs reinforcement)
  Strong in: Protocols and Models (90%)

[Press Enter to exit or 'c' to continue studying]
```

---

## Step 8: Try Different Study Modes

### War Mode (Intensive)

For cramming or catching up:
```bash
nls cortex start --mode war
```

Features:
- Focuses on struggling cards
- Shorter intervals between repetitions
- No "Easy" ratings

### Module Focus

Study a specific module:
```bash
nls cortex start --module 3
```

### Custom Session Length

```bash
nls cortex start --limit 50
```

### Optimized Session

Use FSRS-4 with smart interleaving:
```bash
nls cortex optimize
```

---

## Step 9: View Statistics

```bash
nls cortex stats
```

Output:
```
CCNA Learning Statistics

Overall Progress
  Total atoms: 4,924
  Mastered: 1,245 (25.3%)
  Learning: 2,890 (58.7%)
  New: 789 (16.0%)

Review Metrics
  Average ease: 2.45
  Average interval: 12.3 days
  Retention rate: 89%
```

---

## Step 10: View Your Learning Path

```bash
nls cortex path
```

Output:
```
CCNA ITN Learning Path

[=====>....] M01 Networking Today (85%)
[====>....] M02 Basic Switch Config (72%)
[===>....] M03 Protocols and Models (65%)
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Reveal answer |
| `1-4` | Rate recall |
| `A-D` | Answer MCQ |
| `?` / `idk` | "I don't know" (honest learning path) |
| `q` | Quit session |
| `p` | Pause timer |
| `h` | Show hint |
| `s` | Skip card |

---

## Step 11: Use "I Don't Know" for Unfamiliar Content

When you encounter content you have not learned yet, do not guess randomly. Type `?` or `idk`:

```
[Card 8/20] Module 11: IPv4 Addressing

What is the network address for 192.168.1.100/26?

Your answer: ?

Good honesty! Here is the answer to learn:
  192.168.1.64

[Explanation: /26 = 64 addresses per subnet. 100/64 = 1.56, floor = 1. Network = 64*1 = 64]
```

**Why this matters**:
- Guessing creates false signal in the spaced repetition algorithm
- Honest "I don't know" tracks the atom for targeted remediation
- The system can route you to study notes before drilling

---

## Error Handling and Retry

When you answer incorrectly, Cortex provides scaffolded support:

### First Wrong Answer

You receive a contextual hint and can retry immediately:

```
Incorrect. Here's a hint:

  Watch out for absolute words like 'always' or 'never'.

Try again...
```

### Second Wrong Answer

The correct answer is displayed and the question is tracked for Anki review:

```
INCORRECT

Correct answer:
  TCP (Transmission Control Protocol)

[Explanation: TCP provides reliable, connection-oriented delivery]
```

### Session End Suggestions

If you struggled with specific sections, Cortex generates an Anki filtered deck query:

```
ANKI STUDY SUGGESTION

You struggled with 2 section(s). Use this filtered deck query:

deck:CCNA::ITN::* (tag:section:3.2 OR tag:section:5.1) -is:suspended

[Instructions: Anki -> Tools -> Create Filtered Deck -> paste query]
```

### Remediation Menu

After the session summary, if you struggled with any sections, you see the remediation menu:

```
REMEDIATION OPTIONS

  [1] Generate study notes for struggled topics
  [2] Generate additional practice questions
  [3] Full Anki sync (push atoms + pull stats)
  [s] Skip remediation
```

**Option 1: Study Notes** generates personalized notes based on your error rate:
- Low error rate (< 25%): Brief notes with core concepts
- Medium error rate (25-50%): Standard notes with memory anchors
- High error rate (>= 50%): Comprehensive deep-dive

Notes display in terminal and save to `outputs/notes/` for later review.

**Option 3: Anki Sync** performs full bidirectional sync so you can continue studying on mobile.

See [Session Remediation](../explanation/session-remediation.md) for details on how hints are generated.

---

## Summary

You learned to:
- Start an adaptive study session
- Answer flashcards and MCQs
- Use the recall rating system
- Use "I don't know" for unfamiliar content
- Benefit from hints and retry opportunities on errors
- Use Anki filtered deck suggestions for targeted review
- Generate personalized study notes for struggled topics
- Use the post-session remediation menu
- Explore different study modes
- View statistics and learning path

---

## Next Steps

- [Use Study Notes](../how-to/use-study-notes.md) - Browse and generate remediation notes
- [Configure Anki Sync](../how-to/configure-anki-sync.md) - Study on mobile
- [Maximize Retention](../how-to/maximize-retention.md) - Evidence-based study strategies

---

## Tips for Effective Study

1. **Study daily**: Consistency beats intensity
2. **Rate honestly**: Accurate ratings improve scheduling
3. **Keep sessions short**: 15-20 minutes is optimal
4. **Trust the algorithm**: Let Cortex decide what to show you
