# Session Remediation System

This document explains the error handling and remediation features of the Cortex study session, including the Remediation Learning Loop, immediate retry logic, hint generation, post-session remediation options, and study notes generation.

---

## Overview

The Cortex session runner implements evidence-based remediation strategies that activate when learners make errors. Rather than simply marking answers wrong and moving on, the system provides scaffolded support through hints, immediate retry opportunities, and targeted suggestions for continued practice.

**Design principle**: Immediate corrective feedback with scaffolding improves retention compared to delayed or absent feedback (Roediger & Butler, 2011).

---

## Remediation Learning Loop

The Remediation Learning Loop is a multi-phase system that supports honest learning when content is unfamiliar:

| Phase | Trigger | Action |
|-------|---------|--------|
| **Pre-Session** | Session start | Check for unread notes related to queued atoms |
| **During Session** | "I don't know" input | Reveal answer; track for note generation |
| **During Session** | 2+ consecutive errors | Display micro-note for struggling section |
| **Post-Session** | Struggled sections exist | Offer LLM note generation |
| **Hub Menu** | Manual access | Browse, rate, and generate notes |

### "I Don't Know" Option

All atom handlers support an honest "I don't know" response. Instead of guessing randomly (which creates false signal in the spaced repetition system), learners can indicate unfamiliarity.

**Trigger inputs**: `?`, `l`, `learn`, `idk`, `dk`

**Implementation** in `src/cortex/atoms/base.py`:

```python
DONT_KNOW_INPUTS = {"?", "l", "learn", "idk", "dk", "don't know", "dont know"}

def is_dont_know(user_input: str) -> bool:
    """Check if input indicates 'I don't know'."""
    return user_input.strip().lower() in DONT_KNOW_INPUTS
```

**Behavior**:
1. **Socratic dialogue is triggered** (see below)
2. `dont_know_count` is incremented in database for the atom
3. Section is flagged for potential note generation
4. Dialogue outcome determines whether marked as correct/incorrect

**Rationale**: Guessing creates false positive and negative signals in the spaced repetition algorithm. Honest admission of ignorance allows the system to route learners to foundational material rather than drilling unfamiliar content.

### Socratic Dialogue System

When a learner says "I don't know", the system enters an interactive Socratic tutoring dialogue instead of immediately revealing the answer.

**Implementation** in `src/cortex/socratic.py`:

| Component | Purpose |
|-----------|---------|
| `SocraticTutor` | Manages dialogue sessions with progressive scaffolding |
| `SocraticSession` | Tracks dialogue state, turns, and detected gaps |
| `DialogueRecorder` | Persists dialogues to `socratic_dialogues` table |
| `RemediationRecommender` | Suggests related atoms based on detected gaps |

**Scaffold Levels**:

| Level | Name | Behavior |
|-------|------|----------|
| 0 | Pure Socratic | Questions only, no hints |
| 1 | Nudge | Conceptual nudge ("Think about...") |
| 2 | Partial | Partial reveal ("The answer involves...") |
| 3 | Worked | Worked example with gaps |
| 4 | Reveal | Full answer with explanation |

**Resolution Types**:

| Resolution | Meaning | Impact |
|------------|---------|--------|
| `self_solved` | Learner figured it out at scaffold level 0 | Counted as correct |
| `guided_solved` | Solved with hints (level 1-3) | Counted as correct |
| `gave_up` | Learner requested skip | Counted as incorrect |
| `revealed` | Full answer shown (level 4) | Counted as incorrect |

**Answer Validation** (`_check_answer_correct` method):

The Socratic tutor validates learner responses against the correct answer:

- **MCQ with `correct` index**: Validates against the marked correct option(s)
- **MCQ with `correct: null`**: Returns `False` (cannot validate without known answer)
- **Text answers**: Uses key term matching (60% threshold for majority match)

**Important**: MCQs with `correct: null` AND no explanation are now filtered out during validation to prevent unusable questions from appearing.

