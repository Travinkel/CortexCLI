"""
Socratic Dialogue Engine: Interactive tutoring when learner says "don't know".

Guides learners through knowledge construction via:
- Progressive Socratic questioning
- Scaffolded hints that escalate if stuck
- Cognitive signal detection
- Prerequisite gap identification
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from loguru import logger


class ScaffoldLevel(int, Enum):
    """Progressive scaffolding levels."""
    PURE_SOCRATIC = 0   # Questions only, no hints
    NUDGE = 1           # Conceptual nudge ("Think about...")
    PARTIAL = 2         # Partial reveal ("The answer involves...")
    WORKED = 3          # Worked example with gaps
    REVEAL = 4          # Full answer with explanation


class CognitiveSignal(str, Enum):
    """Detected learner signals during dialogue."""
    CONFUSED = "confused"           # "I don't understand", long latency
    PROGRESSING = "progressing"     # Building on previous response
    BREAKTHROUGH = "breakthrough"   # Sudden correct insight
    STUCK = "stuck"                 # Repeated "don't know"
    PREREQUISITE_GAP = "gap"        # Missing foundational knowledge
    FATIGUE = "fatigue"             # Decreasing quality


class Resolution(str, Enum):
    """How the Socratic session ended."""
    SELF_SOLVED = "self_solved"       # Learner figured it out
    GUIDED_SOLVED = "guided_solved"   # Solved with tutor help
    GAVE_UP = "gave_up"               # Learner requested skip
    REVEALED = "revealed"             # Full answer was shown


@dataclass
class DialogueTurn:
    """A single exchange in the Socratic dialogue."""
    role: Literal["tutor", "learner"]
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    latency_ms: int | None = None
    signal: CognitiveSignal | None = None


@dataclass
class SocraticSession:
    """State of an ongoing Socratic tutoring session."""
    atom_id: str
    atom_content: dict  # front, back, atom_type
    turns: list[DialogueTurn] = field(default_factory=list)
    scaffold_level: ScaffoldLevel = ScaffoldLevel.PURE_SOCRATIC
    detected_gaps: list[str] = field(default_factory=list)
    resolution: Resolution | None = None
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def duration_ms(self) -> int:
        if self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return int((datetime.now() - self.started_at).total_seconds() * 1000)

    def add_tutor_turn(self, content: str) -> None:
        self.turns.append(DialogueTurn(role="tutor", content=content))

    def add_learner_turn(self, content: str, latency_ms: int, signal: CognitiveSignal | None = None) -> None:
        self.turns.append(DialogueTurn(
            role="learner",
            content=content,
            latency_ms=latency_ms,
            signal=signal
        ))

    def get_dialogue_history(self) -> str:
        """Format dialogue history for LLM context."""
        lines = []
        for turn in self.turns:
            prefix = "Tutor" if turn.role == "tutor" else "Learner"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)


# =============================================================================
# Prompts
# =============================================================================

SOCRATIC_SYSTEM_PROMPT = """You are a Socratic tutor. Your goal is to guide the learner
toward understanding through questions, NOT by giving answers directly.

## Rules
1. NEVER reveal the answer directly (unless scaffold_level >= 4)
2. Ask ONE focused question at a time
3. Build on what the learner already knows
4. If they're stuck, simplify your question
5. Celebrate small insights with brief encouragement

## Question Types
- Clarifying: "What do you already know about X?"
- Connecting: "How does X relate to Y?"
- Decomposing: "Let's break this down. What's the first step?"
- Hypothetical: "What would happen if...?"
- Contrastive: "How is X different from Y?"

## Scaffold Levels
Level 0: Pure Socratic questions only
Level 1: Include a conceptual nudge ("Think about the relationship between...")
Level 2: Partial reveal ("The answer involves...")
Level 3: Worked example with gaps ("Step 1 is X, what's step 2?")
Level 4: Full explanation (only when truly stuck)

## Learner Context
{learner_context}

Current scaffold level: {scaffold_level}/4
"""

SOCRATIC_USER_PROMPT = """
QUESTION: {front}
CORRECT ANSWER: {back}
ATOM TYPE: {atom_type}

DIALOGUE SO FAR:
{dialogue_history}

LAST LEARNER RESPONSE: {last_response}

Generate your next Socratic question. Keep it to 1-2 sentences.
If scaffold_level >= 2, you may include a hint.
If scaffold_level >= 4, provide the full explanation.
"""

GAP_DETECTION_PROMPT = """Analyze this learning dialogue to identify prerequisite knowledge gaps.

