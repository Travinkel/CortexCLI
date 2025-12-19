"""
Vertex AI Tutor for Cortex.

Implements Socratic remediation using Google's Gemini model via Vertex AI.
The tutor adapts to the learner's cognitive profile and provides personalized
explanations based on the diagnosed failure mode.

Key Features:
- Socratic questioning (guides to answer, doesn't just give it)
- Scaffolding with fade (hints that progressively reduce)
- Cognitive offloading prevention (penalizes over-reliance on hints)
- Multi-modal explanations (text, LaTeX, visual descriptions)
- Learner persona injection (personalized communication style)

Architecture:
- Multi-agent design: Strategist, Designer, Coach
- Strategist: Selects remediation approach
- Designer: Creates learning materials
- Coach: Delivers Socratic dialogue

Based on research from:
- Collins et al. (1989): Cognitive Apprenticeship
- VanLehn (2011): The Relative Effectiveness of Human Tutoring
- Kalyuga (2007): Expertise Reversal Effect
- Hmelo-Silver et al. (2007): Scaffolding and Achievement

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

# Import from our modules
from src.adaptive.neuro_model import (
    CognitiveDiagnosis,
    FailMode,
)
from src.adaptive.persona_service import LearnerPersona, PersonaService

# Try to import Vertex AI
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel

    HAS_VERTEX = True
except ImportError:
    HAS_VERTEX = False
    logger.warning("Vertex AI not available - using mock tutor")

# Try to import Google Generative AI (alternative)
try:
    import google.generativeai as genai

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default model configuration
DEFAULT_MODEL = "gemini-1.5-pro"
FALLBACK_MODEL = "gemini-1.5-flash"

# Vertex AI configuration
VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "cortex-learning")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")

# API key for google.generativeai (alternative to Vertex)
GENAI_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# Tutor parameters
MAX_HINT_DEPTH = 3  # Maximum hints before giving answer
SCAFFOLDING_FADE_RATE = 0.3  # How quickly scaffolding reduces
MIN_STRUGGLE_TIME_SEC = 30  # Minimum time before hint (prevents offloading)


# =============================================================================
# ENUMERATIONS
# =============================================================================


class TutorMode(str, Enum):
    """Tutoring mode based on diagnosis."""

    SOCRATIC = "socratic"  # Guide with questions
    ELABORATIVE = "elaborative"  # Explain differently
    CONTRASTIVE = "contrastive"  # Compare/contrast
    PROCEDURAL = "procedural"  # Step-by-step walkthrough
    MOTIVATIONAL = "motivational"  # Encouragement/break suggestion


class ScaffoldLevel(str, Enum):
    """Level of scaffolding support."""

    NONE = "none"  # No hints, raw challenge
    MINIMAL = "minimal"  # Subtle nudge
    MODERATE = "moderate"  # Clear hint
    HEAVY = "heavy"  # Detailed guidance
    FULL = "full"  # Complete explanation


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class TutorResponse:
    """Response from the AI tutor."""

    content: str
    mode: TutorMode
    scaffold_level: ScaffoldLevel
    follow_up_question: str | None = None
    latex_content: str | None = None
    visual_description: str | None = None
    suggested_action: str | None = None
    hint_depth: int = 0
    tokens_used: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "mode": self.mode.value,
            "scaffold_level": self.scaffold_level.value,
            "follow_up_question": self.follow_up_question,
            "latex_content": self.latex_content,
            "visual_description": self.visual_description,
            "suggested_action": self.suggested_action,
            "hint_depth": self.hint_depth,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }


@dataclass
class TutorSession:
    """Tracks state for a tutoring session on a single atom."""

    atom_id: str
    atom_content: dict[str, Any]
    diagnosis: CognitiveDiagnosis
    learner_persona: LearnerPersona

    # Session state
    hint_depth: int = 0
    scaffold_level: ScaffoldLevel = ScaffoldLevel.MINIMAL
    time_struggling_sec: float = 0.0
    hints_given: list[str] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)

    # Metrics
    started_at: datetime | None = None
    resolved: bool = False
    resolution_type: str = ""  # "self_solved", "hint_solved", "gave_up", "answer_shown"


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

SYSTEM_PROMPT = """You are a Socratic tutor for advanced mathematics, specializing in rigorous texts like Spivak's Calculus. Your goal is to guide the learner to understanding, NOT to give answers directly.