**Cognitive Signal Detection**:

| Signal | Detection | Action |
|--------|-----------|--------|
| `confused` | "I don't understand", "??", long latency | Escalate scaffold level |
| `progressing` | "Oh I see", "that means" | Maintain current level |
| `stuck` | 3+ consecutive short responses | Escalate to reveal |
| `prerequisite_gap` | Missing foundational knowledge | Trigger remediation recommendations |

### Pre-Session Note Check

Before starting a study session, the system checks for unread remediation notes related to queued atoms.

**Implementation** in `src/cortex/session.py:_check_unread_notes()`:

1. Extract unique `ccna_section_id` values from queued atoms
2. Query `remediation_notes` for unread, qualified notes matching those sections
3. Offer to display notes before practicing
4. Navigate with Enter (next) / q (skip) controls

### Micro-Notes During Session

When a learner makes 2 or more consecutive errors on atoms from the same section, the system displays a quick review.

**Tracking** in `src/cortex/session.py`:

```python
# Micro-note tracking (consecutive errors by section)
self._section_error_streak: dict[str, int] = {}
self._micro_note_shown: set[str] = set()
```

**Trigger logic**:
- Track consecutive errors per `ccna_section_id`
- Reset streak to 0 on correct answer
- Trigger micro-note when streak >= 2 and note not already shown this session

**Display behavior**:
- Show existing note content if available (first 500 characters)
- Fall back to generic tips if no note exists
- Only trigger once per section per session (prevents spam)

---

## Immediate Retry System

### Two-Attempt Model

When a learner answers incorrectly, the system follows a two-attempt remediation flow:

| Attempt | Outcome | System Response |
|---------|---------|-----------------|
| First wrong | Error detected | Display contextual hint; allow immediate retry |
| Second wrong | Persistent error | Display correct answer; track for Anki suggestions |
| Correct (first) | Success | Continue to next question |
| Correct (retry) | Recovery | Continue; original error still tracked |

**Rationale**: This model provides learners the opportunity to self-correct with scaffolding before revealing the answer. Self-correction with hints produces stronger memory traces than passive answer viewing (Metcalfe & Kornell, 2007).

### Implementation

The retry flow in `src/cortex/session.py`:

```python
if not is_correct and not is_retry:
    hint = self._generate_hint(note)
    # Display hint panel
    note["_retry_attempt"] = True
    continue  # Re-present same atom

# After second attempt
if not is_correct:
    self._show_correct_answer(note)
    self._incorrect_atoms.append(note)  # Track for Anki suggestions
```

---

## Hint Generation

### Type-Specific Hints

The `_generate_hint()` method generates contextual hints based on atom type:

| Atom Type | Hint Strategy | Example |
|-----------|---------------|---------|
| **Parsons** | Show first step | "Start with: Configure the interface" |
| **MCQ** | Elimination guidance | "Eliminate: TCP is likely incorrect" |
| **True/False** | Absolute word warning | "Watch out for words like always or never" |
| **Matching** | Free match reveal | "One match: OSPF --> Link-state" |
| **Numeric** | Magnitude range | "The answer is between 10 and 100" |

### Design Rationale

Hints provide scaffolding without giving away the answer:

- **Parsons**: First step anchors the sequence. Ordering problems become tractable once the starting point is known.
- **MCQ**: Elimination reduces cognitive load from 4 options to 3. Does not eliminate the correct answer.
- **True/False**: Alerts learners to common linguistic traps. Absolute statements are frequently false.
- **Matching**: One free pair reduces remaining combinations and provides a correctness signal.
- **Numeric**: Magnitude hints prevent order-of-magnitude errors while requiring precise calculation.

---

## Correct Answer Display

After the second failed attempt, `_show_correct_answer()` displays the full solution:

### Display Format by Type

**Parsons problems**: Numbered step sequence
```
Correct answer:
  [1] Enter global configuration mode
  [2] Configure the interface
  [3] Assign IP address
  [4] Enable the interface
```

