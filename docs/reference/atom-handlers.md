# Atom Handler Reference

Complete reference for the modular atom type handler system in Cortex.

---

## Overview

Atom handlers provide type-specific logic for presenting, validating, and scoring different question types. Each handler implements the `AtomHandler` protocol and is registered via the `@register` decorator.

**Location**: `src/cortex/atoms/`

---

## AtomHandler Protocol

All handlers must implement this interface:

```python
class AtomHandler(Protocol):
    def validate(self, atom: dict) -> bool:
        """Check if atom has required fields for this type."""

    def present(self, atom: dict, console: Console) -> None:
        """Display the question to the user."""

    def get_input(self, atom: dict, console: Console) -> Any:
        """Capture user's answer."""

    def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
        """Validate answer and return result."""

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for attempt N."""
```

---

## AnswerResult Dataclass

Result returned by `check()` method:

```python
@dataclass
class AnswerResult:
    correct: bool              # Whether answer was correct
    feedback: str              # Message to display
    user_answer: str           # What user entered
    correct_answer: str        # Expected answer
    partial_score: float = 1.0 # 0.0-1.0 for partial credit
    explanation: str | None    # Additional context
    dont_know: bool = False    # Triggers Socratic dialogue
```

---

## "I Don't Know" Inputs

Users can indicate unfamiliarity with these inputs:

| Input | Triggers |
|-------|----------|
| `?` | Socratic dialogue |
| `l` | Socratic dialogue |
| `learn` | Socratic dialogue |
| `idk` | Socratic dialogue |
| `dk` | Socratic dialogue |
| `don't know` | Socratic dialogue |

Implementation: `is_dont_know()` function in `src/cortex/atoms/base.py`

---

## Handler Types

### AtomType Enum

```python
class AtomType(str, Enum):
    FLASHCARD = "flashcard"
    CLOZE = "cloze"
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    NUMERIC = "numeric"
    MATCHING = "matching"
    PARSONS = "parsons"
```

---

## Flashcard Handler

**File**: `src/cortex/atoms/flashcard.py`

Basic question/answer cards with quality rating.

### Data Format

| Field | Type | Description |
|-------|------|-------------|
| `front` | string | Question text |
| `back` | string | Answer text |

### User Input

1. Press Space/Enter to reveal answer
2. Rate recall quality (1-4):
   - 1: Complete blackout
   - 2: Incorrect but recognized
   - 3: Correct with effort
   - 4: Effortless recall

### Example

```json
{
  "front": "What does TCP stand for?",
  "back": "Transmission Control Protocol"
}
```

---

## Cloze Handler

**File**: `src/cortex/atoms/cloze.py`

Fill-in-the-blank with masked text.

### Data Format

| Field | Type | Description |
|-------|------|-------------|
| `front` | string | Question with `{{c1::answer}}` syntax |
| `back` | string | Full answer or JSON with explanation |

### Features

- Extracts cloze deletions from `{{c1::answer}}` format
- Fuzzy matching for near-correct answers
- Multiple cloze deletions supported

### Example

```json
{
  "front": "TCP provides {{c1::reliable}} data delivery using {{c2::acknowledgments}}.",
  "back": "reliable, acknowledgments"
}
```

---

## MCQ Handler

**File**: `src/cortex/atoms/mcq.py`

Multiple choice questions with single or multi-select support.

### Data Format (JSON)

```json
{
  "front": "Which protocol uses port 80?",
  "back": {
    "options": ["HTTP", "HTTPS", "FTP", "SSH"],
    "correct": 0,
    "multi_select": false,
    "explanation": "HTTP uses port 80 for unencrypted web traffic."
  }
}
```

### Data Format (Legacy)

```
*HTTP
HTTPS
FTP
SSH
```

Lines starting with `*` are correct answers.

### Features

- **Option Shuffling**: Options randomized per attempt (preserved on retry)
- **Multi-select**: `"multi_select": true` with `"required_count": N`
- **Hints**: Press `h` to eliminate one incorrect option
- **LLM Hints**: When no correct answer marked, uses explanation

### Validation

- Minimum 2 options
- Must have either `correct` index or `explanation`

---

## True/False Handler

**File**: `src/cortex/atoms/true_false.py`

Binary choice questions with LLM-powered error explanation.

### Data Format (JSON)

```json
{
  "front": "TCP is a connectionless protocol.",
  "back": {
    "answer": false,
    "explanation": "TCP is connection-oriented. UDP is connectionless."
  }
}
```

### Data Format (Text)