CORE PRINCIPLES:
1. NEVER give the answer directly unless explicitly instructed
2. Ask probing questions that lead the learner to discover the answer
3. Use the learner's cognitive profile to adapt your communication style
4. Provide scaffolding that fades over time
5. Celebrate productive struggle - it's where learning happens

{learner_context}

CURRENT TASK:
You are helping with a concept the learner struggled with.
Diagnosis: {diagnosis}
Remediation Type: {remediation_type}

SCAFFOLDING LEVEL: {scaffold_level}
- NONE: Raw challenge, no hints
- MINIMAL: Subtle nudge in right direction
- MODERATE: Clear hint about approach
- HEAVY: Detailed guidance with partial solution
- FULL: Complete explanation (last resort only)

RESPONSE FORMAT:
1. Acknowledge the struggle (briefly, empathetically)
2. {mode_specific_instruction}
3. End with a question or action prompt (unless FULL scaffolding)
4. If mathematical content, include LaTeX in $...$ or $$...$$
5. If you detect the user has solved the problem, start your response with "BREAKTHROUGH:"

Keep responses concise but complete. Under 200 words unless explaining a complex proof."""

MODE_INSTRUCTIONS = {
    TutorMode.SOCRATIC: "Ask 1-2 Socratic questions that guide toward the insight without revealing the answer",
    TutorMode.ELABORATIVE: "Explain the concept using a different analogy or approach than the original material",
    TutorMode.CONTRASTIVE: "Create a comparison showing how this concept differs from commonly confused alternatives",
    TutorMode.PROCEDURAL: "Walk through the first step of the solution, then ask what comes next",
    TutorMode.MOTIVATIONAL: "Acknowledge fatigue, suggest a break, and provide encouragement for return",
}


FAIL_MODE_PROMPTS = {
    FailMode.ENCODING_ERROR: """
The learner failed to encode this concept (hippocampal encoding failure).
This means the memory trace was never properly formed.

Strategy: Use elaboration - connect to existing knowledge, use vivid analogies,
create multiple retrieval pathways.

Key question to guide them: "What does this remind you of?" or "Can you explain
this in your own words?"
""",
    FailMode.RETRIEVAL_ERROR: """
The learner knows this but couldn't retrieve it (normal forgetting).
The memory exists but the retrieval pathway is weak.

Strategy: Provide retrieval cues, not answers. Ask leading questions that
activate related knowledge.

Key question: "What do you remember about the context when you learned this?"
""",
    FailMode.DISCRIMINATION_ERROR: """
The learner is confusing this with a similar concept (pattern separation failure).
The hippocampal dentate gyrus isn't distinguishing between overlapping representations.

Strategy: Contrastive analysis - explicitly compare the confused concepts.
Create a "discrimination matrix" showing key differences.

Key question: "What makes this DIFFERENT from [confused concept]?"
""",
    FailMode.INTEGRATION_ERROR: """
The learner knows the pieces but can't connect them (P-FIT integration failure).
Facts exist in isolation, not as a connected network.

Strategy: Worked examples with explicit reasoning steps. Show HOW facts connect,
not just THAT they connect.

Key question: "Given that X is true, what must follow?"
""",
    FailMode.EXECUTIVE_ERROR: """
The learner answered impulsively without careful reading (PFC executive failure).
They likely KNOW the answer but didn't engage System 2 thinking.

Strategy: Enforce deliberation. Ask them to re-read and identify key details
before answering.

Key action: "Read the question again. What is the KEY word that changes everything?"
""",
    FailMode.FATIGUE_ERROR: """