**Note**: Parsons problems display a clean interface without misleading default prompts. The question panel uses reduced height to maximize space for step ordering.

**MCQ**: Correct option with explanation (if available)
```
Correct answer:
  TCP (Transmission Control Protocol)

[Explanation: TCP provides reliable, connection-oriented delivery]
```

**Matching**: Complete pair mapping
```
Correct answer:
  OSPF --> Link-state
  RIP --> Distance-vector
  EIGRP --> Hybrid
```

---

## Fatigue Detection

### Threshold Configuration

The NCDE pipeline monitors cognitive fatigue through a multi-dimensional vector. The fatigue threshold was calibrated to reduce false positives:

| Parameter | Previous Value | Current Value | Rationale |
|-----------|---------------|---------------|-----------|
| `is_critical` threshold | 0.70 | 0.85 | 3D Euclidean norm reaches 0.7 too quickly with normal activity |

### Minimum Session Requirements

Fatigue detection activates only after sufficient session activity:

| Condition | Threshold | Purpose |
|-----------|-----------|---------|
| Minimum interactions | 10+ questions | Baseline data for fatigue calculation |
| Minimum duration | 10+ minutes | Time under cognitive load |

**Evidence basis**: Cognitive fatigue detection requires baseline data. Early-session responses may show high variability that resembles fatigue but reflects warm-up effects rather than depletion.

### Post-Break Grace Period

After a micro-break, response times often remain variable as learners re-engage. To prevent immediate re-triggering of fatigue detection:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `_post_break_grace` | 5 questions | Skip fatigue detection after break |

**Implementation**: The `CortexSession` class maintains a `_post_break_grace` counter that decrements with each question. While positive, fatigue detection is bypassed.

```python
# In src/cortex/session.py
if self._post_break_grace > 0:
    self._post_break_grace -= 1
    # Skip fatigue detection
else:
    # Normal fatigue detection
```

**Rationale**: Response times immediately post-break may be slower due to context-switching, not cognitive depletion. The 5-question grace period allows re-acclimation before resuming fatigue monitoring.

### Implementation

In `src/adaptive/ncde_pipeline.py`, the `RemediationSelector.select()` method:

```python
if fatigue.is_critical:
    total_interactions = session_context.correct_count + session_context.incorrect_count
    min_interactions_met = total_interactions >= 10
    min_time_met = session_context.duration_seconds >= 600  # 10 minutes

    if min_interactions_met or min_time_met:
        return MicroBreakStrategy(break_minutes=10)
    else:
        # Ignore fatigue signal - insufficient baseline data
        pass
```

---

## Log Level Configuration

### Session-Time Log Suppression

During interactive sessions, verbose DEBUG logs degrade the user experience. The session module configures loguru to INFO level:

```python
from loguru import logger as loguru_logger

loguru_logger.remove()  # Remove default DEBUG handler
loguru_logger.add(
    sys.stderr,
    level="INFO",
    format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}",
)
```

**Result**: Clean terminal output with only actionable information. DEBUG logs remain available when running scripts directly.

---

## Post-Session Remediation Menu

At session end, if the learner struggled with any sections, Cortex presents an interactive remediation menu:

### Menu Options

```
REMEDIATION OPTIONS

You struggled with 3 section(s). What would you like to do?

  [1] Generate study notes for struggled topics
  [2] Generate additional practice questions
  [3] Full Anki sync (push atoms + pull stats)
  [s] Skip remediation

Your choice:
```

| Option | Action | Use Case |
|--------|--------|----------|
| **1** | Generate adaptive study notes | Deep review of weak concepts |
| **2** | Generate LLM practice questions | Additional retrieval practice |
| **3** | Full Anki sync | Sync progress to mobile device |
| **s** | Skip | No remediation needed |

### Implementation

The `_offer_post_session_remediation()` method in `src/cortex/session.py` presents options based on session outcomes:

