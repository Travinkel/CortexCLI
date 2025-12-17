# How-To: Use Study Notes

This guide explains how to use the Remediation Learning Loop feature, including the "I Don't Know" option, study notes, and quality tracking.

---

## Overview

The Remediation Learning Loop helps you learn unfamiliar material before drilling with flashcards. Instead of guessing randomly, you can honestly indicate when you do not know an answer, triggering targeted study notes.

**Key components**:
- "I Don't Know" input during study sessions
- Pre-session note check
- Micro-notes triggered by consecutive errors
- Post-session remediation with LLM-generated notes
- Hub menu for browsing and rating notes

---

## Using "I Don't Know" During Sessions

When you encounter unfamiliar content, type one of these inputs instead of guessing:

| Input | Effect |
|-------|--------|
| `?` | Triggers "I don't know" |
| `l` | Triggers "I don't know" |
| `learn` | Triggers "I don't know" |
| `idk` | Triggers "I don't know" |
| `dk` | Triggers "I don't know" |

### What Happens

1. The correct answer is revealed immediately with an explanation
2. The atom's `dont_know_count` is incremented in the database
3. The section is flagged for potential note generation
4. No penalty beyond tracking (not counted as "incorrect" for FSRS)

### Example

```
[Card 5/20] Module 11: IPv4 Addressing

What is the network address for 192.168.1.100/26?

Your answer: ?

Good honesty! Here is the answer to learn:
  192.168.1.64

[Explanation: /26 = 64 addresses per subnet. 100/64 = 1.56, floor = 1. Network = 64*1 = 64]
```

**Rationale**: Guessing creates false signal in the spaced repetition system. Honest "I don't know" responses allow the system to route you to foundational material.

---

## Pre-Session Note Check

Before starting a study session, Cortex checks for unread remediation notes related to your queued atoms.

### Trigger Conditions

- At least one queued atom has a `ccna_section_id`
- An unread, qualified note exists for that section

### User Flow

```
UNREAD STUDY NOTES

You have 2 unread notes for sections in today's queue:

  [1] 11.2 - Understanding Subnetting
  [2] 14.1 - Transport Layer Protocols

Would you like to read them before practicing? [y/N]:
```

### Navigation

| Key | Action |
|-----|--------|
| `Enter` | Next note |
| `q` | Skip remaining notes |
| `1-5` | Rate the note |

---

## Micro-Notes During Session

When you make 2 or more consecutive errors on atoms from the same section, Cortex displays a quick review.

### Trigger Conditions

- 2+ consecutive incorrect answers on the same `ccna_section_id`
- Note not already shown for this section in current session

### Display

```
--- QUICK REVIEW ---
Multiple errors on section 11.2

Think of subnetting like dividing a pizza:
- /24 = 1 pizza (256 slices)
- /25 = half pizza (128 slices)
- /26 = quarter pizza (64 slices)

The network address is always the first slice of your portion.

[Press Enter to continue...]
```

### Behavior

- Shows existing note content if available
- Falls back to generic section tips if no note exists
- Only triggers once per section per session (prevents spam)

---

## Post-Session Remediation

After completing a session, if you struggled with specific sections, Cortex offers remediation options.

### Menu Options

```
REMEDIATION OPTIONS

You struggled with 3 section(s). What would you like to do?

  [1] Generate study notes for struggled topics
  [2] Generate additional practice questions
  [3] Full Anki sync (push atoms + pull stats)
  [4] View Anki filtered deck query
  [s] Skip remediation

Your choice:
```

### Option 1: Generate Study Notes

Generates LLM-powered notes for sections where you had multiple errors:

```
Generating notes for weak sections...

Section 11.2 - Understanding Subnetting
  Error rate: 60% (3/5 wrong)
  Generating comprehensive note...
  Done!

Section 14.1 - Transport Layer
  Error rate: 40% (2/5 wrong)
  Generating standard note...
  Done!

Notes saved to outputs/notes/
```

**Note depth scales with error rate**:

| Error Rate | Depth | Content |
|------------|-------|---------|
| < 25% | Brief | Core concept only |
| 25-50% | Standard | Core + memory anchors |
| >= 50% | Comprehensive | Full deep-dive with examples |

### Option 4: Anki Filtered Deck Query

Provides a query for creating a filtered deck in Anki:

