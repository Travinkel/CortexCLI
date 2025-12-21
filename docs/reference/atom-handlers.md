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

## Partial Credit System

### When to Use Partial Scoring

Partial credit should be used for atom types where learners demonstrate **partial knowledge**:

| Atom Type | Partial Credit? | Calculation |
|-----------|-----------------|-------------|
| **Flashcard** | No | Binary (0.0 or 1.0) |
| **True/False** | No | Binary (0.0 or 1.0) |
| **MCQ (single)** | No | Binary (0.0 or 1.0) |
| **Cloze (single)** | Maybe | Fuzzy match can give partial credit |
| **Matching** | Yes | `correct_pairs / total_pairs` |
| **Parsons** | Yes | `correct_positions / total_steps` |
| **MCQ (multi)** | Yes | `correct_selections / required_count` |
| **Numeric (range)** | Yes | Proportional to distance from correct |
| **Sequencing** | Yes | `correct_positions / total_items` |

### Implementation Pattern

```python
def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
    correct_items = sum(1 for i, item in enumerate(user_answer)
                       if item == correct_answer[i])
    partial_score = correct_items / len(correct_answer)

    return AnswerResult(
        correct=(partial_score == 1.0),
        feedback=self._generate_feedback(partial_score),
        user_answer=str(answer),
        correct_answer=str(correct_answer),
        partial_score=partial_score,  # 0.0-1.0
    )
```

### Examples from Production Handlers

**Matching Handler:**
```python
correct_count = sum(1 for i, term in enumerate(terms)
                   if user_matches.get(i) == correct_matches[i])
partial_score = correct_count / len(terms)
```

**Parsons Handler:**
```python
correct_positions = sum(1 for i, step in enumerate(user_order)
                       if step == correct_order[i])
partial_score = correct_positions / len(correct_order)
```

---

## Progressive Hint System

### Design Principles

1. **Escalating Support**: Each hint reveals more information
2. **Avoid Direct Answers**: Guide thinking, don't solve it
3. **Leverage Previous Attempts**: Use user's wrong answer to tailor hints
4. **Stop at Threshold**: Typically 2-3 hints before revealing answer

### Hint Pattern by Atom Type

| Atom Type | Hint 1 | Hint 2 | Hint 3 |
|-----------|--------|--------|--------|
| **Cloze** | First letter | Length + first/last | Full answer |
| **Numeric** | Formula reminder | Step-by-step | Partial calculation |
| **Parsons** | First step | Last step | Middle step |
| **MCQ** | Eliminate 1 wrong | Eliminate 2 wrong | Reveal correct |
| **Matching** | Reveal 1-2 pairs | Reveal half | Reveal most |

### Implementation Template

```python
def hint(self, atom: dict, attempt: int) -> str | None:
    """Progressive hints based on attempt count."""

    # Hint 1: Gentle nudge
    if attempt == 1:
        return "Think about the relationship between X and Y..."

    # Hint 2: More specific guidance
    elif attempt == 2:
        answer = atom.get("back", "")
        return f"The answer starts with '{answer[0]}' and has {len(answer)} letters"

    # Hint 3: Near-complete reveal
    elif attempt == 3:
        answer = atom.get("back", "")
        return f"First word: '{answer.split()[0]}...'"

    # No more hints
    return None
```

### Adaptive Hints (Using User's Answer)

```python
def hint(self, atom: dict, attempt: int) -> str | None:
    """Tailor hint based on user's last attempt."""

    if attempt == 1:
        # Generic first hint
        return "Consider the execution order of these commands..."

    # Access user's previous attempt from atom runtime state
    last_attempt = atom.get("_last_user_attempt", [])
    correct_order = atom["steps"]

    # Find first error position
    first_error = next((i for i, step in enumerate(last_attempt)
                       if step != correct_order[i]), None)

    if first_error is not None:
        return f"Check position {first_error + 1}. This step comes earlier/later..."

    return None
```

---

## Validation Rules

### Required Fields by Atom Type