```python
def _offer_post_session_remediation(self):
    if not self._incorrect_atoms:
        return  # No struggles, no menu

    # Group errors by section
    section_errors = {}
    for atom in self._incorrect_atoms:
        section_id = atom.get("ccna_section_id") or atom.get("section_id")
        if section_id not in section_errors:
            section_errors[section_id] = []
        section_errors[section_id].append(atom)

    # Find weak sections (threshold: 1+ error if 3+ total, else 2+)
    weak_sections = [
        (section_id, atoms)
        for section_id, atoms in section_errors.items()
        if len(atoms) >= threshold and section_id != "unknown"
    ]

    # Offer automatic remediation cycle
    if Confirm.ask("Start automatic remediation? (Note -> Practice)"):
        self._run_remediation_cycle(weak_sections)
```

---

## Automatic AI Remediation Cycle

When the learner accepts automatic remediation, the system runs a structured cycle for each weak section:

### Cycle Flow

```
For each weak section:
  1. Generate/fetch study note
  2. Display note content
  3. Learner presses Enter to continue
  4. Serve 5-10 targeted exercises
  5. Track pre/post accuracy
  6. Display improvement feedback
```

### Implementation

The `_run_remediation_cycle()` method in `src/cortex/session.py`:

```python
def _run_remediation_cycle(self, weak_sections):
    for section_id, error_atoms in weak_sections:
        # Step 1: Generate or fetch note
        note_content = self._get_or_generate_note(section_id, error_atoms)

        if note_content:
            # Step 2: Display note
            panel = Panel(
                Markdown(note_content.get("content", "")),
                title=note_content.get("title"),
                border_style="cyan",
            )
            console.print(panel)
            console.input("Press Enter to practice this section...")

        # Step 3: Fetch exercises
        exercises = self.study_service.get_manual_session(
            sections=[section_id],
            atom_types=["mcq", "true_false", "cloze", "numeric"],
            limit=5,
        )

        # Step 4: Run mini-session
        pre_error_rate = len(error_atoms) / max(1, self.correct + self.incorrect)
        result = self._run_mini_session(exercises, section_id)
        post_error_rate = result.incorrect / max(1, result.total)

        # Step 5: Display effectiveness
        improvement = pre_error_rate - post_error_rate
        if improvement > 0.1:
            console.print(f"Improvement detected: {improvement:.0%} better!")
```

### Key Methods

| Method | Purpose |
|--------|---------|
| `_run_remediation_cycle()` | Orchestrates the Note -> Practice flow |
| `_get_or_generate_note()` | Fetches existing or generates new study note |
| `_run_mini_session()` | Runs targeted practice with provided exercises |

### Mini-Session

The `_run_mini_session()` method runs a focused practice session:

```python
def _run_mini_session(self, exercises, section_id):
    result = MiniSessionResult(total=0, correct=0, incorrect=0)

    for i, atom in enumerate(exercises, 1):
        handler = get_atom_handler(atom.get("atom_type"))
        response = handler.present(console, atom)
        is_correct, feedback = handler.evaluate(atom, response)

        if is_correct:
            result.correct += 1
        else:
            result.incorrect += 1
        result.total += 1

    return result
```

### Effectiveness Tracking

The system tracks pre/post accuracy to measure remediation effectiveness:

| Metric | Calculation |
|--------|-------------|
| Pre-Error Rate | `len(error_atoms) / (correct + incorrect)` |
| Post-Error Rate | `mini_session.incorrect / mini_session.total` |
| Improvement | `pre_error_rate - post_error_rate` |

Feedback thresholds:
- **> 10% improvement**: "Improvement detected!"
- **Perfect score**: "Perfect score on remediation exercises!"
- **Other**: Shows raw accuracy

---

## NCDE Fail Mode Strategies

The remediation system uses NCDE diagnosis to select appropriate content strategies. The `FAIL_MODE_STRATEGIES` mapping in `src/adaptive/remediation_router.py` defines targeted remediation for each cognitive failure type.