```
ANKI FILTERED DECK QUERY

deck:CCNA::ITN::* (tag:section:11.2 OR tag:section:14.1) -is:suspended

Instructions:
1. Open Anki
2. Tools -> Create Filtered Deck
3. Paste the query above
4. Study the filtered deck
```

---

## Browsing Study Notes (Hub Menu)

Access the study notes browser from the Cortex hub menu.

### Access

```bash
nls cortex start  # Then press 'h' for hub
```

Or navigate to hub and select option 7:

```
CORTEX HUB

  [1] Start adaptive session
  [2] Start war mode session
  [3] View progress
  [4] Import/refresh struggles from YAML
  [5] Configure modules
  [6] Resume previous session
  [7] Browse study notes
  [q] Quit

>_ SELECT ACTION: 7
```

### Notes Browser Sub-Menu

```
STUDY NOTES

Available notes: 12
Sections needing notes: 5

  [1] - View all notes
  [2] - View unread notes
  [3] - Generate notes for weak sections
  [b] - Back to hub
```

### Viewing Notes

Select a note number to read it:

```
+------------------------------------------+
|  Understanding Subnetting                |
|  Section 11.2                            |
+------------------------------------------+
|                                          |
|  ## Mental Model                         |
|                                          |
|  Think of subnetting like apartment      |
|  buildings. The network address is the   |
|  building address, and host addresses    |
|  are apartment numbers within.           |
|                                          |
|  ## Key Concepts                         |
|  ...                                     |
|                                          |
+------------------------------------------+

Rate this note (1-5) or Enter to skip:
Rating: 4

Rating saved!
```

### Rating Notes

After reading a note, rate its helpfulness:

| Rating | Meaning |
|--------|---------|
| 1 | Not helpful |
| 2 | Slightly helpful |
| 3 | Neutral |
| 4 | Helpful |
| 5 | Very helpful |

Ratings contribute to the note quality score and determine whether notes remain "qualified" for display.

---

## Quality Tracking

Cortex automatically tracks note effectiveness.

### Metrics Tracked

| Metric | Description |
|--------|-------------|
| `read_count` | Times the note has been read |
| `user_rating` | Average rating (1-5) |
| `pre_error_rate` | Section error rate before first read |
| `post_error_rate` | Section error rate after reading |
| `effectiveness` | Computed as `pre_error_rate - post_error_rate` |
| `qualified` | Boolean indicating if note meets quality threshold |

### Quality Score Calculation

```
Base score: 50

+ Rating contribution: (rating - 3) * 10
  - Rating 5: +20
  - Rating 4: +10
  - Rating 3: 0
  - Rating 2: -10
  - Rating 1: -20

+ Improvement contribution:
  - > 10% improvement: +20
  - > 0% improvement: +10
  - < -10% improvement: -20

Qualified if score >= 40
```

### Viewing Quality Report

Use the API or direct database query:

```sql
SELECT section_id, title, read_count, user_rating,
       pre_error_rate, post_error_rate, effectiveness, qualified
FROM remediation_notes
WHERE read_count > 0
ORDER BY qualified DESC, effectiveness DESC;
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | - | Required for LLM note generation |
| `STUDY_NOTES_OUTPUT_DIR` | `outputs/notes` | Directory for saved notes |

### Note Generation Model

The system uses `gemini-1.5-flash` by default for fast, cost-effective generation. To change:

```python
from src.learning.note_generator import NoteGenerator

generator = NoteGenerator(model_name="gemini-1.5-pro")
```

---

## Troubleshooting

### Notes Not Generating

**Symptoms**: "LLM not configured" error

**Solution**: Set the `GOOGLE_API_KEY` environment variable:

```bash
export GOOGLE_API_KEY=your-api-key
```

### Section Not Found

**Symptoms**: "Section X.Y not found in module N" error

**Solution**: Ensure source materials exist in `docs/source-materials/CCNA/`

### Notes Not Appearing

**Symptoms**: Notes exist but do not display

**Check**:
1. Note `qualified = TRUE`
2. Note `is_stale = FALSE`
3. Note `expires_at > NOW()`

---

## See Also

- [Session Remediation](../explanation/session-remediation.md) - Full remediation system documentation
- [First Study Session](../tutorials/first-study-session.md) - Getting started with study sessions
- [Database Schema](../reference/database-schema.md) - `remediation_notes` table reference
