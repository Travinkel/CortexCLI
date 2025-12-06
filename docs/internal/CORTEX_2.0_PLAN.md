# Cognitive Cortex 2.0: Implementation Plan

## Executive Summary

This plan transforms the existing Cortex CLI from a **Behaviorist Learning System** (stimulus-response flashcards) into a **Cognitive Augmentation System** that models and enhances the learner's brain.

### Core Innovations
1. **Neuro-Model**: Classifying errors by cognitive system (Hippocampus/P-FIT/PFC)
2. **Learner Persona**: A dynamic JSON profile that evolves with every interaction
3. **Intelligent Scheduling**: Bio-rhythmic study blocks based on chronotype
4. **Remediation Engine**: When flashcards fail, switch modalities
5. **Project Generation**: Auto-generate projects from weak concept clusters
6. **LLM Chat Integration**: Socratic tutoring with full context awareness

---

## Current State Analysis

### What Exists (Production-Ready)
| Component | Location | Lines | Status |
|-----------|----------|-------|--------|
| Cortex CLI | `notion-learning-sync/src/cli/cortex.py` | 1,277 | 95% Complete |
| StudyService | `notion-learning-sync/src/study/study_service.py` | 1,349 | 90% Complete |
| Google Calendar | `notion-learning-sync/src/integrations/google_calendar.py` | 345 | 100% Complete |
| AdaptiveEngine (C#) | `right-learning/backend/.../AdaptiveEngineService.cs` | 414 | 70% Complete |
| Learner Profiles | `migrations/013_adaptive_engine.sql` | 217 | Schema Only |
| Neuro Integration | `migrations/012_neurocognitive_integration.sql` | 366 | Schema Only |

### What's Missing
1. **Cognitive Diagnosis Engine** - No error classification by brain region
2. **Learner Persona Service** - Tables exist but no profile-building logic
3. **LLM Integration** - ChatService stub exists but no Vertex AI connection
4. **Smart Scheduling** - Calendar books events but doesn't optimize by bio-rhythm
5. **Intervention System** - Tables exist but no trigger logic
6. **Project Generation** - Not implemented

---

## Architecture Overview

```
+------------------------------------------------------------------+
|                        CORTEX 2.0                                 |
+------------------------------------------------------------------+
|                                                                   |
|  +----------------+     +------------------+     +--------------+ |
|  |   CLI Layer    |     |   Brain Engine   |     |  Integrations| |
|  +----------------+     +------------------+     +--------------+ |
|  | cortex.py      |---->| neuro_model.py   |---->| vertex_ai.py | |
|  | (User Input)   |     | (Error Diagnosis)|     | (LLM Tutor)  | |
|  +----------------+     +------------------+     +--------------+ |
|         |                       |                       |         |
|         v                       v                       v         |
|  +----------------+     +------------------+     +--------------+ |
|  | study_service  |     | persona_service  |     | calendar.py  | |
|  | (Session Mgmt) |     | (Learner Profile)|     | (Scheduling) | |
|  +----------------+     +------------------+     +--------------+ |
|         |                       |                       |         |
|         +---------------+-------+-----------------------+         |
|                         |                                         |
|                         v                                         |
|  +----------------------------------------------------------+    |
|  |                    PostgreSQL                              |   |
|  | learner_profiles | intervention_events | atom_responses   |   |
|  +----------------------------------------------------------+    |
+------------------------------------------------------------------+
```

---

## Implementation Phases

### Phase 1: The Cognitive Model (neuro_model.py)
**Goal**: Diagnose WHY users fail, not just THAT they failed.

#### New File: `src/adaptive/neuro_model.py`

```python
"""
Cognitive Model for error diagnosis.

Maps behavioral signatures to cognitive systems:
- Hippocampus: Encoding/retrieval failures (memory)
- P-FIT: Integration failures (reasoning)
- Prefrontal Cortex: Executive failures (impulsivity)
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class CognitiveState(Enum):
    """Learner's current cognitive state."""
    FLOW = "flow"                    # Optimal challenge-skill balance
    ANXIETY = "anxiety"              # Too hard, overwhelmed
    BOREDOM = "boredom"              # Too easy, disengaged
    FATIGUE = "fatigue"              # Cognitive exhaustion
    DISTRACTED = "distracted"        # Attention elsewhere

class FailMode(Enum):
    """Classification of error types by cognitive system."""
    ENCODING_ERROR = "encoding"      # Hippocampus - never consolidated
    RETRIEVAL_ERROR = "retrieval"    # Hippocampus - stored but can't access
    INTEGRATION_ERROR = "integration" # P-FIT - facts don't connect
    DISCRIMINATION_ERROR = "discrimination"  # Dentate Gyrus - confused similar items
    EXECUTIVE_ERROR = "executive"    # PFC - impulsivity, didn't read carefully
    FATIGUE_ERROR = "fatigue"        # General - cognitive exhaustion

class SuccessMode(Enum):
    """Classification of success patterns."""
    RECALL = "recall"                # Retrieved from memory correctly
    RECOGNITION = "recognition"      # Recognized among options
    INFERENCE = "inference"          # Derived from related knowledge
    FLUENCY = "fluency"              # Automatic, effortless

@dataclass
class CognitiveDiagnosis:
    """Result of analyzing a user interaction."""
    fail_mode: Optional[FailMode]
    success_mode: Optional[SuccessMode]
    cognitive_state: CognitiveState
    confidence: float  # 0-1 confidence in diagnosis
    remediation_type: str  # 'repeat', 'elaborate', 'contrast', 'rest', 'read'
    remediation_target: Optional[str]  # Source section or concept ID


def diagnose_interaction(
    atom: dict,
    is_correct: bool,
    response_time_ms: int,
    recent_history: list[dict],  # Last 10 interactions
) -> CognitiveDiagnosis:
    """
    Analyze an interaction to diagnose cognitive patterns.

    Algorithm:
    1. If correct: classify success type
    2. If incorrect: classify failure type based on:
       - Response time (fast fail = impulsivity)
       - Atom type (numeric fail = integration error)
       - History (repeated fail = encoding error)
       - Distractor choice (similar = discrimination error)
    """
    # Fast failure detection (< 1.5s)
    if not is_correct and response_time_ms < 1500:
        return CognitiveDiagnosis(
            fail_mode=FailMode.EXECUTIVE_ERROR,
            success_mode=None,
            cognitive_state=CognitiveState.DISTRACTED,
            confidence=0.7,
            remediation_type="slow_down",
            remediation_target=None,
        )

    # Repeated failure detection (>3 lapses)
    lapses = atom.get("lapses", 0)
    if not is_correct and lapses >= 3:
        return CognitiveDiagnosis(
            fail_mode=FailMode.ENCODING_ERROR,
            success_mode=None,
            cognitive_state=CognitiveState.ANXIETY,
            confidence=0.8,
            remediation_type="read",
            remediation_target=atom.get("source_fact_basis"),
        )

    # Numeric/Parsons failure = Integration error
    atom_type = atom.get("atom_type", "flashcard")
    if not is_correct and atom_type in ("numeric", "parsons"):
        return CognitiveDiagnosis(
            fail_mode=FailMode.INTEGRATION_ERROR,
            success_mode=None,
            cognitive_state=CognitiveState.ANXIETY,
            confidence=0.75,
            remediation_type="worked_example",
            remediation_target=atom.get("id"),
        )

    # New item failure = Encoding error
    review_count = atom.get("review_count", 0)
    if not is_correct and review_count <= 1:
        return CognitiveDiagnosis(
            fail_mode=FailMode.ENCODING_ERROR,
            success_mode=None,
            cognitive_state=CognitiveState.FLOW,  # Normal for new items
            confidence=0.6,
            remediation_type="elaborate",
            remediation_target=atom.get("concept_id"),
        )

    # Fatigue detection (slowing response times)
    if recent_history and len(recent_history) >= 5:
        recent_times = [h.get("response_time_ms", 0) for h in recent_history[-5:]]
        if all(t > 10000 for t in recent_times):  # All > 10s
            return CognitiveDiagnosis(
                fail_mode=FailMode.FATIGUE_ERROR if not is_correct else None,
                success_mode=SuccessMode.RECALL if is_correct else None,
                cognitive_state=CognitiveState.FATIGUE,
                confidence=0.65,
                remediation_type="rest",
                remediation_target=None,
            )

    # Default success
    if is_correct:
        success_mode = SuccessMode.FLUENCY if response_time_ms < 3000 else SuccessMode.RECALL
        return CognitiveDiagnosis(
            fail_mode=None,
            success_mode=success_mode,
            cognitive_state=CognitiveState.FLOW,
            confidence=0.5,
            remediation_type="continue",
            remediation_target=None,
        )

    # Default failure (retrieval error)
    return CognitiveDiagnosis(
        fail_mode=FailMode.RETRIEVAL_ERROR,
        success_mode=None,
        cognitive_state=CognitiveState.FLOW,
        confidence=0.5,
        remediation_type="repeat",
        remediation_target=None,
    )
```

---

### Phase 2: The Learner Persona (persona_service.py)
**Goal**: Build and evolve a dynamic profile for each learner.

#### New File: `src/adaptive/persona_service.py`

```python
"""
Learner Persona Service.

Builds and maintains a dynamic cognitive profile that evolves with every interaction.
This profile is injected into LLM prompts for personalized tutoring.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import json

from sqlalchemy import text
from src.db.database import engine


@dataclass
class LearnerPersona:
    """
    Dynamic cognitive profile of a learner.

    Updated after every session based on performance patterns.
    """
    user_id: str

    # Processing characteristics
    processing_speed: str = "moderate"  # fast_accurate, fast_inaccurate, slow_accurate, slow_inaccurate
    attention_span_minutes: int = 25  # Before accuracy drops
    preferred_session_length: int = 25  # Pomodoro default

    # Chronotype
    chronotype: str = "neutral"  # morning_lark, night_owl, neutral
    peak_performance_hour: int = 10  # 0-23
    low_energy_hours: list[int] = field(default_factory=lambda: [14, 15, 16])  # Afternoon dip

    # Strengths/Weaknesses by Knowledge Type
    strength_factual: float = 0.5
    strength_conceptual: float = 0.5
    strength_procedural: float = 0.5
    strength_strategic: float = 0.5

    # Mechanism Effectiveness
    effectiveness_retrieval: float = 0.5
    effectiveness_generation: float = 0.5
    effectiveness_elaboration: float = 0.5
    effectiveness_application: float = 0.5
    effectiveness_discrimination: float = 0.5

    # Struggle patterns
    interference_prone_topics: list[str] = field(default_factory=list)  # Concepts often confused
    conceptual_weaknesses: list[str] = field(default_factory=list)  # Fundamental gaps

    # Calibration
    calibration_score: float = 0.5  # <0.5 = underconfident, >0.5 = overconfident

    # Learning modality preferences
    preferred_modality: str = "mixed"  # visual, procedural, declarative, mixed

    def to_prompt_context(self) -> str:
        """
        Generate context string for LLM prompts.

        This is injected into every AI tutoring prompt so the LLM
        understands how to communicate with this specific learner.
        """
        strengths = []
        if self.strength_factual > 0.7:
            strengths.append("factual recall")
        if self.strength_procedural > 0.7:
            strengths.append("step-by-step procedures")
        if self.strength_conceptual > 0.7:
            strengths.append("abstract concepts")

        weaknesses = []
        if self.strength_factual < 0.4:
            weaknesses.append("memorizing specific facts")
        if self.strength_procedural < 0.4:
            weaknesses.append("following multi-step procedures")
        if self.strength_conceptual < 0.4:
            weaknesses.append("grasping abstract concepts")

        context = f"""
LEARNER PROFILE:
- Processing Style: {self.processing_speed}
- Attention Span: ~{self.attention_span_minutes} minutes before fatigue
- Peak Performance: {self.peak_performance_hour}:00 (chronotype: {self.chronotype})
- Strengths: {', '.join(strengths) if strengths else 'Balanced'}
- Areas for Growth: {', '.join(weaknesses) if weaknesses else 'None identified'}
- Topics Often Confused: {', '.join(self.interference_prone_topics) if self.interference_prone_topics else 'None'}
- Preferred Explanations: {self.preferred_modality}
- Calibration: {'Tends to be overconfident' if self.calibration_score > 0.6 else 'Tends to be underconfident' if self.calibration_score < 0.4 else 'Well-calibrated'}

COMMUNICATION GUIDELINES:
- {'Use concrete examples and analogies' if self.strength_conceptual < 0.5 else 'Can handle abstract explanations'}
- {'Break down into small steps' if self.strength_procedural < 0.5 else 'Can handle multi-step explanations'}
- {'Use visual diagrams when possible' if self.preferred_modality == 'visual' else 'Text-based explanations work well'}
- {'Challenge overconfidence with Socratic questions' if self.calibration_score > 0.6 else 'Build confidence with positive reinforcement'}
"""
        return context.strip()


class PersonaService:
    """
    Service for building and updating learner personas.
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id

    def get_persona(self) -> LearnerPersona:
        """Load or create learner persona from database."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    strength_factual,
                    strength_conceptual,
                    strength_procedural,
                    strength_strategic,
                    effectiveness_retrieval,
                    effectiveness_generation,
                    effectiveness_elaboration,
                    effectiveness_application,
                    effectiveness_discrimination,
                    calibration_score,
                    preferred_session_duration_min,
                    optimal_study_hour
                FROM learner_profiles
                WHERE user_id = :user_id
            """), {"user_id": self.user_id})

            row = result.fetchone()

            if not row:
                # Create default persona
                return self._create_default_persona()

            return LearnerPersona(
                user_id=self.user_id,
                strength_factual=float(row.strength_factual or 0.5),
                strength_conceptual=float(row.strength_conceptual or 0.5),
                strength_procedural=float(row.strength_procedural or 0.5),
                strength_strategic=float(row.strength_strategic or 0.5),
                effectiveness_retrieval=float(row.effectiveness_retrieval or 0.5),
                effectiveness_generation=float(row.effectiveness_generation or 0.5),
                effectiveness_elaboration=float(row.effectiveness_elaboration or 0.5),
                effectiveness_application=float(row.effectiveness_application or 0.5),
                effectiveness_discrimination=float(row.effectiveness_discrimination or 0.5),
                calibration_score=float(row.calibration_score or 0.5),
                preferred_session_length=int(row.preferred_session_duration_min or 25),
                peak_performance_hour=int(row.optimal_study_hour or 10),
            )

    def _create_default_persona(self) -> LearnerPersona:
        """Create and persist a default persona."""
        persona = LearnerPersona(user_id=self.user_id)
        self._save_persona(persona)
        return persona

    def _save_persona(self, persona: LearnerPersona) -> None:
        """Persist persona to database."""
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO learner_profiles (
                    id, user_id,
                    strength_factual, strength_conceptual,
                    strength_procedural, strength_strategic,
                    effectiveness_retrieval, effectiveness_generation,
                    effectiveness_elaboration, effectiveness_application,
                    effectiveness_discrimination,
                    calibration_score,
                    preferred_session_duration_min,
                    optimal_study_hour
                ) VALUES (
                    gen_random_uuid(), :user_id,
                    :sf, :sc, :sp, :ss,
                    :er, :eg, :ee, :ea, :ed,
                    :cal, :session_dur, :peak_hour
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    strength_factual = :sf,
                    strength_conceptual = :sc,
                    strength_procedural = :sp,
                    strength_strategic = :ss,
                    effectiveness_retrieval = :er,
                    effectiveness_generation = :eg,
                    effectiveness_elaboration = :ee,
                    effectiveness_application = :ea,
                    effectiveness_discrimination = :ed,
                    calibration_score = :cal,
                    preferred_session_duration_min = :session_dur,
                    optimal_study_hour = :peak_hour,
                    updated_at = NOW()
            """), {
                "user_id": persona.user_id,
                "sf": persona.strength_factual,
                "sc": persona.strength_conceptual,
                "sp": persona.strength_procedural,
                "ss": persona.strength_strategic,
                "er": persona.effectiveness_retrieval,
                "eg": persona.effectiveness_generation,
                "ee": persona.effectiveness_elaboration,
                "ea": persona.effectiveness_application,
                "ed": persona.effectiveness_discrimination,
                "cal": persona.calibration_score,
                "session_dur": persona.preferred_session_length,
                "peak_hour": persona.peak_performance_hour,
            })
            conn.commit()

    def update_from_session(self, session_stats: dict) -> None:
        """
        Update persona based on session performance.

        Args:
            session_stats: Dict with keys:
                - correct_by_type: {knowledge_type: count}
                - incorrect_by_type: {knowledge_type: count}
                - correct_by_mechanism: {mechanism: count}
                - incorrect_by_mechanism: {mechanism: count}
                - avg_response_time_ms: int
                - session_duration_minutes: int
        """
        persona = self.get_persona()

        # Update knowledge type strengths (exponential moving average)
        alpha = 0.1  # Learning rate
        for ktype in ["factual", "conceptual", "procedural", "strategic"]:
            correct = session_stats.get("correct_by_type", {}).get(ktype, 0)
            incorrect = session_stats.get("incorrect_by_type", {}).get(ktype, 0)
            total = correct + incorrect
            if total > 0:
                session_accuracy = correct / total
                current = getattr(persona, f"strength_{ktype}")
                new_value = current * (1 - alpha) + session_accuracy * alpha
                setattr(persona, f"strength_{ktype}", new_value)

        # Update mechanism effectiveness
        for mechanism in ["retrieval", "generation", "elaboration", "application", "discrimination"]:
            correct = session_stats.get("correct_by_mechanism", {}).get(mechanism, 0)
            incorrect = session_stats.get("incorrect_by_mechanism", {}).get(mechanism, 0)
            total = correct + incorrect
            if total > 0:
                session_accuracy = correct / total
                current = getattr(persona, f"effectiveness_{mechanism}")
                new_value = current * (1 - alpha) + session_accuracy * alpha
                setattr(persona, f"effectiveness_{mechanism}", new_value)

        # Update processing speed classification
        avg_time = session_stats.get("avg_response_time_ms", 5000)
        accuracy = session_stats.get("overall_accuracy", 0.5)
        if avg_time < 3000 and accuracy > 0.8:
            persona.processing_speed = "fast_accurate"
        elif avg_time < 3000 and accuracy <= 0.8:
            persona.processing_speed = "fast_inaccurate"
        elif avg_time >= 3000 and accuracy > 0.8:
            persona.processing_speed = "slow_accurate"
        else:
            persona.processing_speed = "slow_inaccurate"

        self._save_persona(persona)
```

---

### Phase 3: Vertex AI Tutor Integration (vertex_tutor.py)
**Goal**: Socratic tutoring when learner struggles.

#### New File: `src/integrations/vertex_tutor.py`

```python
"""
Vertex AI Tutor Integration.

Provides AI-powered remediation when learner struggles with concepts.
Uses the LearnerPersona for personalized explanations.
"""
import os
from typing import Optional
from loguru import logger

# Lazy import for Vertex AI
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    GenerativeModel = None


class VertexTutor:
    """
    AI tutor powered by Vertex AI (Gemini).

    Provides:
    - Remediation explanations for failed concepts
    - Contrastive analysis for discrimination errors
    - Worked examples for integration errors
    - Encouragement for flow state maintenance
    """

    def __init__(self, project_id: Optional[str] = None, location: str = "us-central1"):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.model = None
        self._initialized = False

    @property
    def is_available(self) -> bool:
        return VERTEX_AVAILABLE and self.project_id is not None

    def initialize(self) -> bool:
        """Initialize Vertex AI client."""
        if not self.is_available:
            logger.warning("Vertex AI not available. Install google-cloud-aiplatform.")
            return False

        try:
            aiplatform.init(project=self.project_id, location=self.location)
            self.model = GenerativeModel("gemini-1.5-flash")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            return False

    def get_remediation(
        self,
        atom: dict,
        user_answer: str,
        fail_mode: str,
        persona_context: str,
    ) -> str:
        """
        Generate a remediation explanation for a failed item.

        Args:
            atom: The learning atom dict
            user_answer: What the user answered
            fail_mode: Type of cognitive failure (from neuro_model)
            persona_context: LearnerPersona prompt context

        Returns:
            AI-generated explanation tailored to the learner
        """
        if not self._initialized:
            if not self.initialize():
                return self._fallback_remediation(atom, fail_mode)

        prompts = {
            "encoding": self._encoding_prompt,
            "integration": self._integration_prompt,
            "discrimination": self._discrimination_prompt,
            "executive": self._executive_prompt,
            "retrieval": self._retrieval_prompt,
        }

        prompt_fn = prompts.get(fail_mode, self._retrieval_prompt)
        prompt = prompt_fn(atom, user_answer, persona_context)

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Vertex AI generation failed: {e}")
            return self._fallback_remediation(atom, fail_mode)

    def _encoding_prompt(self, atom: dict, user_answer: str, persona: str) -> str:
        return f"""
{persona}

TASK: The learner is having trouble encoding (memorizing) this concept.
They have failed it multiple times, indicating the memory trace isn't forming.

CONCEPT TO EXPLAIN:
Question: {atom.get('front', '')}
Correct Answer: {atom.get('back', '')}
Their Answer: {user_answer}

INSTRUCTIONS:
1. Don't just repeat the fact - they've seen it multiple times
2. Create memorable "hooks" - analogies, stories, mnemonics
3. Connect it to something they already know
4. Be brief (3-4 sentences max)
5. End with a simple self-check question

Provide your explanation:
"""

    def _integration_prompt(self, atom: dict, user_answer: str, persona: str) -> str:
        steps = atom.get("numeric_steps") or atom.get("back", "").split("\n")
        return f"""
{persona}

TASK: The learner failed a calculation/procedure problem.
This is an INTEGRATION ERROR - they know the facts but can't connect them to solve problems.

PROBLEM:
{atom.get('front', '')}

CORRECT SOLUTION:
{chr(10).join(steps) if isinstance(steps, list) else steps}

THEIR ANSWER: {user_answer}

INSTRUCTIONS:
1. Identify which STEP they likely got wrong
2. Explain the LOGIC of that step (not just the mechanics)
3. Use a simple worked example if helpful
4. Ask them to identify what they missed

Provide your explanation:
"""

    def _discrimination_prompt(self, atom: dict, user_answer: str, persona: str) -> str:
        return f"""
{persona}

TASK: The learner confused two similar concepts (DISCRIMINATION ERROR).
The Dentate Gyrus needs practice separating these patterns.

QUESTION:
{atom.get('front', '')}

CORRECT: {atom.get('back', '')}
THEIR ANSWER (wrong): {user_answer}

INSTRUCTIONS:
1. Create a clear COMPARISON between what they chose and the correct answer
2. Highlight the KEY DIFFERENCE (not all differences)
3. Provide a "When to use X vs Y" rule
4. Use a memorable contrast or analogy

Provide your explanation:
"""

    def _executive_prompt(self, atom: dict, user_answer: str, persona: str) -> str:
        return f"""
{persona}

TASK: The learner answered too quickly and got it wrong (EXECUTIVE ERROR).
This is an impulsivity issue, not a knowledge gap.

QUESTION: {atom.get('front', '')}
CORRECT: {atom.get('back', '')}
THEIR ANSWER: {user_answer}
RESPONSE TIME: Very fast (< 1.5 seconds)

INSTRUCTIONS:
1. Gently point out they might have rushed
2. Ask them to re-read the question carefully
3. Suggest a "pause and think" strategy
4. Don't over-explain - they probably know this

Keep your response very brief (2 sentences):
"""

    def _retrieval_prompt(self, atom: dict, user_answer: str, persona: str) -> str:
        return f"""
{persona}

TASK: The learner couldn't retrieve this from memory.
They may have known it before but the memory trace faded.

QUESTION: {atom.get('front', '')}
CORRECT: {atom.get('back', '')}
THEIR ANSWER: {user_answer}

INSTRUCTIONS:
1. Briefly explain the concept
2. Connect it to related concepts they might remember
3. Suggest a retrieval cue they can use next time
4. Be encouraging - this is normal memory behavior

Provide your explanation (3-4 sentences):
"""

    def _fallback_remediation(self, atom: dict, fail_mode: str) -> str:
        """Fallback when Vertex AI is unavailable."""
        return f"""
[AI Tutor Unavailable]

Correct Answer: {atom.get('back', '')}

Source: {atom.get('source_fact_basis', 'Review your notes')}

Tip: This was a {fail_mode} error. Try re-reading the source material.
"""

    def get_encouragement(self, streak: int, accuracy: float) -> str:
        """Generate encouragement for flow state maintenance."""
        if not self._initialized:
            if not self.initialize():
                return self._fallback_encouragement(streak, accuracy)

        prompt = f"""
Generate a single sentence of cyberpunk-themed encouragement for a learner.

Context:
- Current streak: {streak} correct answers
- Session accuracy: {accuracy*100:.0f}%
- Mood: {"Crushing it" if streak > 10 else "Building momentum" if streak > 5 else "Getting warmed up"}

Style: Brief, punchy, cyberpunk/neural-network themed.
Example: "Neural pathways reinforcing. Your pattern recognition subroutines are operating at peak efficiency."

Generate one sentence:
"""
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return self._fallback_encouragement(streak, accuracy)

    def _fallback_encouragement(self, streak: int, accuracy: float) -> str:
        if streak > 10:
            return "[*] NEURAL OPTIMIZATION: PEAK STATE DETECTED"
        elif streak > 5:
            return "[*] PATTERN LOCK: Synaptic efficiency increasing"
        else:
            return "[*] INITIALIZATION SEQUENCE: Neural calibration in progress"
```

---

### Phase 4: Smart Calendar Scheduling
**Goal**: Schedule based on bio-rhythms, not just empty slots.

#### Update: `src/integrations/google_calendar.py`

Add these methods to the existing `CortexCalendar` class:

```python
def suggest_optimal_schedule(
    self,
    persona: "LearnerPersona",
    days_ahead: int = 7,
    session_types: list[str] = None,
) -> list[dict]:
    """
    Suggest optimal study times based on learner's chronotype.

    Args:
        persona: Learner persona with chronotype info
        days_ahead: Days to schedule
        session_types: Types of sessions to schedule

    Returns:
        List of suggested time slots with type recommendations
    """
    if session_types is None:
        session_types = ["deep_work", "maintenance", "review"]

    suggestions = []

    for day_offset in range(days_ahead):
        date = datetime.now() + timedelta(days=day_offset)

        # Skip if it's today and past peak hour
        if day_offset == 0 and datetime.now().hour > persona.peak_performance_hour:
            continue

        # Deep Work: Morning (peak hour)
        if "deep_work" in session_types:
            deep_work_hour = persona.peak_performance_hour
            suggestions.append({
                "type": "deep_work",
                "description": "High cognitive load (Parsons, Numeric)",
                "start_hour": deep_work_hour,
                "duration_minutes": 60,
                "date": date.date(),
                "reasoning": f"Peak performance window based on your chronotype ({persona.chronotype})",
            })

        # Maintenance: Afternoon (lower energy)
        if "maintenance" in session_types:
            maintenance_hour = persona.low_energy_hours[0] if persona.low_energy_hours else 14
            suggestions.append({
                "type": "maintenance",
                "description": "Light review (Flashcards)",
                "start_hour": maintenance_hour,
                "duration_minutes": 20,
                "date": date.date(),
                "reasoning": "Lower cognitive load appropriate for afternoon energy dip",
            })

        # Review: Evening (consolidation)
        if "review" in session_types:
            suggestions.append({
                "type": "review",
                "description": "Spaced review before sleep",
                "start_hour": 20,  # 8 PM
                "duration_minutes": 15,
                "date": date.date(),
                "reasoning": "Pre-sleep review enhances memory consolidation",
            })

    return suggestions


def auto_schedule_week(
    self,
    persona: "LearnerPersona",
    mastery_data: dict,
) -> list[str]:
    """
    Automatically schedule a week of optimized study sessions.

    Args:
        persona: Learner persona
        mastery_data: Current mastery stats

    Returns:
        List of created event IDs
    """
    suggestions = self.suggest_optimal_schedule(persona, days_ahead=7)
    created_events = []

    for suggestion in suggestions:
        # Determine modules based on session type and mastery
        if suggestion["type"] == "deep_work":
            # Focus on weak areas with high-load atoms
            modules = mastery_data.get("weak_modules", [11, 12, 13])
            title = "Cortex Deep Work"
        elif suggestion["type"] == "maintenance":
            # Flashcard review
            modules = mastery_data.get("maintenance_modules", list(range(1, 18)))
            title = "Cortex Maintenance"
        else:
            # Evening review
            modules = mastery_data.get("review_modules", list(range(11, 18)))
            title = "Cortex Review"

        start_time = datetime.combine(
            suggestion["date"],
            datetime.min.time().replace(hour=suggestion["start_hour"]),
        )

        event_id = self.book_study_session(
            start_time=start_time,
            duration_minutes=suggestion["duration_minutes"],
            modules=modules,
            title=title,
        )

        if event_id:
            created_events.append(event_id)

    return created_events


def list_events(self, days: int = 7) -> list[dict]:
    """List all calendar events (not just Cortex ones)."""
    if not self._authenticated or not self.service:
        return []

    now = datetime.utcnow()
    time_max = now + timedelta(days=days)

    try:
        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=now.isoformat() + "Z",
            timeMax=time_max.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return events_result.get("items", [])
    except Exception as e:
        logger.warning(f"Could not fetch events: {e}")
        return []


def update_event(
    self,
    event_id: str,
    new_start_time: Optional[datetime] = None,
    new_duration_minutes: Optional[int] = None,
    new_title: Optional[str] = None,
) -> bool:
    """Update an existing calendar event."""
    if not self._authenticated or not self.service:
        return False

    try:
        # Get existing event
        event = self.service.events().get(
            calendarId="primary",
            eventId=event_id,
        ).execute()

        # Update fields
        if new_start_time:
            event["start"]["dateTime"] = new_start_time.isoformat()
            if new_duration_minutes:
                end_time = new_start_time + timedelta(minutes=new_duration_minutes)
            else:
                # Keep same duration
                old_start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", ""))
                old_end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", ""))
                duration = old_end - old_start
                end_time = new_start_time + duration
            event["end"]["dateTime"] = end_time.isoformat()

        if new_title:
            event["summary"] = new_title

        self.service.events().update(
            calendarId="primary",
            eventId=event_id,
            body=event,
        ).execute()

        return True
    except Exception as e:
        logger.error(f"Failed to update event: {e}")
        return False


def create_task(
    self,
    title: str,
    due_datetime: datetime,
    description: str = "",
) -> Optional[str]:
    """Create a task/reminder event on calendar."""
    return self.book_study_session(
        start_time=due_datetime,
        duration_minutes=0,  # Zero-duration = task
        modules=[],
        title=f"[!] {title}",
    )
```

---

### Phase 5: CLI Integration
**Goal**: Wire everything together in the Cortex CLI.

#### Updates to `src/cli/cortex.py`

Key additions:

```python
# Add imports at top
from src.adaptive.neuro_model import diagnose_interaction, CognitiveDiagnosis, FailMode
from src.adaptive.persona_service import PersonaService, LearnerPersona
from src.integrations.vertex_tutor import VertexTutor


# Add to CortexSession.__init__
self.persona_service = PersonaService()
self.persona = self.persona_service.get_persona()
self.vertex_tutor = VertexTutor()
self.session_history = []  # Track recent interactions for diagnosis
self.diagnosis_history = []  # Track cognitive diagnoses


# Update record_interaction in the session run loop
def _process_answer(self, note: dict, is_correct: bool, response_time_ms: int, user_answer: str):
    """Process answer with cognitive diagnosis."""
    # Record basic interaction
    self.study_service.record_interaction(
        atom_id=note.get("id"),
        is_correct=is_correct,
        response_time_ms=response_time_ms,
        user_answer=user_answer,
        session_type="war" if self.war_mode else "adaptive",
    )

    # Cognitive diagnosis
    diagnosis = diagnose_interaction(
        atom=note,
        is_correct=is_correct,
        response_time_ms=response_time_ms,
        recent_history=self.session_history[-10:],
    )

    self.session_history.append({
        "atom_id": note.get("id"),
        "is_correct": is_correct,
        "response_time_ms": response_time_ms,
    })
    self.diagnosis_history.append(diagnosis)

    # Trigger intervention if needed
    if not is_correct and diagnosis.fail_mode in (
        FailMode.ENCODING_ERROR,
        FailMode.INTEGRATION_ERROR,
        FailMode.DISCRIMINATION_ERROR,
    ):
        self._offer_remediation(note, user_answer, diagnosis)

    return diagnosis


def _offer_remediation(
    self,
    note: dict,
    user_answer: str,
    diagnosis: CognitiveDiagnosis,
):
    """Offer AI-powered remediation for cognitive errors."""
    # Display diagnosis
    diagnosis_panel = Panel(
        f"[bold magenta]⚠ {diagnosis.fail_mode.value.upper()} ERROR DETECTED[/]\n\n"
        f"Recommended: {diagnosis.remediation_type.replace('_', ' ').title()}",
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.HEAVY,
    )
    console.print(diagnosis_panel)

    # Offer AI help
    if Confirm.ask("[cyan]Activate Neural Remediation?[/cyan]", default=True):
        with CortexSpinner(console, "Consulting neural networks..."):
            explanation = self.vertex_tutor.get_remediation(
                atom=note,
                user_answer=user_answer,
                fail_mode=diagnosis.fail_mode.value,
                persona_context=self.persona.to_prompt_context(),
            )

        console.print(Panel(
            explanation,
            title="[bold cyan][*] NEURAL REMEDIATION[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["accent"]),
            box=box.HEAVY,
        ))

        # Ask if helpful
        was_helpful = Confirm.ask("Was this explanation helpful?", default=True)
        # TODO: Record intervention feedback


# Add new command: chat
@cortex_app.command("chat")
def cortex_chat():
    """
    Interactive chat with the AI tutor.

    Context-aware conversations about your learning material.
    """
    persona_service = PersonaService()
    persona = persona_service.get_persona()
    vertex_tutor = VertexTutor()

    if not vertex_tutor.is_available:
        console.print(Panel(
            "[yellow]Vertex AI not configured.[/yellow]\n\n"
            "Set GOOGLE_CLOUD_PROJECT environment variable\n"
            "and install google-cloud-aiplatform.",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    if not vertex_tutor.initialize():
        console.print("[red]Failed to initialize Vertex AI[/red]")
        return

    console.print(Panel(
        "[cyan]CORTEX NEURAL INTERFACE ACTIVE[/cyan]\n\n"
        "Ask questions about your learning material.\n"
        "Type 'exit' to close the connection.",
        border_style=Style(color=CORTEX_THEME["primary"]),
    ))

    while True:
        user_input = Prompt.ask("\n[cyan]>_ INPUT[/cyan]")

        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[dim]Neural interface disconnected.[/dim]")
            break

        # TODO: Implement chat with context from recent session


# Add new command: profile
@cortex_app.command("profile")
def cortex_profile():
    """
    Display your cognitive learner profile.
    """
    persona_service = PersonaService()
    persona = persona_service.get_persona()

    # Build profile display
    content = Text()
    content.append("[*] LEARNER COGNITIVE PROFILE [*]\n\n", style=STYLES["cortex_primary"])

    content.append("PROCESSING\n", style=STYLES["cortex_accent"])
    content.append(f"  Speed: {persona.processing_speed.replace('_', ' ').title()}\n")
    content.append(f"  Attention Span: {persona.attention_span_minutes} min\n")
    content.append(f"  Chronotype: {persona.chronotype.replace('_', ' ').title()}\n")
    content.append(f"  Peak Hour: {persona.peak_performance_hour}:00\n\n")

    content.append("KNOWLEDGE TYPE STRENGTHS\n", style=STYLES["cortex_accent"])
    for ktype in ["factual", "conceptual", "procedural", "strategic"]:
        value = getattr(persona, f"strength_{ktype}")
        bar = _format_progress_bar(value * 100, 10)
        content.append(f"  {ktype.title()}: {bar} {value*100:.0f}%\n")

    content.append("\nMECHANISM EFFECTIVENESS\n", style=STYLES["cortex_accent"])
    for mech in ["retrieval", "generation", "elaboration", "application", "discrimination"]:
        value = getattr(persona, f"effectiveness_{mech}")
        bar = _format_progress_bar(value * 100, 10)
        content.append(f"  {mech.title()}: {bar} {value*100:.0f}%\n")

    content.append("\nCALIBRATION\n", style=STYLES["cortex_accent"])
    cal = persona.calibration_score
    if cal > 0.6:
        content.append("  [yellow]Tends toward overconfidence[/yellow]\n")
    elif cal < 0.4:
        content.append("  [blue]Tends toward underconfidence[/blue]\n")
    else:
        content.append("  [green]Well-calibrated[/green]\n")

    console.print(Panel(
        content,
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))


# Add new command: auto-schedule
@cortex_app.command("auto-schedule")
def cortex_auto_schedule(
    days: int = typer.Option(7, "--days", "-d", help="Days to schedule"),
):
    """
    Auto-schedule study sessions based on your cognitive profile.
    """
    persona_service = PersonaService()
    persona = persona_service.get_persona()
    study_service = StudyService()
    calendar = CortexCalendar()

    if not calendar.is_available or not calendar.has_credentials:
        console.print(calendar.get_setup_instructions())
        return

    if not calendar.authenticate():
        console.print("[red]Calendar authentication failed[/red]")
        return

    # Get mastery data for scheduling decisions
    stats = study_service.get_study_stats()
    mastery_data = {
        "weak_modules": [],  # TODO: Calculate from stats
        "maintenance_modules": list(range(1, 18)),
        "review_modules": list(range(11, 18)),
    }

    console.print(Panel(
        f"[cyan]Analyzing your cognitive profile and calendar...[/cyan]\n"
        f"Chronotype: {persona.chronotype}\n"
        f"Peak Hour: {persona.peak_performance_hour}:00",
        border_style=Style(color=CORTEX_THEME["primary"]),
    ))

    # Get suggestions
    suggestions = calendar.suggest_optimal_schedule(persona, days_ahead=days)

    # Display suggestions
    table = Table(
        title="[bold cyan]SUGGESTED SCHEDULE[/bold cyan]",
        box=box.HEAVY,
    )
    table.add_column("Date", style=STYLES["cortex_accent"])
    table.add_column("Time", style=STYLES["cortex_white"])
    table.add_column("Type", style=STYLES["cortex_warning"])
    table.add_column("Duration")
    table.add_column("Reasoning", style=STYLES["cortex_dim"])

    for s in suggestions:
        table.add_row(
            str(s["date"]),
            f"{s['start_hour']}:00",
            s["type"].replace("_", " ").title(),
            f"{s['duration_minutes']} min",
            s["reasoning"][:40] + "...",
        )

    console.print(table)

    if Confirm.ask("\n[cyan]Create these calendar events?[/cyan]", default=True):
        event_ids = calendar.auto_schedule_week(persona, mastery_data)
        console.print(f"[green]Created {len(event_ids)} calendar events[/green]")
```

---

## File Structure Summary

```
notion-learning-sync/src/
├── adaptive/
│   ├── __init__.py
│   ├── neuro_model.py          # NEW: Cognitive diagnosis engine
│   └── persona_service.py       # NEW: Learner profile management
├── cli/
│   └── cortex.py                # UPDATE: Add chat, profile, auto-schedule
├── integrations/
│   ├── google_calendar.py       # UPDATE: Add smart scheduling
│   └── vertex_tutor.py          # NEW: AI tutoring integration
└── study/
    └── study_service.py         # UPDATE: Wire in neuro_model
```

---

## Execution Order

| Priority | Component | Prompt | Dependencies |
|----------|-----------|--------|--------------|
| 1 | neuro_model.py | Phase 1 | None |
| 2 | persona_service.py | Phase 2 | None |
| 3 | vertex_tutor.py | Phase 3 | persona_service |
| 4 | google_calendar.py updates | Phase 4 | persona_service |
| 5 | cortex.py updates | Phase 5 | All above |

---

## Testing Strategy

1. **neuro_model.py**: Unit tests with mock interaction data
2. **persona_service.py**: Integration tests against PostgreSQL
3. **vertex_tutor.py**: Mock Vertex AI in tests, manual validation with real API
4. **Calendar**: Manual testing with Google Calendar sandbox
5. **End-to-end**: Run `nls cortex start` and verify diagnosis triggers

---

## Database Schema (Already Exists)

The following tables from `013_adaptive_engine.sql` support this plan:
- `learner_profiles` - Stores persona data
- `intervention_events` - Tracks remediation history
- `calibration_metrics` - Per-domain confidence tracking
- `session_interleaving_log` - Session optimization data

No new migrations required.

---

## Future Enhancements (Post-MVP)

1. **Project Generation**: Auto-generate micro/mini projects from weak concepts
2. **Discrimination Training**: Side-by-side comparison exercises for interference-prone topics
3. **Pomodoro Integration**: Auto-adjust session length based on detected fatigue
4. **Mobile Notifications**: Push study reminders via calendar
5. **Wearable Integration**: Import sleep/exercise data for neuro-optimization

---

# Appendix: PhD-Level Architectural Synthesis

## Research Summary

This section synthesizes the scientific and technical foundations supporting the Cortex 2.0 architecture, based on comprehensive research across Intelligent Tutoring Systems, Neuroscience, and Generative AI.

---

## 1. Intelligent Scheduling: The "X over Y, Force Z" Problem

### Core Challenge
The user requires a system that can intelligently **reject** an upcoming activity (X or Y) and instead **prescribe foundational remediation** (Z) when a deep conceptual gap is detected.

### Solution Architecture: Hierarchical Reinforcement Learning (HRL) + Deep Knowledge Tracing

#### Deep Knowledge Tracing (DKT)
- **What it is**: A recurrent neural network that models student knowledge state over time
- **Key Innovation**: Prerequisite-Driven DKT (PDKT) explicitly models the dependency structure between concepts
- **Citation**: *"Deep Knowledge Tracing"* - Stanford AI Lab, 2015
- **Application**: The DKT backbone provides the **diagnosis** of whether a gap exists and where it is

#### Reinforcement Learning for Instructional Sequencing
- **What it is**: An RL agent that learns the optimal sequence of learning activities to maximize long-term learning gain
- **Key Insight**: The RL policy can learn that "teaching Z before X" yields higher reward than "teaching X directly"
- **Citation**: *"Deep Reinforcement Learning Framework for Instructional Sequencing"* - IEEE, 2023
- **Application**: The RL layer is the **decision engine** that chooses Z over X/Y

#### Hierarchical Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                     MACRO SCHEDULER (Calendar)                   │
│  - Bio-rhythmic scheduling (chronotype-aware)                   │
│  - Session type selection (Deep Work vs. Maintenance)           │
│  - Fatigue/recovery modeling                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MESO SCHEDULER (Session)                     │
│  - Learning goal selection                                       │
│  - Concept cluster prioritization                                │
│  - Interleaving strategy                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MICRO SCHEDULER (Atom)                       │
│  - RL Policy Agent (next learning atom selection)               │
│  - FSRS for spaced repetition timing                            │
│  - Intervention trigger (detect struggle → force Z)             │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Finding: Remediation Trigger Logic
Research confirms the mechanism for "forcing Z":

1. **DKT monitors** the student's performance on concept X
2. If P(mastery of X) < threshold AND X has prerequisite Z:
   - **RL agent calculates** expected reward of:
     - Path A: Continue teaching X → Low expected gain (unstable foundation)
     - Path B: Backtrack to Z, then return to X → Higher expected long-term gain
3. **Policy selects Path B** and queues atoms for concept Z

This is the mathematical formulation of "you must do Z" that the user requested.

---

## 2. Cognitive Training: Hippocampus & P-FIT Targeting

### The Neuroscience Foundation

#### Parieto-Frontal Integration Theory (P-FIT)
- **What it is**: The leading neurobiological theory of general intelligence
- **Key Regions**: Prefrontal cortex (reasoning), parietal cortex (spatial/quantitative), white matter tracts connecting them
- **Training Implication**: Intelligence correlates with the **efficiency of communication** between these regions
- **Citation**: *"The P-FIT of intelligence: Converging neuroimaging evidence"* - Jung & Haier, 2007
- **Application**: Design learning atoms that require **integration** of multiple concepts, forcing cross-network communication

#### Hippocampal Pattern Separation
- **What it is**: The computational process by which the hippocampus distinguishes between similar memories
- **Key Structure**: Dentate Gyrus → CA3 pathway
- **Failure Mode**: When pattern separation fails, similar concepts become confused (e.g., OSPF vs EIGRP)
- **Training Approach**: The **Mnemonic Similarity Task** paradigm trains discrimination between similar stimuli
- **Citation**: *"Pattern separation in the hippocampus"* - Yassa & Stark, 2011
- **Application**: Design "Discrimination" learning atoms that force comparison of similar concepts

### Implementing Cognitive Fail Modes

| Fail Mode | Cognitive System | Behavioral Signature | Remediation Strategy |
|-----------|------------------|---------------------|---------------------|
| Encoding Error | Hippocampus (consolidation) | Fails new item within 5 min | Elaboration (create hooks) |
| Retrieval Error | Hippocampus (access) | Knew before, can't recall now | Cued retrieval practice |
| Integration Error | P-FIT (reasoning) | Knows facts, can't combine | Worked examples |
| Discrimination Error | Dentate Gyrus | Confuses similar items | Contrastive analysis |
| Executive Error | Prefrontal Cortex | Fast + Wrong | Forced latency |
| Fatigue Error | Global | Progressively slower | Rest/break |

### Perceptual Learning Modules (PLMs)
- **What they are**: Training interventions that accelerate the development of perceptual fluency
- **Key Finding**: PLMs in algebra show significant gains in structure recognition (d = 0.5-0.8)
- **Intuition Development**: This is how "Ramanujan-like" pattern recognition is trained—not through explicit rules, but through massive exposure that creates implicit, automatic recognition
- **Citation**: *"Perceptual Learning in Mathematics"* - Kellman et al., 2010
- **Application**: Create rapid-fire exposure drills that train pattern recognition without requiring explicit reasoning

---

## 3. Knowledge Graph Construction: AutoMathKG Pattern

### LLM-Empowered Graph Building

#### The AutoMathKG Architecture
- **Input**: Raw mathematical text (e.g., Spivak's Calculus chapters)
- **Process**: LLM extracts entities (definitions, theorems, proofs) and relationships (prerequisite, applies-to, generalizes)
- **Output**: A structured knowledge graph with semantic embeddings
- **Citation**: *"AutoMathKG: Automated mathematical knowledge graph based on LLM and vector database"* - arXiv, 2024

#### Graph Neural Networks for Prerequisite Prediction
- **Purpose**: Infer hidden prerequisite relationships between concepts
- **Technique**: Heterogeneous Graph Neural Networks trained on known prerequisites can predict new ones
- **Application**: The learner's graph "self-forms" by discovering which concepts must precede others
- **Citation**: *"Heterogeneous GNN for Concept Prerequisite Relation Learning"* - ACL, 2021

### The "Backbone + Adaptation" Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    GLOBAL KNOWLEDGE GRAPH                        │
│  - All human knowledge (curated from world's best resources)   │
│  - Static structure (definitions, theorems, prerequisites)     │
│  - High-quality "Gold Standard" atoms                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Learner begins
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LEARNER KNOWLEDGE GRAPH                       │
│  - Subset of Global Graph activated for this learner           │
│  - Nodes colored by mastery (Red/Yellow/Green/Purple/Blue)     │
│  - Purple = "Implied Mastery" (skipped because too advanced)   │
│  - Blue = "Misconception Path" (optional deep dive)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Weak concepts detected
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROJECT GENERATION                            │
│  - Identify 2-3 weak, related concepts                          │
│  - LLM generates a scaffolded project targeting them            │
│  - Project size: Micro (15m) / Mini (2h) / Standard / Capstone │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Project Generation: The Agentic Pipeline

### AI Agent Workflow for Curriculum Generation

```python
# Pseudocode for Project Generation Agent

class ProjectGeneratorAgent:
    """
    Generates personalized learning projects from knowledge gaps.
    """

    def generate_project(self, weak_concepts: List[Concept], project_size: str):
        # Step 1: Analyze the gap
        gap_analysis = self.llm.analyze(
            prompt=f"""
            The learner struggles with these concepts: {weak_concepts}
            What is the underlying misconception or skill gap?
            What real-world scenario would require these concepts together?
            """
        )

        # Step 2: Generate the project brief
        project = self.llm.generate(
            prompt=f"""
            Create a {project_size} project (micro=15min, mini=2hr, standard=1day, capstone=1week)

            Target Concepts: {weak_concepts}
            Gap Analysis: {gap_analysis}

            Output JSON:
            {{
                "title": "...",
                "scenario": "Real-world context...",
                "learning_objectives": [...],
                "steps": [
                    {{"step": 1, "instruction": "...", "hint": "...", "deliverable": "..."}},
                    ...
                ],
                "rubric": {{
                    "criterion_1": {{"description": "...", "weight": 0.3}},
                    ...
                }},
                "success_criteria": "..."
            }}
            """
        )

        # Step 3: Link to knowledge graph
        project.prerequisite_concepts = self.graph.get_prerequisites(weak_concepts)
        project.target_concepts = weak_concepts

        return project
```

### Project Size Matrix

| Size | Duration | Scope | Example |
|------|----------|-------|---------|
| **Micro** | 5-15 min | Single concept application | "Write a Python script to convert these IPs to binary" |
| **Mini** | 1-2 hours | 2-3 related concepts | "Open Packet Tracer. Build 3-router OSPF topology. Ping across." |
| **Standard** | 1 day | Module-level integration | "Design VLSM scheme for 3-floor office. Document IP plan." |
| **Capstone** | 1 week+ | Cross-module synthesis | "Design secure network for hospital. Write proposal with security justification." |

---

## 5. Critical Analysis: Failure Modes of the System

### 1. Cognitive Offloading Risk
- **The Problem**: Over-reliance on AI scaffolding may prevent the learner from developing independent critical thinking
- **Research Finding**: *"AI alters the mental architecture of coping"* - Frontiers, 2024
- **Mitigation**:
  - Implement "Scaffolding Fade" - gradually reduce AI hints over time
  - Require learner to explain their reasoning before revealing AI feedback
  - Track "independence score" in learner profile

### 2. The Fluency-Creativity Paradox
- **The Problem**: Perceptual learning creates fluency, but Ramanujan's genius came from **creative** pattern recognition, not just speed
- **Research Finding**: Creative insight requires **incubation periods** where the mind wanders (Default Mode Network activation)
- **Citation**: *"Incubation, not sleep, aids problem-solving"* - Oxford Academic, 2019
- **Mitigation**:
  - The system should NOT optimize for 100% time-on-task
  - Build in "diffuse mode" periods between intense sessions
  - Encourage offline rumination with prompts like "Think about this before tomorrow's session"

### 3. Transfer Limitations of Cognitive Training
- **The Problem**: Training on specific tasks may not transfer to general intelligence
- **Research Finding**: P-FIT training shows near-transfer effects but limited far-transfer
- **Citation**: *"Combined cognitive training: Systematic review"* - Frontiers, 2020
- **Mitigation**:
  - Focus on training with **authentic** domain materials (Spivak) rather than abstract cognitive games
  - Measure transfer explicitly with varied assessment types

### 4. Dependency and Learned Helplessness
- **The Problem**: If the system always provides remediation, learners may never develop struggle tolerance
- **Research Finding**: *"Desirable Difficulties"* research shows that some struggle enhances retention
- **Citation**: Bjork, 1994
- **Mitigation**:
  - Implement a "productive struggle" window before offering intervention
  - Track "resilience score" in learner profile

---

## 6. Learner Persona Schema (Technical Specification)

### JSON Schema for Learner Profile

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LearnerPersona",
  "type": "object",
  "properties": {
    "user_id": {"type": "string", "format": "uuid"},
    "processing": {
      "type": "object",
      "properties": {
        "speed": {"enum": ["fast_accurate", "fast_inaccurate", "slow_accurate", "slow_inaccurate"]},
        "attention_span_minutes": {"type": "integer", "minimum": 5, "maximum": 120},
        "working_memory_capacity": {"type": "number", "minimum": 0, "maximum": 1}
      }
    },
    "chronotype": {
      "type": "object",
      "properties": {
        "type": {"enum": ["morning_lark", "night_owl", "neutral"]},
        "peak_hour": {"type": "integer", "minimum": 0, "maximum": 23},
        "low_energy_hours": {"type": "array", "items": {"type": "integer"}}
      }
    },
    "knowledge_strengths": {
      "type": "object",
      "properties": {
        "factual": {"type": "number"},
        "conceptual": {"type": "number"},
        "procedural": {"type": "number"},
        "strategic": {"type": "number"}
      }
    },
    "mechanism_effectiveness": {
      "type": "object",
      "properties": {
        "retrieval": {"type": "number"},
        "generation": {"type": "number"},
        "elaboration": {"type": "number"},
        "application": {"type": "number"},
        "discrimination": {"type": "number"}
      }
    },
    "struggle_patterns": {
      "type": "object",
      "properties": {
        "interference_prone_topics": {"type": "array", "items": {"type": "string"}},
        "conceptual_gaps": {"type": "array", "items": {"type": "string"}},
        "typical_fail_mode": {"enum": ["encoding", "retrieval", "integration", "discrimination", "executive"]}
      }
    },
    "calibration": {
      "type": "object",
      "properties": {
        "score": {"type": "number", "description": "<0.5=under, 0.5=good, >0.5=over"},
        "overconfidence_rate": {"type": "number"},
        "underconfidence_rate": {"type": "number"}
      }
    },
    "acceleration": {
      "type": "object",
      "properties": {
        "baseline_learning_rate": {"type": "number", "description": "Items mastered per hour at start"},
        "current_learning_rate": {"type": "number"},
        "acceleration_factor": {"type": "number", "description": "Current/Baseline ratio"},
        "tier1_active": {"type": "boolean", "description": "Learning science techniques"},
        "tier2_active": {"type": "boolean", "description": "Neuroplasticity protocols"}
      }
    }
  }
}
```

This schema is injected into every LLM prompt as context, enabling personalized tutoring responses.

---

## 7. Google Calendar Integration: Full CRUD Specification

### Required Scopes
```python
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",  # Read/write events
    "https://www.googleapis.com/auth/tasks",             # Task management
]
```

### API Operations

| Operation | Method | Use Case |
|-----------|--------|----------|
| List Events | `events().list()` | Check availability, show agenda |
| Create Event | `events().insert()` | Book study session |
| Update Event | `events().update()` | Reschedule session |
| Delete Event | `events().delete()` | Cancel session |
| List Tasks | `tasks().list()` | Show pending tasks |
| Create Task | `tasks().insert()` | Add "Study X before exam" |

### Smart Scheduling Algorithm

```python
def auto_schedule_week(persona: LearnerPersona, mastery: MasteryData) -> List[CalendarEvent]:
    """
    Generate optimized study schedule based on:
    1. Learner's chronotype (when they learn best)
    2. Current mastery gaps (what needs work)
    3. Existing calendar (what's available)
    4. Cognitive load theory (session timing)
    """

    events = []
    free_slots = get_free_slots(days=7)

    for slot in free_slots:
        # Determine optimal activity type for this time
        hour = slot.start.hour

        if is_peak_hour(hour, persona):
            # Morning peak → High cognitive load (Parsons, Numeric)
            activity_type = "deep_work"
            modules = mastery.weakest_modules[:3]
            duration = 60
        elif is_low_energy_hour(hour, persona):
            # Afternoon dip → Low cognitive load (Flashcards)
            activity_type = "maintenance"
            modules = list(range(1, 18))
            duration = 20
        else:
            # Evening → Consolidation (Review before sleep)
            activity_type = "review"
            modules = mastery.recently_learned
            duration = 15

        events.append(create_study_event(
            start=slot.start,
            duration=duration,
            type=activity_type,
            modules=modules,
            title=f"Cortex {activity_type.replace('_', ' ').title()}"
        ))

    return events
```

---

## 8. Vertex AI Integration: Gemini Configuration

### Model Selection

| Task | Model | Reasoning |
|------|-------|-----------|
| Remediation explanations | `gemini-1.5-flash` | Fast, good for short explanations |
| Project generation | `gemini-1.5-pro` | Better at structured outputs |
| Knowledge extraction | `gemini-1.5-pro` | Handles long context (Spivak chapters) |
| Quick encouragement | `gemini-1.5-flash` | Latency-sensitive |

### System Prompt Template

```python
CORTEX_SYSTEM_PROMPT = """
You are CORTEX, an AI tutor embedded in an advanced learning system.

LEARNER CONTEXT:
{persona.to_prompt_context()}

CURRENT SESSION:
- Mode: {session.mode}
- Accuracy so far: {session.accuracy}%
- Cognitive state: {session.cognitive_state}
- Recent struggles: {session.recent_failures}

YOUR ROLE:
1. Provide Socratic guidance, not direct answers
2. Match explanation style to learner profile
3. Be brief (3-4 sentences max unless asked)
4. When the learner fails, diagnose the cognitive failure mode
5. Always end with a thought-provoking question

COMMUNICATION STYLE:
- Cyberpunk/Neural network themed vocabulary
- Use phrases like "pattern lock", "neural pathway", "cognitive subroutine"
- Be encouraging but not patronizing
"""
```

---

## Conclusion: The Cortex as Cognitive Prosthesis

This architecture positions Cortex not as a replacement for human learning, but as a **cognitive prosthesis** that:

1. **Diagnoses** learning failures at the neural system level
2. **Prescribes** targeted remediation based on cognitive science
3. **Schedules** learning to align with biological rhythms
4. **Generates** personalized projects to synthesize knowledge
5. **Evolves** a learner persona that the AI uses for personalization

The key innovation is the synthesis of three typically separate fields:
- **AI/ML** (DKT, RL, LLMs)
- **Neuroscience** (P-FIT, Pattern Separation, Perceptual Learning)
- **Learning Science** (Spacing, Interleaving, Desirable Difficulties)

By grounding every design decision in research, the system achieves the PhD-level rigor the user requested while remaining implementable with current technology.