### Strategy Mapping

| Fail Mode | Note Type | Atom Types | Exercise Count | Rationale |
|-----------|-----------|------------|----------------|-----------|
| **FM1_ENCODING** | Elaborative | flashcard, cloze | 8 | Information never properly stored; deep explanation + memorization drills |
| **FM2_RETRIEVAL** | None | flashcard, cloze, mcq | 10 | Stored but cannot access; practice-only to strengthen retrieval pathways |
| **FM3_DISCRIMINATION** | Contrastive | matching, mcq, true_false | 6 | Confuses similar concepts; side-by-side comparison + discrimination drills |
| **FM4_INTEGRATION** | Procedural | parsons, numeric | 5 | Cannot apply knowledge in context; worked examples + procedure practice |
| **FM5_EXECUTIVE** | Summary | mcq, true_false | 8 | Wrong strategy selection; strategy review + decision practice |
| **FM6_FATIGUE** | None | None | 0 | Cognitive overload; suggest break, no new content |

### Note Types

| Type | Description |
|------|-------------|
| `elaborative` | Deep explanation with multiple examples |
| `contrastive` | Side-by-side comparison of similar concepts |
| `procedural` | Step-by-step worked examples |
| `summary` | High-level overview and key takeaways |

### Usage

```python
from src.adaptive.remediation_router import get_remediation_strategy

strategy = get_remediation_strategy("FM3_DISCRIMINATION")
# Returns: {
#     "note_type": "contrastive",
#     "atom_types": ["matching", "mcq", "true_false"],
#     "description": "Side-by-side comparison + discrimination drills",
#     "exercise_count": 6
# }
```

The function supports flexible input formats:
- Uppercase with underscores: `"FM1_ENCODING"`
- Lowercase: `"fm1_encoding"`
- Partial match: `"encoding"`, `"retrieval"`

---

## Study Notes Generation

When learners struggle with specific sections, Cortex generates personalized study notes using LLM.

### Adaptive Depth Selection

Note depth adjusts based on error rate:

| Error Rate | Depth | Content Volume |
|------------|-------|----------------|
| < 25% | `brief` | Core concept only |
| 25-50% | `standard` | Core + memory anchors |
| >= 50% | `comprehensive` | Full deep-dive |

### Note Structure

Generated notes include:

| Section | Purpose |
|---------|---------|
| **Core Concept** | Essential definition and explanation |
| **What You Got Wrong** | Analysis of specific errors made |
| **Memory Anchors** | Mnemonics and associations |
| **Quick Reference** | Summary table or bullet points |
| **Key Commands** | CLI/configuration commands (if applicable) |

### Output Handling

Study notes are:

1. **Displayed in terminal** using Rich markdown rendering
2. **Saved to disk** at `outputs/notes/{timestamp}-{section_ids}.md`

### Implementation

The `_generate_study_notes()` method in `src/cortex/session.py`:

```python
def _generate_study_notes(self):
    for section_id in struggled_sections:
        error_rate = self._calculate_section_error_rate(section_id)

        if error_rate < 0.25:
            depth = "brief"
        elif error_rate < 0.50:
            depth = "standard"
        else:
            depth = "comprehensive"

        notes = generator.generate_study_notes(
            section_content=content,
            section_id=section_id,
            section_title=title,
            struggle_data=struggles,
            error_patterns=patterns,
            cognitive_state=state,
            depth=depth,
        )

        # Display with Rich markdown
        console.print(Markdown(notes))

        # Save to file
        save_path = f"outputs/notes/{timestamp}-{section_id}.md"
```

### Note Quality Tracking

The system automatically tracks note effectiveness through multiple signals:

| Metric | Description | Source |
|--------|-------------|--------|
| `read_count` | Number of times note was read | `note_read_history` table |
| `user_rating` | 1-5 rating from user | Manual input after reading |
| `pre_error_rate` | Section error rate before first read | Computed from `learning_atoms` |
| `post_error_rate` | Section error rate after reading | Computed after next session |
| `effectiveness` | `pre_error_rate - post_error_rate` | Computed column |