```
front: "TCP is a connectionless protocol."
back: "False"
```

### Features

- Accepts `T`, `F`, `True`, `False` (case-insensitive)
- LLM error explanation via Gemini 1.5 Flash
- Explanation generated when back field lacks detail

### LLM Prompts

**System**: Explains why statement is true/false with analogy
**User**: Statement, student answer, correct answer

---

## Numeric Handler

**File**: `src/cortex/atoms/numeric.py`

Calculations with tolerance ranges (subnetting, conversions).

### Data Format

```json
{
  "front": "Convert 192.168.1.0/24 to binary. What is the third octet?",
  "back": "1",
  "tolerance": 0,
  "unit": ""
}
```

### Features

- Exact or tolerance-based matching
- Step-by-step hints for calculations
- Supports ranges (e.g., "128-255")

### Hints

1. Formula reminder
2. Step-by-step guidance
3. Partial answer reveal

---

## Parsons Handler

**File**: `src/cortex/atoms/parsons.py`

Code/command ordering problems with partial credit.

### Data Format (JSON)

```json
{
  "front": "Arrange these Cisco commands to configure an interface:",
  "back": "enable -> configure terminal -> interface g0/0 -> ip address 10.0.0.1 255.255.255.0 -> no shutdown"
}
```

### Data Format (List)

```json
{
  "steps": [
    "enable",
    "configure terminal",
    "interface g0/0",
    "ip address 10.0.0.1 255.255.255.0",
    "no shutdown"
  ]
}
```

### Features

- **Scrambling**: Steps randomized (preserved on retry)
- **Partial Credit**: Score based on correct positions
- **Visual Diff**: Three-state feedback (correct position, wrong position, incorrect step)
- **LLM Error Analysis**: Explains first critical error via Gemini

### Hints

| Attempt | Hint |
|---------|------|
| 1 | First step revealed |
| 2 | Last step revealed |
| 3 | Middle step revealed |
| With answer | Shows how many steps are correct |

### Partial Score

```python
partial_score = correct_positions / len(correct_order)
```

---

## Matching Handler

**File**: `src/cortex/atoms/matching.py`

Term-definition pairing for discrimination training.

### Data Format

```json
{
  "front": "Match the protocol to its port number:",
  "back": {
    "pairs": [
      {"term": "HTTP", "definition": "80"},
      {"term": "HTTPS", "definition": "443"},
      {"term": "FTP", "definition": "21"},
      {"term": "SSH", "definition": "22"}
    ]
  }
}
```

### Features

- Terms and definitions shuffled independently
- Partial credit per correct pair
- Supports text-based matching input

### Input Format

User enters pairs as: `1a 2c 3b 4d` (number = term, letter = definition)

---

## Handler Registration

Handlers are registered via decorator:

```python
from src.cortex.atoms import AtomType, register

@register(AtomType.MCQ)
class MCQHandler:
    ...
```

Access handlers via:

```python
from src.cortex.atoms import get_handler

handler = get_handler("mcq")  # or get_handler(AtomType.MCQ)
```

---

## Adding New Handlers

1. Create new file in `src/cortex/atoms/`
2. Import `AtomType`, `register`, and `AnswerResult`
3. Implement `AtomHandler` protocol
4. Add type to `AtomType` enum
5. Import in `src/cortex/atoms/__init__.py`

Example skeleton:

```python
from . import AtomType, register
from .base import AnswerResult, is_dont_know

@register(AtomType.NEW_TYPE)
class NewTypeHandler:
    def validate(self, atom: dict) -> bool:
        return bool(atom.get("front") and atom.get("back"))

    def present(self, atom: dict, console: Console) -> None:
        console.print(atom["front"])

    def get_input(self, atom: dict, console: Console) -> dict:
        response = Prompt.ask("Answer")
        if is_dont_know(response):
            return {"dont_know": True}
        return {"answer": response}

    def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
        if answer.get("dont_know"):
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=atom["back"],
                dont_know=True,
            )

        is_correct = answer["answer"].lower() == atom["back"].lower()
        return AnswerResult(
            correct=is_correct,
            feedback="Correct!" if is_correct else "Incorrect.",
            user_answer=answer["answer"],
            correct_answer=atom["back"],
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        if attempt == 1:
            return f"The answer starts with: {atom['back'][:3]}..."
        return None
```

---

## See Also

- [Architecture Overview](../explanation/architecture.md)
- [Cognitive Diagnosis](../explanation/cognitive-diagnosis.md)
- [Adaptive Learning](../explanation/adaptive-learning.md)
