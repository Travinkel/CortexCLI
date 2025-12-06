"""
Automated Quality Evaluation for Learning Atoms (AutoSxS).

Implements a two-model evaluation pipeline:
1. Generator Model (Flash): Creates learning atoms quickly
2. Evaluator Model (Pro): Grades the atoms against quality rubric

Based on Vertex AI Evaluation Service best practices:
- Custom metrics/rubrics for domain-specific quality
- Automatic regeneration loop for failed atoms
- Adversarial distractor generation for MCQs
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger

from config import get_settings
from src.generation.schemas import (
    QUALITY_RUBRIC_SCHEMA,
    get_evaluation_config,
    validate_against_schema,
)


class EvaluationVerdict(str, Enum):
    """Verdict from quality evaluation."""
    APPROVE = "approve"  # Ready for production
    REVISE = "revise"    # Needs regeneration with feedback
    REJECT = "reject"    # Cannot be fixed, discard


@dataclass
class CriteriaScores:
    """Scores for each evaluation criterion."""
    accuracy: int = 0       # 1-5: Is content factually correct?
    completeness: int = 0   # 1-5: Is answer complete (not truncated)?
    clarity: int = 0        # 1-5: Is question clear and unambiguous?
    atomicity: int = 0      # 1-5: Does it test exactly one concept?
    answerability: int = 0  # 1-5: Can question be answered from content alone?

    @property
    def average(self) -> float:
        """Calculate average score."""
        scores = [self.accuracy, self.completeness, self.clarity, self.atomicity, self.answerability]
        return sum(scores) / len(scores) if all(scores) else 0


@dataclass
class EvaluationResult:
    """Result of evaluating a learning atom."""
    overall_score: int  # 1-5
    criteria: CriteriaScores
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    verdict: EvaluationVerdict = EvaluationVerdict.REVISE

    @property
    def should_approve(self) -> bool:
        return self.verdict == EvaluationVerdict.APPROVE

    @property
    def can_revise(self) -> bool:
        return self.verdict == EvaluationVerdict.REVISE


@dataclass
class DistractorAnalysis:
    """Analysis of MCQ distractors."""
    distractor: str
    misconception: str  # Why a learner might choose this
    why_wrong: str      # Why it's technically incorrect
    plausibility_score: int  # 1-5


class AutoEvaluator:
    """
    Automated quality evaluator using a secondary LLM.

    Uses a stronger model (Pro) to evaluate outputs from the generator (Flash),
    implementing the AutoSxS pattern from Vertex AI.

    Evaluation criteria based on learning science:
    1. Accuracy - Is the content factually correct?
    2. Completeness - Is the answer complete (not truncated)?
    3. Clarity - Is the question clear and unambiguous?
    4. Atomicity - Does it test exactly one concept?
    5. Answerability - Can the question be answered from the content alone?
    """

    # Score thresholds
    APPROVE_THRESHOLD = 4.0  # Average score >= 4.0 to approve
    REJECT_THRESHOLD = 2.0   # Average score < 2.0 to reject

    def __init__(
        self,
        api_key: Optional[str] = None,
        evaluator_model: str = "gemini-1.5-pro",  # Stronger model for evaluation
    ):
        """
        Initialize the evaluator.

        Args:
            api_key: Gemini API key
            evaluator_model: Model to use for evaluation (should be stronger than generator)
        """
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.evaluator_model = evaluator_model
        self._client = None

    @property
    def client(self):
        """Lazy-load Gemini client for evaluation."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(
                model_name=self.evaluator_model,
                system_instruction=self._get_evaluator_system_prompt(),
            )
        return self._client

    def _get_evaluator_system_prompt(self) -> str:
        """System prompt for the evaluator model."""
        return """You are an expert Quality Assurance specialist for educational content.

Your task is to evaluate learning atoms (flashcards, quiz questions) against strict quality criteria.

EVALUATION CRITERIA (each scored 1-5):

1. ACCURACY (Is the content factually correct?)
   - 5: Completely accurate, matches authoritative sources
   - 4: Accurate with minor simplifications
   - 3: Mostly accurate, one minor error
   - 2: Contains significant inaccuracy
   - 1: Fundamentally incorrect

2. COMPLETENESS (Is the answer complete?)
   - 5: Fully complete, proper ending punctuation
   - 4: Complete, slight room for more context
   - 3: Adequate but missing some context
   - 2: Incomplete, ends awkwardly or mid-sentence
   - 1: Severely truncated or empty

3. CLARITY (Is the question clear?)
   - 5: Crystal clear, no ambiguity
   - 4: Clear with minor room for improvement
   - 3: Understandable but could be clearer
   - 2: Ambiguous or confusing
   - 1: Incomprehensible or garbled

4. ATOMICITY (Does it test one concept?)
   - 5: Tests exactly one atomic fact
   - 4: One main concept, minor related detail
   - 3: Two related concepts
   - 2: Multiple unrelated concepts
   - 1: Covers entire topic

5. ANSWERABILITY (Can it be answered from content alone?)
   - 5: Fully answerable from typical curriculum
   - 4: Answerable with reasonable domain knowledge
   - 3: Requires some inference
   - 2: Requires significant outside knowledge
   - 1: Cannot be answered without external sources

VERDICT GUIDELINES:
- APPROVE: Average score >= 4.0 AND no criterion below 3
- REVISE: Average score 2.0-3.9 OR any criterion 2-3
- REJECT: Average score < 2.0 OR any criterion is 1

Always provide specific, actionable recommendations for improvement."""

    async def evaluate_atom(
        self,
        atom_type: str,
        front: str,
        back: str,
        content_json: Optional[dict] = None,
        source_content: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Evaluate a single learning atom.

        Args:
            atom_type: Type of atom (flashcard, mcq, etc.)
            front: Question/prompt text
            back: Answer text
            content_json: Type-specific content (options, pairs, etc.)
            source_content: Original source for accuracy check

        Returns:
            EvaluationResult with scores and verdict
        """
        prompt = self._build_evaluation_prompt(
            atom_type=atom_type,
            front=front,
            back=back,
            content_json=content_json,
            source_content=source_content,
        )

        try:
            response = await self._call_evaluator(prompt)
            return self._parse_evaluation(response)
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # Return a default "needs review" result
            return EvaluationResult(
                overall_score=3,
                criteria=CriteriaScores(3, 3, 3, 3, 3),
                issues=["Evaluation failed - manual review required"],
                verdict=EvaluationVerdict.REVISE,
            )

    def _build_evaluation_prompt(
        self,
        atom_type: str,
        front: str,
        back: str,
        content_json: Optional[dict],
        source_content: Optional[str],
    ) -> str:
        """Build the evaluation prompt."""
        prompt_parts = [
            "Evaluate this learning atom for quality.",
            f"\nATOM TYPE: {atom_type}",
            f"\nQUESTION/PROMPT:\n{front}",
            f"\nANSWER:\n{back}",
        ]

        if content_json:
            prompt_parts.append(f"\nADDITIONAL CONTENT:\n{json.dumps(content_json, indent=2)}")

        if source_content:
            # Truncate source to reasonable length
            source_excerpt = source_content[:1500]
            prompt_parts.append(f"\nSOURCE CONTENT (for accuracy check):\n{source_excerpt}")

        prompt_parts.append("""
Return your evaluation as JSON:
{
  "overall_score": 1-5,
  "criteria": {
    "accuracy": 1-5,
    "completeness": 1-5,
    "clarity": 1-5,
    "atomicity": 1-5,
    "answerability": 1-5
  },
  "issues": ["specific issue 1", "specific issue 2"],
  "recommendations": ["how to fix 1", "how to fix 2"],
  "verdict": "approve" | "revise" | "reject"
}""")

        return "\n".join(prompt_parts)

    async def _call_evaluator(self, prompt: str) -> str:
        """Call the evaluator model."""
        response = self.client.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,  # Very deterministic for evaluation
                "top_p": 0.8,
                "max_output_tokens": 1024,
            },
        )

        if response.text:
            return response.text

        raise ValueError("Empty response from evaluator")

    def _parse_evaluation(self, response: str) -> EvaluationResult:
        """Parse evaluator response into EvaluationResult."""
        # Extract JSON
        json_match = re.search(r"\{[\s\S]*\}", response)
        if not json_match:
            raise ValueError("No JSON found in evaluation response")

        data = json.loads(json_match.group(0))

        criteria_data = data.get("criteria", {})
        criteria = CriteriaScores(
            accuracy=criteria_data.get("accuracy", 3),
            completeness=criteria_data.get("completeness", 3),
            clarity=criteria_data.get("clarity", 3),
            atomicity=criteria_data.get("atomicity", 3),
            answerability=criteria_data.get("answerability", 3),
        )

        verdict_str = data.get("verdict", "revise").lower()
        try:
            verdict = EvaluationVerdict(verdict_str)
        except ValueError:
            verdict = EvaluationVerdict.REVISE

        return EvaluationResult(
            overall_score=data.get("overall_score", 3),
            criteria=criteria,
            issues=data.get("issues", []),
            recommendations=data.get("recommendations", []),
            verdict=verdict,
        )

    async def generate_distractors(
        self,
        question: str,
        correct_answer: str,
        num_distractors: int = 3,
    ) -> list[DistractorAnalysis]:
        """
        Generate high-quality distractors for MCQ questions.

        Uses chain-of-thought prompting to create plausible but incorrect answers
        with explanations of common misconceptions.

        Args:
            question: The MCQ question stem
            correct_answer: The correct answer
            num_distractors: Number of distractors to generate

        Returns:
            List of DistractorAnalysis with misconception explanations
        """
        prompt = f"""Generate {num_distractors} wrong answers (distractors) for this multiple choice question.

QUESTION: {question}
CORRECT ANSWER: {correct_answer}

For each distractor, think step-by-step:
1. What misconception might lead a learner to choose this?
2. Why is it technically incorrect?
3. How plausible is it (1-5)?

The best distractors are:
- Plausible to someone who partially understands the topic
- Based on real misconceptions, not random wrong answers
- Similar in length and style to the correct answer
- Clearly incorrect to someone with full understanding

Return as JSON array:
[
  {{
    "distractor": "the wrong answer text",
    "misconception": "why a learner might choose this",
    "why_wrong": "why it's technically incorrect",
    "plausibility_score": 1-5
  }}
]"""

        try:
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.5,  # Slightly creative for variety
                    "max_output_tokens": 1024,
                },
            )

            if response.text:
                json_match = re.search(r"\[[\s\S]*\]", response.text)
                if json_match:
                    data = json.loads(json_match.group(0))
                    return [
                        DistractorAnalysis(
                            distractor=d.get("distractor", ""),
                            misconception=d.get("misconception", ""),
                            why_wrong=d.get("why_wrong", ""),
                            plausibility_score=d.get("plausibility_score", 3),
                        )
                        for d in data
                    ]

        except Exception as e:
            logger.error(f"Distractor generation failed: {e}")

        return []

    async def batch_evaluate(
        self,
        atoms: list[dict],
        source_content: Optional[str] = None,
    ) -> list[EvaluationResult]:
        """
        Evaluate a batch of atoms.

        Args:
            atoms: List of atom dicts with atom_type, front, back, content_json
            source_content: Optional source content for accuracy check

        Returns:
            List of EvaluationResults
        """
        results = []
        for atom in atoms:
            result = await self.evaluate_atom(
                atom_type=atom.get("atom_type", "flashcard"),
                front=atom.get("front", ""),
                back=atom.get("back", ""),
                content_json=atom.get("content_json"),
                source_content=source_content,
            )
            results.append(result)
        return results


# =============================================================================
# Regeneration Loop
# =============================================================================

async def evaluate_and_regenerate(
    generator,  # RobustAtomGenerator instance
    evaluator: AutoEvaluator,
    atom: dict,
    source_content: str,
    max_attempts: int = 3,
) -> tuple[dict, EvaluationResult]:
    """
    Evaluate an atom and regenerate if needed.

    Implements the feedback loop:
    1. Evaluate atom
    2. If verdict is REVISE, regenerate with feedback
    3. Repeat until APPROVE or max attempts reached
    4. Return final atom and evaluation

    Args:
        generator: The atom generator instance
        evaluator: The evaluator instance
        atom: The atom to evaluate
        source_content: Source content for context
        max_attempts: Maximum regeneration attempts

    Returns:
        Tuple of (final_atom, evaluation_result)
    """
    current_atom = atom
    evaluation = None

    for attempt in range(max_attempts):
        # Evaluate current atom
        evaluation = await evaluator.evaluate_atom(
            atom_type=current_atom.get("atom_type", "flashcard"),
            front=current_atom.get("front", ""),
            back=current_atom.get("back", ""),
            content_json=current_atom.get("content_json"),
            source_content=source_content,
        )

        if evaluation.should_approve:
            logger.info(f"Atom approved after {attempt + 1} attempt(s)")
            return current_atom, evaluation

        if evaluation.verdict == EvaluationVerdict.REJECT:
            logger.warning(f"Atom rejected, cannot be fixed")
            return current_atom, evaluation

        if attempt < max_attempts - 1:
            # Generate revision prompt with feedback
            feedback = "\n".join([
                "Previous issues:",
                *[f"- {issue}" for issue in evaluation.issues],
                "",
                "Recommendations:",
                *[f"- {rec}" for rec in evaluation.recommendations],
            ])

            logger.info(f"Regenerating atom (attempt {attempt + 2})")
            # Here you would call generator.regenerate_with_feedback()
            # For now, we'll just return after first evaluation
            break

    return current_atom, evaluation


# =============================================================================
# Quality Metrics Summary
# =============================================================================

def summarize_evaluations(results: list[EvaluationResult]) -> dict:
    """
    Summarize a batch of evaluation results.

    Returns:
        Dict with statistics and grade distribution
    """
    if not results:
        return {"total": 0}

    total = len(results)
    approved = sum(1 for r in results if r.verdict == EvaluationVerdict.APPROVE)
    revised = sum(1 for r in results if r.verdict == EvaluationVerdict.REVISE)
    rejected = sum(1 for r in results if r.verdict == EvaluationVerdict.REJECT)

    avg_overall = sum(r.overall_score for r in results) / total
    avg_accuracy = sum(r.criteria.accuracy for r in results) / total
    avg_completeness = sum(r.criteria.completeness for r in results) / total
    avg_clarity = sum(r.criteria.clarity for r in results) / total
    avg_atomicity = sum(r.criteria.atomicity for r in results) / total
    avg_answerability = sum(r.criteria.answerability for r in results) / total

    # Collect all issues
    all_issues = {}
    for r in results:
        for issue in r.issues:
            all_issues[issue] = all_issues.get(issue, 0) + 1

    return {
        "total": total,
        "approved": approved,
        "revised": revised,
        "rejected": rejected,
        "approval_rate": approved / total * 100,
        "averages": {
            "overall": round(avg_overall, 2),
            "accuracy": round(avg_accuracy, 2),
            "completeness": round(avg_completeness, 2),
            "clarity": round(avg_clarity, 2),
            "atomicity": round(avg_atomicity, 2),
            "answerability": round(avg_answerability, 2),
        },
        "top_issues": sorted(all_issues.items(), key=lambda x: -x[1])[:10],
    }


# =============================================================================
# CLI Test
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        evaluator = AutoEvaluator()

        # Test evaluation
        test_atoms = [
            {
                "atom_type": "flashcard",
                "front": "What is the purpose of a default gateway in IP networking?",
                "back": "The default gateway is a router interface that forwards packets destined for networks outside the local subnet to remote destinations.",
            },
            {
                "atom_type": "flashcard",
                "front": "In networking, what circuits The circuits?",
                "back": "Something about circuits",
            },
            {
                "atom_type": "flashcard",
                "front": "What is Business DSL?",
                "back": "Business DSL is",
            },
        ]

        print("\n=== Auto Evaluation Test ===\n")

        for atom in test_atoms:
            result = await evaluator.evaluate_atom(
                atom_type=atom["atom_type"],
                front=atom["front"],
                back=atom["back"],
            )

            print(f"Q: {atom['front'][:60]}...")
            print(f"A: {atom['back'][:60]}...")
            print(f"Score: {result.overall_score}/5 - {result.verdict.value.upper()}")
            print(f"Criteria: Acc={result.criteria.accuracy}, "
                  f"Comp={result.criteria.completeness}, "
                  f"Clar={result.criteria.clarity}, "
                  f"Atom={result.criteria.atomicity}, "
                  f"Ans={result.criteria.answerability}")
            if result.issues:
                print(f"Issues: {result.issues}")
            print()

    asyncio.run(test())