| Atom Type | Required Fields | Optional Fields |
|-----------|----------------|-----------------|
| **All Types** | `front` | `back`, `content_json`, `metadata` |
| **MCQ** | `back` (with `options`) | `explanation`, `multi_select`, `required_count` |
| **Cloze** | `front` (with `{{...}}`) | `hints`, `case_sensitive` |
| **Matching** | `pairs` (min 2) | `shuffle_terms`, `shuffle_defs` |
| **Parsons** | `steps` or `back` (with `->`) | `source_fact_basis`, `explanation` |
| **Numeric** | `back` (numeric) | `tolerance`, `unit`, `numeric_steps` |

### Validation Implementation

```python
def validate(self, atom: dict) -> bool:
    """Strict validation to prevent runtime errors."""

    # Check required fields
    if not atom.get("front"):
        return False

    # Type-specific validation
    content = atom.get("content_json", {})

    # Example: MCQ validation
    options = content.get("options", [])
    if len(options) < 2:
        return False

    # Check for correct answer marker
    has_correct = (
        "correct" in content or
        "explanation" in content or
        any(opt.startswith("*") for opt in options)
    )

    if not has_correct:
        return False

    return True
```

### Quality Constraints

Beyond basic validation, handlers can enforce quality standards:

```python
def validate(self, atom: dict) -> bool:
    """Enhanced validation with quality checks."""

    if not atom.get("front"):
        return False

    # Atomicity check: front text shouldn't be too long
    front_words = len(atom["front"].split())
    if front_words > 50:  # Too complex for single atom
        logger.warning(f"Atom {atom.get('id')} front text too long: {front_words} words")
        return False

    # Ensure back field has substance
    back = atom.get("back", "")
    if isinstance(back, str) and len(back.strip()) < 2:
        return False

    return True
```

---

## Best Practices for Handler Development

### 1. Preserve State Across Retries

Store runtime state in the atom dict with `_` prefix:

```python
def present(self, atom: dict, console: Console) -> None:
    # First presentation: shuffle options
    if "_shuffled_options" not in atom:
        options = atom["options"].copy()
        random.shuffle(options)
        atom["_shuffled_options"] = options

    # Subsequent retries: use same shuffled order
    options = atom["_shuffled_options"]
    # ... display options
```

### 2. Handle "I Don't Know" Gracefully

```python
def get_input(self, atom: dict, console: Console) -> Any:
    response = Prompt.ask("Answer")

    if is_dont_know(response):
        return {"dont_know": True}

    # Parse actual answer
    return {"answer": self._parse_response(response)}

def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
    if answer.get("dont_know"):
        return AnswerResult(
            correct=False,
            feedback="",  # Socratic dialogue will handle this
            user_answer="I don't know",
            correct_answer=atom["back"],
            dont_know=True,  # Triggers Socratic flow
        )
    # ... normal validation
```

### 3. Use Rich for Terminal-Native UX

```python
from rich.table import Table
from rich.panel import Panel

def present(self, atom: dict, console: Console) -> None:
    # Create visually distinct panel
    panel = Panel(
        atom["front"],
        title="[bold cyan]Question[/bold cyan]",
        border_style="cyan"
    )
    console.print(panel)

    # Use table for structured data
    table = Table(show_header=False, box=None)
    for i, option in enumerate(options, 1):
        table.add_row(f"[{i}]", option)
    console.print(table)
```

### 4. Fail-Safe Error Handling

```python
def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
    try:
        # Main validation logic
        is_correct = self._validate_answer(atom, answer)
        # ... generate result

    except Exception as e:
        logger.error(f"Error checking atom {atom.get('id')}: {e}")

        # Graceful degradation: mark as incorrect but allow continuation
        return AnswerResult(
            correct=False,
            feedback=f"Error validating answer: {str(e)}",
            user_answer=str(answer),
            correct_answer=str(atom.get("back", "Unknown")),
            partial_score=0.0,
        )
```

### 5. LLM Integration for Explanations