The learner is cognitively exhausted (resource depletion).
No amount of explanation will help right now.

Strategy: Suggest break, validate the struggle, provide motivation to return.
DO NOT attempt to teach - it will be wasted effort.

Key message: "Your brain needs rest. Take a 10-minute break. You've earned it."
""",
}


# =============================================================================
# VERTEX AI TUTOR
# =============================================================================


class VertexTutor:
    """
    AI Tutor using Google Vertex AI (Gemini).

    Provides personalized Socratic tutoring based on cognitive diagnosis
    and learner persona.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        project: str = VERTEX_PROJECT,
        location: str = VERTEX_LOCATION,
    ):
        """Initialize the tutor with Vertex AI."""
        self.model_name = model_name
        self.project = project
        self.location = location
        self.model: GenerativeModel | None = None
        self._initialized = False

        # Track offloading
        self._hint_requests: list[datetime] = []
        self._offloading_penalty: float = 0.0

    def initialize(self) -> bool:
        """Initialize Vertex AI connection."""
        if self._initialized:
            return True

        # Try Vertex AI first
        if HAS_VERTEX:
            try:
                vertexai.init(project=self.project, location=self.location)
                self.model = GenerativeModel(self.model_name)
                self._initialized = True
                logger.info(f"Vertex AI initialized with model {self.model_name}")
                return True
            except Exception as e:
                logger.warning(f"Vertex AI init failed: {e}")

        # Try google.generativeai as fallback
        if HAS_GENAI and GENAI_API_KEY:
            try:
                genai.configure(api_key=GENAI_API_KEY)
                self.model = genai.GenerativeModel(self.model_name)
                self._initialized = True
                logger.info(f"Google GenAI initialized with model {self.model_name}")
                return True
            except Exception as e:
                logger.warning(f"Google GenAI init failed: {e}")

        logger.error("No AI backend available - tutor will use mock responses")
        return False

    def _determine_mode(self, diagnosis: CognitiveDiagnosis) -> TutorMode:
        """Determine tutoring mode based on diagnosis."""
        if diagnosis.fail_mode == FailMode.FATIGUE_ERROR:
            return TutorMode.MOTIVATIONAL

        if diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR:
            return TutorMode.CONTRASTIVE

        if diagnosis.fail_mode == FailMode.INTEGRATION_ERROR:
            return TutorMode.PROCEDURAL

        if diagnosis.fail_mode == FailMode.ENCODING_ERROR:
            return TutorMode.ELABORATIVE

        # Default to Socratic for retrieval and executive errors
        return TutorMode.SOCRATIC

    def _determine_scaffold_level(
        self,
        session: TutorSession,
        time_since_last_hint: float,
    ) -> ScaffoldLevel:
        """
        Determine scaffolding level based on struggle time and hint history.

        Implements the "Productive Struggle" protocol - scaffolding fades
        over time but increases if struggling too long.
        """
        # Check for cognitive offloading (asking for hints too quickly)
        if time_since_last_hint < MIN_STRUGGLE_TIME_SEC and session.hint_depth > 0:
            self._offloading_penalty += 0.1
            logger.warning(
                f"Potential cognitive offloading detected. Penalty: {self._offloading_penalty:.1f}"
            )
            # Don't increase scaffolding - make them struggle
            return ScaffoldLevel.MINIMAL

        # Progressive scaffolding based on hint depth
        if session.hint_depth == 0:
            return ScaffoldLevel.MINIMAL
        elif session.hint_depth == 1:
            return ScaffoldLevel.MODERATE
        elif session.hint_depth == 2:
            return ScaffoldLevel.HEAVY
        else:
            return ScaffoldLevel.FULL

    def _build_prompt(
        self,
        session: TutorSession,
        user_message: str,
        mode: TutorMode,
        scaffold_level: ScaffoldLevel,
    ) -> str:
        """Build the complete prompt for the AI."""
        # Get learner context
        learner_context = session.learner_persona.to_prompt_context()

        # Get fail mode specific guidance
        fail_mode_guidance = ""
        if session.diagnosis.fail_mode:
            fail_mode_guidance = FAIL_MODE_PROMPTS.get(session.diagnosis.fail_mode, "")

        # Build system prompt
        system = SYSTEM_PROMPT.format(
            learner_context=learner_context,
            diagnosis=session.diagnosis.fail_mode.value
            if session.diagnosis.fail_mode
            else "unknown",
            remediation_type=session.diagnosis.remediation_type.value,
            scaffold_level=scaffold_level.value,
            mode_specific_instruction=MODE_INSTRUCTIONS.get(mode, "Guide the learner"),
        )

        # Build content prompt
        atom = session.atom_content
        content_prompt = f"""
{fail_mode_guidance}

CONTENT:
Question: {atom.get("front", "Unknown question")}
Correct Answer: {atom.get("back", "Unknown answer")}
Concept: {atom.get("concept_name", "Unknown concept")}
Source: {atom.get("source_fact_basis", "Unknown source")}

CONVERSATION HISTORY:
{self._format_history(session.conversation_history)}

LEARNER'S MESSAGE:
{user_message}

CURRENT HINT DEPTH: {session.hint_depth}/{MAX_HINT_DEPTH}

Provide your response following the scaffolding level and mode guidelines.
"""

        return f"{system}\n\n{content_prompt}"

    def _format_history(self, history: list[dict]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "(No previous conversation)"

        lines = []
        for msg in history[-5:]:  # Last 5 exchanges
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]  # Truncate long messages
            lines.append(f"{role.upper()}: {content}")

        return "\n".join(lines)

    async def get_response(
        self,
        session: TutorSession,
        user_message: str,
        time_since_last_hint: float = 60.0,
    ) -> TutorResponse:
        """
        Get a tutoring response.

        Args:
            session: The current tutoring session
            user_message: The learner's message or question
            time_since_last_hint: Seconds since last hint (for offloading detection)

        Returns:
            TutorResponse with content and metadata
        """
        start_time = time.time()

        # Determine mode and scaffolding
        mode = self._determine_mode(session.diagnosis)
        scaffold_level = self._determine_scaffold_level(session, time_since_last_hint)

        # Build prompt
        prompt = self._build_prompt(session, user_message, mode, scaffold_level)

        # Get AI response
        if self._initialized and self.model:
            try:
                response_text = await self._call_model(prompt)
            except Exception as e:
                logger.error(f"Model call failed: {e}")
                response_text = self._get_mock_response(session, mode, scaffold_level)
        else:
            response_text = self._get_mock_response(session, mode, scaffold_level)

        # Check for breakthrough
        if response_text.strip().startswith("BREAKTHROUGH:"):
            session.resolved = True
            session.resolution_type = "self_solved"
            response_text = response_text.replace("BREAKTHROUGH:", "").strip()

        # Parse response for LaTeX and follow-up questions
        latex_content = self._extract_latex(response_text)
        follow_up = self._extract_follow_up(response_text)

        # Update session
        session.hint_depth += 1
        session.hints_given.append(response_text[:100])
        session.conversation_history.append(
            {
                "role": "learner",
                "content": user_message,
            }
        )
        session.conversation_history.append(
            {
                "role": "tutor",
                "content": response_text,
            }
        )

        latency = int((time.time() - start_time) * 1000)

        return TutorResponse(
            content=response_text,
            mode=mode,
            scaffold_level=scaffold_level,
            follow_up_question=follow_up,
            latex_content=latex_content,
            hint_depth=session.hint_depth,
            latency_ms=latency,
        )

    async def _call_model(self, prompt: str) -> str:
        """Call the AI model and get response."""
        if HAS_VERTEX and isinstance(self.model, GenerativeModel) or HAS_GENAI:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text

        return "I'm having trouble connecting to the AI service."

    def _get_mock_response(
        self,
        session: TutorSession,
        mode: TutorMode,
        scaffold_level: ScaffoldLevel,
    ) -> str:
        """Generate a mock response when AI is unavailable."""
        atom = session.atom_content
        concept = atom.get("concept_name", "this concept")

        if mode == TutorMode.MOTIVATIONAL:
            return (
                "I can see you've been working hard. Your brain needs rest to "
                "consolidate what you've learned. Take a 10-minute break - "
                "grab some water, stretch, or take a short walk. "
                "You've earned it, and you'll come back sharper."
            )

        if mode == TutorMode.CONTRASTIVE:
            return (
                f"Let's look at this differently. {concept} is often confused "
                f"with similar concepts. What makes it UNIQUE? What's the "
                f"one feature that distinguishes it from everything else?"
            )

        if mode == TutorMode.PROCEDURAL:
            return (
                "Let's break this down step by step. What's the FIRST thing "
                "you need to identify before you can solve this? "
                "Don't think about the whole problem - just the first step."
            )

        if mode == TutorMode.ELABORATIVE:
            return (
                f"Let me explain {concept} a different way. Think of it like "
                f"this: [the tutor would provide an analogy here]. "
                f"Does that help? What part is still unclear?"
            )

        # Socratic default
        return (
            f"Good question. Before I help further, let me ask: "
            f"What do you already know about {concept}? "
            f"What's the part that's confusing you most?"
        )

    def _extract_latex(self, text: str) -> str | None:
        """Extract LaTeX content from response."""
        import re

        # Find $...$ or $$...$$ patterns
        patterns = re.findall(r"\$\$([^$]+)\$\$|\$([^$]+)\$", text)
        if patterns:
            # Return first substantial match
            for match in patterns:
                content = match[0] or match[1]
                if len(content) > 5:
                    return content
        return None

    def _extract_follow_up(self, text: str) -> str | None:
        """Extract follow-up question from response."""
        # Look for sentences ending with ?
        import re

        questions = re.findall(r"[^.!?]*\?", text)
        if questions:
            return questions[-1].strip()  # Return last question
        return None

    def create_session(
        self,
        atom: dict[str, Any],
        diagnosis: CognitiveDiagnosis,
        persona: LearnerPersona | None = None,
    ) -> TutorSession:
        """Create a new tutoring session for an atom."""
        if persona is None:
            service = PersonaService()
            persona = service.get_persona()

        return TutorSession(
            atom_id=str(atom.get("id", "unknown")),
            atom_content=atom,
            diagnosis=diagnosis,
            learner_persona=persona,
            started_at=datetime.now(),
        )

    def get_offloading_penalty(self) -> float:
        """Get the current cognitive offloading penalty."""
        return self._offloading_penalty

    def reset_offloading_penalty(self) -> None:
        """Reset the offloading penalty (e.g., after a break)."""
        self._offloading_penalty = 0.0