**Quality Score Calculation** in `src/learning/note_generator.py:evaluate_note_quality()`:

```python
score = 50  # Base score

# Rating contribution: +/- 20 based on rating
if user_rating:
    score += (user_rating - 3) * 10

# Improvement contribution
if pre_error_rate and post_error_rate:
    improvement = pre_error_rate - post_error_rate
    if improvement > 0.1:
        score += 20
    elif improvement > 0:
        score += 10
    elif improvement < -0.1:
        score -= 20

# Note is "qualified" if score >= 40
```

Notes with `qualified = FALSE` are excluded from display and recommendations.

---

## Hub Menu: Browse Study Notes

The Cortex hub includes a dedicated study notes browser (Option 7).

### Access

```
CORTEX HUB

  [1] Start adaptive session
  ...
  [7] Browse study notes
  [q] Quit
```

### Sub-Menu Options

| Option | Action |
|--------|--------|
| **1** | View all qualified notes |
| **2** | View unread notes only |
| **3** | Generate notes for weak sections |
| **b** | Return to hub |

### Note Viewer

When viewing a note:
1. Full markdown content is rendered in terminal
2. Note is marked as read in `note_read_history`
3. User is prompted for 1-5 rating
4. Rating is stored and contributes to quality score

### Note Generation

Option 3 identifies sections needing notes based on:
- `anki_lapses` count across atoms in section
- `dont_know_count` across atoms in section
- Minimum threshold of 2 combined errors

For each section without an existing note, the system:
1. Loads source material from `docs/source-materials/CCNA/`
2. Generates note via Google Generative AI (gemini-1.5-flash)
3. Stores in `remediation_notes` table
4. Sets 30-day expiration

---

## Anki Filtered Deck Suggestions

### Purpose

After a session, the system generates Anki filtered deck queries for sections where the learner struggled. This enables targeted mobile review of weak areas.

### Query Format

```
deck:CCNA::ITN::* (tag:section:X.Y OR tag:section:X.Z) -is:suspended
```

Components:
- `deck:CCNA::ITN::*` - Searches the CCNA deck hierarchy
- `tag:section:X.Y` - Filters to struggled sections
- `-is:suspended` - Excludes suspended cards

### Display

The `_display_anki_suggestions()` method shows at session end:

```
ANKI STUDY SUGGESTION

You struggled with 3 section(s). Use this filtered deck query:

deck:CCNA::ITN::* (tag:section:3.2 OR tag:section:5.1 OR tag:section:7.4) -is:suspended

Sections to review:
  - 3.2
  - 5.1
  - 7.4

[Instructions: Anki -> Tools -> Create Filtered Deck -> paste query]
```

### Section Extraction

The system extracts section IDs from multiple sources:
1. `section_id` field on atom
2. `tag:section:X.Y` format in tags array
3. `source_section` field as fallback

---

## Bi-Directional Anki Sync

Cortex synchronizes with Anki in both directions to maintain consistent scheduling state.

### Automatic Session Sync

At session start, Cortex automatically pulls FSRS statistics from Anki:

```python
def _start_session(self):
    self.sync_anki()  # Pull latest stats before loading queue
    self._load_queue()
```

**Purpose**: Ensures scheduling decisions reflect any reviews performed in Anki since the last Cortex session.

### Full Sync Option

The remediation menu offers full bidirectional sync:

| Direction | Operation | Data |
|-----------|-----------|------|
| **Push** | Cortex -> Anki | New atoms, updated content |
| **Pull** | Anki -> Cortex | FSRS stability, review counts, due dates |

### Graceful Degradation

If Anki is unavailable (not running, AnkiConnect not installed):

```python
def sync_anki(self):
    try:
        self._anki_client.pull_stats()
    except ConnectionError:
        logger.info("Anki not available - skipping sync")
        # Session continues without sync
```