DIALOGUE:
{dialogue_history}

CURRENT TOPIC: {topic}
QUESTION: {front}

Based on the learner's responses, which foundational concepts seem to be missing or confused?
Focus on prerequisite knowledge that would help them understand this topic.

Return a JSON object:
{{"gaps": ["concept1", "concept2"], "evidence": ["quote or observation 1", "quote 2"]}}

If no gaps detected, return: {{"gaps": [], "evidence": []}}
"""


# =============================================================================
# Socratic Tutor Engine
# =============================================================================

class SocraticTutor:
    """
    Manages Socratic tutoring dialogues.

    Triggered when learner says "don't know", guides them through
    knowledge construction with progressive scaffolding.
    """

    # ==========================================================================
    # COGNITIVE SIGNAL PATTERNS (re.VERBOSE for readability)
    # ==========================================================================

    # Patterns indicating confusion
    CONFUSION_PATTERNS = [
        re.compile(r"""
            i \s+ don'?t \s+ understand
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            i'?m \s+ confused
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            what \s+ do \s+ you \s+ mean
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            i \s+ don'?t \s+ know
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            no \s+ idea
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            \b lost \b
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            \?\?+                           # Multiple question marks
        """, re.VERBOSE),
    ]

    # Patterns indicating progress (including near-correct responses)
    PROGRESS_PATTERNS = [
        re.compile(r"""
            oh ,? \s* i \s+ see
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            so \s+ it'?s
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            that \s+ means
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            \b because \b
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            right ,? \s* so
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            got \s+ it
        """, re.VERBOSE | re.IGNORECASE),

        # Near-correct answer patterns
        re.compile(r"""
            \d+                             # Number (e.g., 192)
            \s*                             # Optional whitespace
            (?: is | equals? | gives? )     # Linking verb
            \s*
            (?: the \s* )?                  # Optional "the"
            (?: answer )?                   # Optional "answer"
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            (?: so \s+ )?                   # Optional "so"
            the \s+ answer \s+
            (?: is | would \s+ be )         # "is" or "would be"
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            \d+                             # First operand
            \s* [+\-*/] \s*                 # Operator
            \d+                             # Second operand
            \s* =                           # Equals sign
        """, re.VERBOSE),

        re.compile(r"""
            (?: i \s+ )?                    # Optional "i"
            (?: think | believe | guess )   # Cognitive verb
            \s+
            (?: it'?s | the \s+ answer \s+ is )
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            (?: wait | hold \s+ on )        # Pause phrase
            .*                              # Anything
            (?: so | then )                 # Conclusion
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            let \s+ me \s+
            (?: try | think | work )        # Action verb
        """, re.VERBOSE | re.IGNORECASE),
    ]

    # Patterns for extracting numeric answers from natural language
    NUMERIC_ANSWER_PATTERNS = [
        re.compile(r"""
            (\d+)                           # Capture the number
            \s*                             # Optional whitespace
            (?: is | equals? | gives? | = ) # Linking verb
            \s*
            (?: the \s* )?                  # Optional "the"
            (?: answer | result | it )      # What it equals
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            (?: so \s+ )?                   # Optional "so"
            (?: it'?s | the \s+ answer \s+ is | i \s+ get )
            \s+
            (\d+)                           # Capture the number
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            (\d+)                           # First operand
            \s* [+\-*/] \s*                 # Operator
            \d+                             # Second operand
            \s* = \s*
            (\d+)                           # Capture the result
        """, re.VERBOSE),

        re.compile(r"""
            answer                          # The word "answer"
            [:\s]+                          # Colon or whitespace
            (\d+)                           # Capture the number
        """, re.VERBOSE | re.IGNORECASE),

        re.compile(r"""
            (\d+)                           # Capture the number
            (?: \s* $ | \s* \. )            # At end of string or before period
        """, re.VERBOSE),
    ]

    # Stuck threshold
    STUCK_THRESHOLD = 3  # Consecutive "don't know" before escalating

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
        learner_context: str = "",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.learner_context = learner_context
        self._client = None

        if not self.api_key:
            logger.warning("No Gemini API key - Socratic tutor will use fallback mode")

    @property
    def is_available(self) -> bool:
        return self.api_key is not None

    def start_session(self, atom: dict) -> SocraticSession:
        """Initialize a new Socratic dialogue session."""
        session = SocraticSession(
            atom_id=str(atom.get("id", atom.get("card_id", "unknown"))),
            atom_content={
                "front": atom.get("front", ""),
                "back": atom.get("back", ""),
                "atom_type": atom.get("atom_type", "flashcard"),
            }
        )

        # Generate opening question
        opening = self._generate_opening_question(session)
        session.add_tutor_turn(opening)

        return session

    def process_response(
        self,
        session: SocraticSession,
        response: str,
        latency_ms: int
    ) -> tuple[str | None, bool]:
        """
        Process learner response and generate next question.

        Returns:
            (next_question, is_resolved) - Question to ask, or None if dialogue should end
        """
        # Detect cognitive signals
        signal = self._detect_signal(response, latency_ms, session)
        session.add_learner_turn(response, latency_ms, signal)

        # Check for skip/give up
        if self._is_skip_request(response):
            session.resolution = Resolution.GAVE_UP
            session.ended_at = datetime.now()
            return None, True

        # Check if they've solved it
        if self._check_answer_correct(response, session):
            session.resolution = self._determine_resolution(session)
            session.ended_at = datetime.now()
            return self._generate_celebration(session), True

        # Check if should escalate scaffolding
        if signal == CognitiveSignal.STUCK or signal == CognitiveSignal.CONFUSED:
            session.scaffold_level = ScaffoldLevel(
                min(session.scaffold_level.value + 1, ScaffoldLevel.REVEAL.value)
            )

        # At max scaffold, reveal answer
        if session.scaffold_level == ScaffoldLevel.REVEAL:
            session.resolution = Resolution.REVEALED
            session.ended_at = datetime.now()
            return self._generate_full_explanation(session), True

        # Generate next Socratic question
        next_question = self._generate_question(session)
        session.add_tutor_turn(next_question)

        return next_question, False

    def detect_prerequisite_gaps(self, session: SocraticSession) -> list[str]:
        """Analyze dialogue for missing foundational knowledge."""
        if not self.is_available or session.turn_count < 2:
            return []

        try:
            import google.generativeai as genai

            if self._client is None:
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(model_name=self.model_name)

            prompt = GAP_DETECTION_PROMPT.format(
                dialogue_history=session.get_dialogue_history(),
                topic=session.atom_content.get("atom_type", "unknown"),
                front=session.atom_content.get("front", ""),
            )

            response = self._client.generate_content(prompt)
            text = response.text.strip()

            # Extract JSON from response
            if "{" in text:
                json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return data.get("gaps", [])

            return []

        except Exception as e:
            logger.error(f"Gap detection failed: {e}")
            return []

    def _generate_opening_question(self, session: SocraticSession) -> str:
        """Generate the first Socratic question."""
        front = session.atom_content.get("front", "")
        atom_type = session.atom_content.get("atom_type", "flashcard")

        # Fallback opening questions by type
        type_openers = {
            "numeric": f"Let's work through this step by step. Looking at '{front[:100]}...', what's the first piece of information we need to identify?",
            "mcq": f"Before we look at the options, what do you already know about {self._extract_topic(front)}?",
            "parsons": "Let's think about the order. What would be the very first step you'd take?",
            "true_false": "What's your intuition about this statement? What part makes you uncertain?",
            "cloze": "What context clues in the sentence might help you fill in the blank?",
            "flashcard": f"What do you already know about {self._extract_topic(front)}?",
        }

        fallback = type_openers.get(atom_type, f"What comes to mind when you think about {self._extract_topic(front)}?")

        if not self.is_available:
            return fallback

        try:
            import google.generativeai as genai

            if self._client is None:
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SOCRATIC_SYSTEM_PROMPT.format(
                        learner_context=self.learner_context or "No specific context available.",
                        scaffold_level=session.scaffold_level.value
                    )
                )

            prompt = f"""The learner said "I don't know" to this question:

QUESTION: {front}
ATOM TYPE: {atom_type}

Generate your opening Socratic question to help them start thinking about it.
Keep it to 1-2 sentences. Start with what they might already know."""

            response = self._client.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Opening question generation failed: {e}")
            return fallback

    def _generate_question(self, session: SocraticSession) -> str:
        """Generate the next Socratic question based on dialogue."""
        if not self.is_available:
            return self._fallback_question(session)

        try:
            import google.generativeai as genai

            if self._client is None:
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SOCRATIC_SYSTEM_PROMPT.format(
                        learner_context=self.learner_context or "No specific context available.",
                        scaffold_level=session.scaffold_level.value
                    )
                )

            # Get last learner response
            last_learner = ""
            for turn in reversed(session.turns):
                if turn.role == "learner":
                    last_learner = turn.content
                    break

            prompt = SOCRATIC_USER_PROMPT.format(
                front=session.atom_content.get("front", ""),
                back=session.atom_content.get("back", ""),
                atom_type=session.atom_content.get("atom_type", ""),
                dialogue_history=session.get_dialogue_history(),
                last_response=last_learner,
            )

            response = self._client.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return self._fallback_question(session)

    def _fallback_question(self, session: SocraticSession) -> str:
        """Generate fallback questions when LLM unavailable."""
        level = session.scaffold_level
        front = session.atom_content.get("front", "")
        back = session.atom_content.get("back", "")

        if level == ScaffoldLevel.PURE_SOCRATIC:
            return "Can you think of any related concepts that might help here?"
        elif level == ScaffoldLevel.NUDGE:
            topic = self._extract_topic(front)
            return f"Think about the core concept behind {topic}. What's the key principle?"
        elif level == ScaffoldLevel.PARTIAL:
            # Reveal first few words of answer
            hint = back[:min(30, len(back))] + "..."
            return f"The answer starts with: '{hint}'. Can you complete it?"
        elif level == ScaffoldLevel.WORKED:
            return f"Let me break it down: The answer is '{back}'. Can you explain why?"
        else:
            return back  # Full reveal

    def _generate_celebration(self, session: SocraticSession) -> str:
        """Generate a celebration that connects the learner's journey to the answer."""
        turn_count = session.turn_count
        back = session.atom_content.get("back", "")

        # Try to summarize the learner's correct steps
        learner_turns = [t for t in session.turns if t.role == "learner"]
        correct_steps = []

        for turn in learner_turns[-5:]:  # Check recent turns
            content = turn.content.lower()
            # Check if turn contained partial correct info
            back_terms = [w for w in re.findall(r'\b\w+\b', back.lower()) if len(w) > 3]
            for term in back_terms:
                if term in content and term not in str(correct_steps):
                    correct_steps.append(term)

        # Build personalized celebration
        if correct_steps:
            steps_str = ", ".join(correct_steps[:3])
            prefix = f"You were on the right track with: {steps_str}! "
        else:
            prefix = ""

        if turn_count <= 2:
            return prefix + "Excellent! You got there quickly with just a little guidance!"
        elif turn_count <= 4:
            return prefix + "Great work! You worked through it step by step."
        else:
            return prefix + "Well done for persisting! That's how real learning happens."

    def _generate_full_explanation(self, session: SocraticSession) -> str:
        """Generate full explanation when revealing answer."""
        back = session.atom_content.get("back", "")
        return f"Here's the answer: {back}\n\nLet me know if you'd like me to explain any part of it."

    def _detect_signal(
        self,
        response: str,
        latency_ms: int,
        session: SocraticSession
    ) -> CognitiveSignal | None:
        """Detect cognitive signal from learner response."""
        response_lower = response.lower().strip()

        # Check for confusion patterns (compiled regex objects)
        for pattern in self.CONFUSION_PATTERNS:
            if pattern.search(response_lower):
                return CognitiveSignal.CONFUSED

        # Check for progress patterns (compiled regex objects)
        for pattern in self.PROGRESS_PATTERNS:
            if pattern.search(response_lower):
                return CognitiveSignal.PROGRESSING

        # Check for stuck (repeated short responses or "don't know")
        recent_learner_turns = [
            t for t in session.turns[-self.STUCK_THRESHOLD*2:]
            if t.role == "learner"
        ]
        if len(recent_learner_turns) >= self.STUCK_THRESHOLD:
            short_responses = sum(1 for t in recent_learner_turns if len(t.content) < 20)
            if short_responses >= self.STUCK_THRESHOLD:
                return CognitiveSignal.STUCK

        # Check for very long latency (> 30 seconds)
        if latency_ms > 30000:
            return CognitiveSignal.CONFUSED

        return None

    def _check_answer_correct(self, response: str, session: SocraticSession) -> bool:
        """
        Check if learner's response contains the correct answer.

        Enhanced with:
        1. Numeric extraction ("192 is the answer" -> check for 192)
        2. Fuzzy matching for near-correct responses
        3. Pattern matching for answer declarations
        """
        back = session.atom_content.get("back", "")
        back_lower = back.lower()
        response_lower = response.lower()

        # 1. Extract and check numeric answers using class-level patterns
        # Patterns like: "192 is the answer", "so it's 192", "128 + 64 = 192"
        expected_numbers = re.findall(r'\b(\d+)\b', back_lower)

        for pattern in self.NUMERIC_ANSWER_PATTERNS:
            matches = pattern.findall(response_lower)
            if matches:
                # Flatten matches (some patterns have groups)
                found_numbers = []
                for m in matches:
                    if isinstance(m, tuple):
                        found_numbers.extend(m)
                    else:
                        found_numbers.append(m)

                # Check if any found number matches expected
                for num in found_numbers:
                    if num in expected_numbers:
                        return True

        # Handle JSON back (MCQ, etc.)
        try:
            back_data = json.loads(back)
            if isinstance(back_data, dict):
                # For MCQ, check if they mention the correct option
                if "options" in back_data:
                    correct_idx = back_data.get("correct")

                    # If correct is null or missing, we CANNOT validate the answer
                    # This prevents false positives when we don't know the right answer
                    if correct_idx is None:
                        # Check explanation if available - but be conservative
                        explanation = back_data.get("explanation", "")
                        if explanation:
                            # Only mark as correct if response is very close to explanation
                            exp_terms = [w for w in re.findall(r'\b\w+\b', explanation.lower()) if len(w) > 4]
                            if exp_terms:
                                matches = sum(1 for term in exp_terms if term in response_lower)
                                # Require 80% match for explanations (stricter)
                                if matches / len(exp_terms) > 0.8:
                                    return True
                        # Without a correct index, we cannot verify - return False
                        return False

                    if isinstance(correct_idx, int) and correct_idx < len(back_data["options"]):
                        correct_text = back_data["options"][correct_idx].lower()
                        # Check for substantial match, not just substring
                        correct_terms = [w for w in re.findall(r'\b\w+\b', correct_text) if len(w) > 3]
                        if correct_terms:
                            matches = sum(1 for term in correct_terms if term in response_lower)
                            if matches / len(correct_terms) > 0.7:
                                return True
                        # Fallback to substring for short answers
                        elif correct_text in response_lower or response_lower in correct_text:
                            return True

                    # Multiple correct indices (list)
                    if isinstance(correct_idx, list):
                        for idx in correct_idx:
                            if isinstance(idx, int) and idx < len(back_data["options"]):
                                correct_text = back_data["options"][idx].lower()
                                if correct_text in response_lower:
                                    return True

                    return False  # MCQ with options but no match

        except (json.JSONDecodeError, TypeError):
            pass

        # Simple substring match for non-JSON text answers
        # Extract key terms from back (words > 3 chars)
        key_terms = [w for w in re.findall(r'\b\w+\b', back_lower) if len(w) > 3]

        if key_terms:
            matches = sum(1 for term in key_terms if term in response_lower)
            # Require 80% of key terms for correct (stricter to prevent false positives)
            # Also require at least 3 terms matched or the full set for short answers
            min_required = max(3, int(len(key_terms) * 0.8))
            if matches >= min_required:
                return True

            # For very short answers (1-2 key terms), require exact match
            if len(key_terms) <= 2 and matches == len(key_terms):
                # Also check that response has meaningful content beyond the answer
                response_terms = [w for w in re.findall(r'\b\w+\b', response_lower) if len(w) > 3]
                if len(response_terms) >= len(key_terms):
                    return True

        return False

    def _is_skip_request(self, response: str) -> bool:
        """Check if learner wants to skip/give up."""
        skip_patterns = ["skip", "give up", "show answer", "reveal", "just tell me", "next"]
        response_lower = response.lower().strip()
        return any(p in response_lower for p in skip_patterns)

    def _determine_resolution(self, session: SocraticSession) -> Resolution:
        """Determine how the session was resolved."""
        if session.scaffold_level == ScaffoldLevel.PURE_SOCRATIC:
            return Resolution.SELF_SOLVED
        elif session.scaffold_level.value <= ScaffoldLevel.PARTIAL.value:
            return Resolution.GUIDED_SOLVED
        else:
            return Resolution.REVEALED

    def _extract_topic(self, text: str) -> str:
        """Extract a topic phrase from question text."""
        # Take first significant phrase
        text = re.sub(r'^(what|which|how|why|when|where|who|is|are|does|do)\s+', '', text.lower())
        words = text.split()[:5]
        return " ".join(words) if words else "this concept"