# =============================================================================
# MULTI-AGENT ARCHITECTURE
# =============================================================================


class TutorStrategist:
    """
    Strategist agent that determines the optimal tutoring approach.

    Considers:
    - Cognitive diagnosis
    - Learner persona
    - Historical effectiveness of different strategies
    """

    def select_strategy(
        self,
        diagnosis: CognitiveDiagnosis,
        persona: LearnerPersona,
        atom: dict[str, Any],
    ) -> dict[str, Any]:
        """Select the optimal tutoring strategy."""
        strategy = {
            "mode": TutorMode.SOCRATIC,
            "initial_scaffold": ScaffoldLevel.MINIMAL,
            "max_hints": MAX_HINT_DEPTH,
            "use_visual": False,
            "use_latex": True,
            "emphasis": "understanding",
        }

        # Adjust based on diagnosis
        if diagnosis.fail_mode == FailMode.FATIGUE_ERROR:
            strategy["mode"] = TutorMode.MOTIVATIONAL
            strategy["max_hints"] = 1
            strategy["emphasis"] = "rest"

        elif diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR:
            strategy["mode"] = TutorMode.CONTRASTIVE
            strategy["emphasis"] = "distinction"
            strategy["use_visual"] = True

        elif diagnosis.fail_mode == FailMode.INTEGRATION_ERROR:
            strategy["mode"] = TutorMode.PROCEDURAL
            strategy["emphasis"] = "connection"
            strategy["initial_scaffold"] = ScaffoldLevel.MODERATE

        elif diagnosis.fail_mode == FailMode.ENCODING_ERROR:
            strategy["mode"] = TutorMode.ELABORATIVE
            strategy["emphasis"] = "encoding"

        # Adjust based on persona
        if persona.preferred_modality == "visual":
            strategy["use_visual"] = True

        if persona.strength_conceptual < 0.4:
            strategy["initial_scaffold"] = ScaffoldLevel.MODERATE
            strategy["emphasis"] = "concrete_examples"

        if persona.calibration_score > 0.65:
            # Overconfident - use more Socratic questioning
            strategy["mode"] = TutorMode.SOCRATIC
            strategy["initial_scaffold"] = ScaffoldLevel.MINIMAL

        return strategy