The system logs the unavailability and continues without blocking the session.

See [Configure Anki Sync](../how-to/configure-anki-sync.md) for setup instructions.

---

## LLM Content Generation

### Purpose

When learners struggle with specific sections, the system can generate additional practice questions using an LLM (Gemini API).

### Activation

The feature activates when:
1. `GEMINI_API_KEY` is configured
2. Session completed with errors
3. User selects option 2 from remediation menu

### Generation Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Max sections | 3 | Prevent overwhelming content generation |
| Cards per section | 3 | Targeted practice volume |
| Quality validation | Disabled | Speed; generated content is supplementary |

### Implementation Flow

```python
def _offer_llm_generation(self):
    if not self._incorrect_atoms:
        return

    for section_id in weak_sections[:3]:
        cards = generator.generate_from_section(
            section_id=section_id,
            max_cards=3,
        )
```

**Note**: Uses `generate_from_section()` method (not `generate_from_text()`).

---

## Configuration

### Environment Variables

```bash
# Fatigue detection
NCDE_FATIGUE_THRESHOLD=0.85
NCDE_MIN_INTERACTIONS_FOR_FATIGUE=10
NCDE_MIN_DURATION_FOR_FATIGUE_SECONDS=600

# LLM generation
GEMINI_API_KEY=your-api-key

# Study notes output
STUDY_NOTES_OUTPUT_DIR=outputs/notes
```

### Log Level

The session log level is hardcoded to INFO. To enable DEBUG logging for troubleshooting, modify `src/cortex/session.py`:

```python
loguru_logger.add(sys.stderr, level="DEBUG", ...)
```

---

## Design Decisions

### Why Two Attempts Instead of Three?

Two attempts balances feedback with session pacing:
- One attempt provides no opportunity for self-correction
- Three or more attempts frustrates learners and slows session progress
- Two attempts allows scaffolded recovery without excessive repetition

### Why Not Show Hints Immediately?

Initial attempt without hints tests genuine recall. Premature hints:
- Prevent accurate assessment of knowledge state
- May become a crutch that reduces learning effort
- Inflate apparent accuracy beyond true mastery

### Why Track Errors Even After Retry Success?

A successful retry indicates recent learning, not durable knowledge. Tracking ensures:
- Anki suggestions include recovered items
- FSRS stability reflects the error
- Future sessions may revisit the concept

### Why Adaptive Depth for Study Notes?

Note verbosity scales with struggle intensity:
- Low error rates indicate near-mastery; brief notes suffice
- High error rates indicate conceptual gaps; comprehensive notes address root causes
- This prevents cognitive overload from unnecessary detail

### Why Grace Period After Breaks?

Post-break cognitive state differs from mid-session fatigue:
- Context-switching adds response latency
- Mental re-engagement takes several questions
- Without grace period, breaks would immediately trigger more breaks

---

## References

- Metcalfe, J., & Kornell, N. (2007). Principles of cognitive science in education: The effects of generation, errors, and feedback. *Psychonomic Bulletin & Review, 14*(2), 225-229.
- Roediger, H. L., & Butler, A. C. (2011). The critical role of retrieval practice in long-term retention. *Trends in Cognitive Sciences, 15*(1), 20-27.

---

## See Also

- [Use Study Notes](../how-to/use-study-notes.md) - How-to guide for the Remediation Learning Loop
- [Cognitive Diagnosis](cognitive-diagnosis.md) - NCDE error classification
- [Adaptive Learning](adaptive-learning.md) - Card selection and scheduling
- [Struggle-Aware System](struggle-aware-system.md) - Dynamic struggle tracking integration
- [Database Schema](../reference/database-schema.md) - `remediation_notes` table reference
- [First Study Session](../tutorials/first-study-session.md) - Tutorial for new users
- [Configure Anki Sync](../how-to/configure-anki-sync.md) - Anki integration setup
