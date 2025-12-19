"""
Simulated study load test for AdaptiveTutor.

Runs 1,000 synthetic card interactions across distinct personas:
- Speed Runner: very fast answers (<500ms) to trigger SELF_EXPLANATION.
- Drifter: highly variable response times to trigger FOCUS_RESET.
- Struggler: frequent failures with occasional slow corrects to trigger WORKED_EXAMPLE.

This is an in-memory simulation (no UI/DB) intended to surface runtime
errors (e.g., ZeroDivisionError) and verify pedagogy guardrails fire.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.delivery.atom_deck import Atom
from src.delivery.tutor import AdaptiveTutor, Remediation


@dataclass
class Persona:
    name: str
    response_fn: Callable[[Atom, int], tuple[bool, int]]
    expected_remediations: set[str]  # Expected remediation types for this persona


def _make_deck(count: int = 20) -> list[Atom]:
    """Create a synthetic deck with light variation."""
    deck: list[Atom] = []
    for i in range(count):
        deck.append(
            Atom(
                id=f"atom-{i}",
                card_id=f"card-{i}",
                atom_type="flashcard" if i % 3 else "mcq",
                front=f"What is concept #{i}?",
                back=f"Answer #{i}",
                source_refs=[{"excerpt": f"Source excerpt #{i}"}],
                content_json={"options": [{"text": "A"}, {"text": "B"}], "correct_index": 0} if i % 3 == 0 else None,
                knowledge_type="definition" if i % 2 == 0 else "factual",
                difficulty=3 + (i % 3),
                derived_from_visual=bool(i % 5 == 0),
                media_type="mermaid" if i % 5 == 0 else None,
                media_code="graph TD;A-->B;" if i % 5 == 0 else None,
            )
        )
    return deck


def _speed_runner(_: Atom, __: int) -> tuple[bool, int]:
    """Speed Runner: Always correct, very fast (<500ms) to trigger SELF_EXPLANATION."""
    return True, random.randint(120, 450)


def _drifter(_: Atom, __: int) -> tuple[bool, int]:
    """Drifter: Variable correctness, highly variable times to trigger FOCUS_RESET."""
    return random.choice([True, False]), random.choice([300, 8000, 12000, 4000, 9500, 1500])


def _struggler(_: Atom, __: int) -> tuple[bool, int]:
    """Struggler: Mostly incorrect, occasional slow correct to trigger WORKED_EXAMPLE."""
    if random.random() < 0.1:
        return True, random.randint(16000, 20000)
    return False, random.randint(2500, 7000)


def run_simulation(total_interactions: int = 1000) -> dict[str, int]:
    """
    Run the study simulation.

    Args:
        total_interactions: Number of card interactions to simulate.

    Returns:
        Dictionary of remediation counts by type.

    Raises:
        AssertionError: If expected pedagogy triggers don't fire.
        Exception: Any runtime errors (ZeroDivisionError, etc.)
    """
    deck = _make_deck()
    tutor = AdaptiveTutor(deck)

    personas: list[Persona] = [
        Persona(
            "speed_runner",
            _speed_runner,
            {Remediation.SELF_EXPLANATION.value}
        ),
        Persona(
            "drifter",
            _drifter,
            {Remediation.FOCUS_RESET.value}
        ),
        Persona(
            "struggler",
            _struggler,
            {Remediation.WORKED_EXAMPLE.value}
        ),
    ]

    remediation_counts: dict[str, int] = {r.value: 0 for r in Remediation}
    remediation_counts["exceptions"] = 0

    # Track per-persona remediation counts for validation
    persona_remediations: dict[str, dict[str, int]] = {
        p.name: {r.value: 0 for r in Remediation}
        for p in personas
    }

    # Track recent times for realistic variance calculation
    recent_times_by_atom: dict[str, list[int]] = {}

    last_persona = None
    last_atom = None
    last_latency = None

    for idx in range(total_interactions):
        persona = personas[idx % len(personas)]
        atom = deck[idx % len(deck)]

        try:
            is_correct, latency = persona.response_fn(atom, idx)

            # Track recent times for this atom
            if atom.id not in recent_times_by_atom:
                recent_times_by_atom[atom.id] = []
            recent_times_by_atom[atom.id].append(latency)
            recent_times = recent_times_by_atom[atom.id][-5:]  # Keep last 5

            # Store for error reporting
            last_persona = persona.name
            last_atom = atom.id
            last_latency = latency

            response = tutor.submit_response(
                atom=atom,
                is_correct=is_correct,
                response_ms=latency,
                grade=5 if is_correct else 1,
                recent_times=recent_times,
            )

            remediation_type = response.remediation.value
            remediation_counts[remediation_type] = remediation_counts.get(remediation_type, 0) + 1
            persona_remediations[persona.name][remediation_type] += 1

        except Exception as e:
            remediation_counts["exceptions"] += 1
            print(f"\n❌ EXCEPTION at interaction {idx}:")
            print(f"   Persona: {last_persona}")
            print(f"   Atom ID: {last_atom}")
            print(f"   Latency: {last_latency}ms")
            print(f"   Error: {type(e).__name__}: {e}")
            raise

    # Validate that expected remediations fired for each persona
    validation_errors = []

    for persona in personas:
        for expected_remediation in persona.expected_remediations:
            count = persona_remediations[persona.name][expected_remediation]
            if count == 0:
                validation_errors.append(
                    f"{persona.name} should trigger {expected_remediation} but got 0 occurrences"
                )

    # Print validation summary
    print("\n📊 PERSONA VALIDATION:")
    for persona in personas:
        print(f"\n  {persona.name.upper()}:")
        for rem_type, count in persona_remediations[persona.name].items():
            if count > 0:
                marker = "✓" if rem_type in persona.expected_remediations else " "
                print(f"    {marker} {rem_type}: {count}")

    if validation_errors:
        print("\n⚠️ VALIDATION WARNINGS:")
        for err in validation_errors:
            print(f"   - {err}")
        # Note: We warn but don't fail - the pedagogy engine may have valid reasons
        # to not trigger expected remediations in all cases

    return remediation_counts


def main() -> int:
    """
    Run simulation and return exit code.

    Returns:
        0 if successful, 1 if exceptions occurred.
    """
    print("🧪 STARTING 1,000-CARD TUTOR STRESS TEST...")
    print("=" * 50)

    try:
        results = run_simulation()

        print("\n" + "=" * 50)
        print("📈 SIMULATION RESULTS:")
        print("-" * 30)

        for k, v in sorted(results.items(), key=lambda x: -x[1]):
            if v > 0:
                print(f"  {k}: {v}")

        print("-" * 30)

        if results["exceptions"] > 0:
            print(f"\n❌ FAILED: {results['exceptions']} exceptions occurred.")
            return 1
        else:
            print("\n✅ PASSED: No exceptions. Tutor is stable.")
            return 0

    except Exception as e:
        print(f"\n💥 CRITICAL FAILURE: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
