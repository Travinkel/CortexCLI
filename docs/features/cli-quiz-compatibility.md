# CLI Quiz Compatibility Matrix

**Version**: 1.0
**Last Updated**: December 3, 2025

---

## Overview

This document defines which learning atom types can be used in command-line interface (CLI) quizzes versus those requiring graphical user interface (UI) implementation.

---

## Compatibility Matrix

| Atom Type | CLI Compatible | UI Required | Implementation Complexity |
|-----------|---------------|-------------|---------------------------|
| MCQ | Yes | Optional | Low |
| TRUE_FALSE | Yes | Optional | Low |
| MATCHING | Yes | Optional | Medium |
| CLOZE | Partial | Recommended | Medium |
| PARSONS | No | Required | High |
| CODE_TRACING | Partial | Recommended | High |
| DRAG_DROP | No | Required | High |

---

## CLI-Compatible Types

### Multiple Choice Questions (MCQ)

**CLI Implementation**:
```
Question: Which layer of the OSI model handles logical addressing?

A) Physical Layer
B) Data Link Layer
C) Network Layer
D) Transport Layer

Your answer (A/B/C/D): C

Correct! The Network Layer (Layer 3) handles IP addressing and routing.
```

**Required Fields**:
- `front`: Question text
- `options`: List of 4 choices
- `correct_index`: Index of correct answer (0-3)
- `explanation`: Feedback text

**CLI Features**:
- Single keystroke input (A/B/C/D)
- Immediate feedback
- Optional hint system
- Score tracking

### True/False Questions

**CLI Implementation**:
```
Statement: TCP provides connectionless data delivery.

True (T) or False (F): F

Correct! TCP is connection-oriented. UDP is connectionless.
```

**Required Fields**:
- `front`: Statement to evaluate
- `back`: "True" or "False"
- `explanation`: Clarification

**CLI Features**:
- Binary input (T/F or Y/N)
- Confidence rating option
- Streak tracking

### Matching Questions

**CLI Implementation**:
```
Match each protocol to its port number:

Protocols:          Ports:
1. HTTP             A. 21
2. HTTPS            B. 22
3. FTP              C. 80
4. SSH              D. 443

Enter matches (e.g., 1C 2D 3A 4B): 1C 2D 3A 4B

Correct! All matches are correct.
  HTTP = 80
  HTTPS = 443
  FTP = 21
  SSH = 22
```

**Required Fields**:
- `front`: Instruction text
- `pairs`: Array of {left, right} objects
- Distractor options (optional)

**CLI Features**:
- Space-separated pair input
- Partial credit scoring
- Randomized presentation order

---

## Partially CLI-Compatible Types

### Cloze Deletion

**CLI Implementation** (Type-the-answer mode):
```
Complete the statement:

The OSI model has _____ layers, while TCP/IP has _____ layers.

Answer 1: 7
Answer 2: 4

Correct! OSI has 7 layers, TCP/IP has 4 layers.
```

**Limitations**:
- Requires exact text matching
- Typo handling needed (fuzzy matching)
- Multiple blanks increase complexity

**Recommended Alternative**:
- Convert to MCQ for CLI
- Use full cloze in Anki (native support)

### Code Tracing

**CLI Implementation** (Output prediction):
```
What is the output of this code?

  x = 5
  y = x + 3
  x = y * 2
  print(x, y)

Your answer: 16 8

Correct! After execution: x=16, y=8
```

**Limitations**:
- Works for simple output prediction
- Full trace tables require structured input
- Complex programs need step-by-step UI

---

## UI-Required Types

### Parsons Problems

**Why UI Required**:
- Drag-and-drop line reordering
- Visual feedback for indentation
- 2D arrangement (horizontal + vertical)

**Current Status**: Deferred to frontend phase

**Data Structure Ready**:
```json
{
    "atom_type": "PARSONS",
    "front": "Arrange the lines to configure a router interface:",
    "lines": [
        "Router(config)# interface GigabitEthernet0/0",
        "Router(config-if)# ip address 192.168.1.1 255.255.255.0",
        "Router(config-if)# no shutdown",
        "Router(config-if)# exit"
    ],
    "correct_order": [0, 1, 2, 3],
    "distractors": [
        "Router(config-if)# shutdown",
        "Router# show ip interface brief"
    ]
}
```

**Workaround for CLI** (Not recommended):
- Present as ordering question with line numbers
- Lose visual indentation feedback
- Reduced pedagogical value

### Drag-and-Drop Categorization