```python
def check(self, atom: dict, answer: Any, console: Console | None) -> AnswerResult:
    is_correct = (user_answer == correct_answer)

    # Generate LLM explanation for wrong answers
    if not is_correct and console is not None:
        explanation = self._generate_explanation(atom, user_answer, correct_answer)
    else:
        explanation = atom.get("explanation")

    return AnswerResult(
        correct=is_correct,
        feedback="Correct!" if is_correct else "Not quite.",
        user_answer=user_answer,
        correct_answer=correct_answer,
        explanation=explanation,
    )

def _generate_explanation(self, atom: dict, user_answer: str, correct_answer: str) -> str:
    """Call LLM to explain the error."""
    from src.ai.llm_client import get_llm_client

    prompt = f"""The student answered '{user_answer}' to this question:
    {atom['front']}

    The correct answer is '{correct_answer}'.

    Explain why in 1-2 sentences, using an analogy if helpful."""

    client = get_llm_client()
    return client.generate(prompt, max_tokens=100)
```

### 6. Testing Your Handler

```python
# tests/unit/atoms/test_your_type.py
import pytest
from src.cortex.atoms.your_type import YourTypeHandler

def test_validate_valid_atom():
    handler = YourTypeHandler()
    atom = {"front": "Q?", "back": "A"}
    assert handler.validate(atom) is True

def test_validate_missing_fields():
    handler = YourTypeHandler()
    atom = {"front": "Q?"}  # Missing back
    assert handler.validate(atom) is False

def test_check_correct_answer():
    handler = YourTypeHandler()
    atom = {"front": "Q?", "back": "answer"}
    result = handler.check(atom, {"answer": "answer"}, None)
    assert result.correct is True
    assert result.partial_score == 1.0

def test_check_partial_credit():
    handler = YourTypeHandler()
    atom = {"front": "Q?", "steps": ["A", "B", "C"]}
    result = handler.check(atom, ["A", "C", "B"], None)  # 1 of 3 correct
    assert result.correct is False
    assert result.partial_score == pytest.approx(0.33, rel=0.01)

def test_hint_progression():
    handler = YourTypeHandler()
    atom = {"front": "Q?", "back": "answer"}

    hint1 = handler.hint(atom, 1)
    hint2 = handler.hint(atom, 2)
    hint3 = handler.hint(atom, 3)

    assert hint1 is not None
    assert hint2 is not None
    assert len(hint2) > len(hint1)  # More detailed
    assert hint3 is None or "answer" in hint3.lower()  # Near-complete reveal
```

---

## Handler Development Checklist

When creating a new atom type handler:

- [ ] **Validation**
  - [ ] Check all required fields exist
  - [ ] Validate field types and constraints
  - [ ] Handle malformed data gracefully

- [ ] **Presentation**
  - [ ] Use Rich for terminal-native UX
  - [ ] Handle both JSON and text formats (if applicable)
  - [ ] Preserve shuffled state on retry

- [ ] **Input Capture**
  - [ ] Detect "I don't know" inputs
  - [ ] Parse user response into structured format
  - [ ] Validate input before passing to `check()`

- [ ] **Answer Checking**
  - [ ] Implement correct/incorrect logic
  - [ ] Calculate partial credit (if applicable)
  - [ ] Generate clear, actionable feedback
  - [ ] Handle edge cases (empty input, malformed, etc.)

- [ ] **Hints**
  - [ ] Implement progressive hint escalation
  - [ ] Tailor hints to user's previous attempt
  - [ ] Stop hints at threshold (2-3 attempts)

- [ ] **Testing**
  - [ ] Unit tests for validation
  - [ ] Unit tests for correct/incorrect answers
  - [ ] Unit tests for partial credit calculation
  - [ ] Unit tests for hint progression

- [ ] **Documentation**
  - [ ] Add handler to this reference doc
  - [ ] Include data format examples
  - [ ] Document special features
  - [ ] Note any LLM dependencies

---

## See Also

- [Learning Atoms Taxonomy](learning-atoms.md) - Complete atom type catalog
- [Architecture Overview](../explanation/architecture.md) - System design
- [Cognitive Diagnosis](../explanation/cognitive-diagnosis.md) - Error analysis
- [Adaptive Learning](../explanation/adaptive-learning.md) - Content selection
- [TUI Design](../explanation/tui-design.md) - Terminal interface patterns
- [Greenlight Integration](../explanation/greenlight-integration.md) - Runtime-dependent atoms