class TutorCoach:
    """
    Coach agent that delivers the actual tutoring dialogue.

    Focuses on:
    - Socratic questioning
    - Scaffolding delivery
    - Emotional support
    """

    def __init__(self, vertex_tutor: VertexTutor):
        self.tutor = vertex_tutor

    async def deliver_guidance(
        self,
        session: TutorSession,
        user_input: str,
        strategy: dict[str, Any],
    ) -> TutorResponse:
        """Deliver guidance based on strategy."""
        return await self.tutor.get_response(
            session=session,
            user_message=user_input,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global tutor instance
_tutor: VertexTutor | None = None


def get_tutor() -> VertexTutor:
    """Get or create the global tutor instance."""
    global _tutor
    if _tutor is None:
        _tutor = VertexTutor()
        _tutor.initialize()
    return _tutor


async def get_help(
    atom: dict[str, Any],
    diagnosis: CognitiveDiagnosis,
    user_message: str = "I don't understand this.",
    persona: LearnerPersona | None = None,
) -> TutorResponse:
    """
    Quick helper to get tutoring help for an atom.

    Args:
        atom: The atom the learner is struggling with
        diagnosis: The cognitive diagnosis
        user_message: What the learner is asking
        persona: Optional learner persona (will load default if None)

    Returns:
        TutorResponse with guidance
    """
    tutor = get_tutor()
    session = tutor.create_session(atom, diagnosis, persona)
    return await tutor.get_response(session, user_message)


def get_quick_hint(
    atom: dict[str, Any],
    fail_mode: FailMode,
) -> str:
    """
    Get a quick hint without full AI call.

    Useful for synchronous contexts or when AI is unavailable.
    """
    concept = atom.get("concept_name", "this concept")
    atom.get("front", "")

    hints = {
        FailMode.ENCODING_ERROR: (
            f"Let's strengthen the memory trace. Can you explain {concept} "
            f"in your own words, without looking at the answer?"
        ),
        FailMode.RETRIEVAL_ERROR: (
            "The memory is there, but the pathway is weak. "
            "What context do you remember learning this in?"
        ),
        FailMode.DISCRIMINATION_ERROR: (
            f"You might be confusing this with something similar. "
            f"What makes {concept} UNIQUE compared to related concepts?"
        ),
        FailMode.INTEGRATION_ERROR: (
            "The pieces aren't connecting. What's the FIRST fact you need "
            "to know before you can figure out the rest?"
        ),
        FailMode.EXECUTIVE_ERROR: (
            "Take a breath. Re-read the question slowly. "
            "What's the KEY word that tells you what to do?"
        ),
        FailMode.FATIGUE_ERROR: (
            "Your brain is tired. Take a 10-minute break. You'll come back sharper."
        ),
    }

    return hints.get(fail_mode, f"Think about what you know about {concept}.")