**Why UI Required**:
- Spatial arrangement
- Visual grouping feedback
- Multi-category sorting

**Example**: Sort these into OSI layers
- Cannot effectively represent in text-only CLI

---

## Quiz Session Flow (CLI)

### Standard Quiz Mode

```
=== CCNA Module 3 Quiz ===
Question 1/10 | Score: 0/0

Which protocol operates at the Transport layer?
A) IP
B) TCP
C) Ethernet
D) HTTP

> B

Correct! (+1 point)
TCP operates at Layer 4 (Transport) providing reliable delivery.

[Press Enter to continue]
```

### Adaptive Mode

```
=== Adaptive Quiz: Networking Fundamentals ===
Difficulty: Medium | Streak: 3

Based on your previous answers, here's your next question:

What is the default subnet mask for a Class C address?
A) 255.0.0.0
B) 255.255.0.0
C) 255.255.255.0
D) 255.255.255.255

> C

Correct! Streak: 4 | Difficulty increasing...
```

### Review Mode

```
=== Review Session ===
Cards due today: 15 | Overdue: 3

[Card 1/18]
Front: What command enters global configuration mode on a Cisco device?

[Press Space to reveal answer]

Back: configure terminal (or conf t)

Rate your recall:
1 = Forgot  2 = Hard  3 = Good  4 = Easy

> 3

Next card...
```

---

## CLI Quiz Engine Requirements

### Core Features

| Feature | Priority | Status |
|---------|----------|--------|
| MCQ presentation | P0 | Planned |
| True/False presentation | P0 | Planned |
| Matching presentation | P1 | Planned |
| Score tracking | P0 | Planned |
| Session persistence | P1 | Planned |
| Spaced repetition scheduling | P2 | Future |

### Input Handling

| Input Type | Validation | Error Handling |
|------------|------------|----------------|
| Single letter (A-D) | Case-insensitive | Prompt retry |
| True/False (T/F) | Accept T/F, True/False, Y/N | Prompt retry |
| Matching pairs | Parse "1A 2B" format | Partial credit |
| Free text | Fuzzy matching (Levenshtein) | Accept near-matches |

### Output Formatting

- ANSI colors for feedback (green=correct, red=incorrect)
- Clear screen between questions (optional)
- Progress bar for session
- Summary statistics at end

---

## Database Queries for CLI Quiz

### Get Quiz-Compatible Atoms

```sql
SELECT *
FROM clean_atoms
WHERE atom_type IN ('MCQ', 'TRUE_FALSE', 'MATCHING')
  AND is_atomic = true
  AND needs_review = false
  AND quality_score >= 0.75
ORDER BY RANDOM()
LIMIT 10;
```

### Get Atoms by Module

```sql
SELECT ca.*
FROM clean_atoms ca
JOIN clean_modules cm ON ca.module_id = cm.id
WHERE cm.name LIKE '%Module 3%'
  AND ca.atom_type IN ('MCQ', 'TRUE_FALSE', 'MATCHING')
  AND ca.is_atomic = true
ORDER BY RANDOM()
LIMIT 10;
```

### Get Due Review Items

```sql
SELECT *
FROM clean_atoms
WHERE anki_due_date <= CURRENT_DATE
  AND atom_type IN ('MCQ', 'TRUE_FALSE', 'MATCHING')
  AND anki_note_id IS NOT NULL
ORDER BY anki_due_date ASC;
```

---

## Implementation Roadmap

### Phase 1: Basic CLI Quiz (Current)

- [ ] MCQ presentation and validation
- [ ] TRUE_FALSE presentation and validation
- [ ] Score tracking per session
- [ ] Basic feedback display

### Phase 2: Enhanced CLI Quiz

- [ ] MATCHING question support
- [ ] Session persistence (resume later)
- [ ] Performance statistics
- [ ] Difficulty filtering

### Phase 3: Spaced Repetition CLI

- [ ] Due date calculation
- [ ] Review scheduling
- [ ] Performance-based rescheduling
- [ ] FSRS integration

### Phase 4: UI Development (Future)

- [ ] Parsons problem interface
- [ ] Drag-and-drop matching
- [ ] Visual code tracing
- [ ] Mobile-responsive design

---

## References

- [Typer CLI Framework](https://typer.tiangolo.com/)
- [Rich Console Library](https://rich.readthedocs.io/)
- [FSRS Algorithm](https://github.com/open-spaced-repetition/fsrs4anki)
- ADR-005: Activity Matrix for Learning Content
