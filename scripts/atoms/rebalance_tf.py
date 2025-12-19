#!/usr/bin/env python3
"""
Rebalance TRUE/FALSE atoms to achieve 50/50 distribution.

Strategy:
1. Select TRUE atoms spread across modules/concepts
2. Generate FALSE versions using negation patterns
3. Update database with converted atoms

Negation patterns:
- Term swap: "TCP is connection-oriented" -> "TCP is connectionless"
- Quantity change: "32 bits" -> "64 bits"
- Protocol swap: "OSPF uses Dijkstra" -> "OSPF uses Bellman-Ford"
- Layer swap: "operates at Layer 3" -> "operates at Layer 2"
- Negate key verb: "provides" -> "does not provide"
"""

import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import create_engine, text

from config import get_settings

# Negation patterns for networking concepts
NEGATION_PATTERNS = [
    # Protocol swaps
    (r"\bTCP\b", "UDP"),
    (r"\bUDP\b", "TCP"),
    (r"\bOSPF\b", "RIP"),
    (r"\bRIP\b", "OSPF"),
    (r"\bIPv4\b", "IPv6"),
    (r"\bIPv6\b", "IPv4"),
    # Layer swaps
    (r"Layer 1\b", "Layer 2"),
    (r"Layer 2\b", "Layer 3"),
    (r"Layer 3\b", "Layer 4"),
    (r"Layer 4\b", "Layer 7"),
    (r"Layer 7\b", "Layer 1"),
    # Quantity swaps
    (r"\b32 bits?\b", "64 bits"),
    (r"\b64 bits?\b", "32 bits"),
    (r"\b8 bits?\b", "16 bits"),
    (r"\b16 bits?\b", "8 bits"),
    (r"\b128 bits?\b", "64 bits"),
    # Device swaps
    (r"\brouter\b", "switch"),
    (r"\bswitch\b", "router"),
    (r"\bhub\b", "router"),
    # Connection type swaps
    (r"\bconnection-oriented\b", "connectionless"),
    (r"\bconnectionless\b", "connection-oriented"),
    (r"\breliable\b", "unreliable"),
    (r"\bunreliable\b", "reliable"),
    # Direction swaps
    (r"\bunicast\b", "broadcast"),
    (r"\bbroadcast\b", "unicast"),
    (r"\bmulticast\b", "unicast"),
    # Algorithm swaps
    (r"\bDijkstra\b", "Bellman-Ford"),
    (r"\bBellman-Ford\b", "Dijkstra"),
]


def apply_negation(statement: str) -> str | None:
    """
    Apply a negation pattern to convert a TRUE statement to FALSE.
    Returns None if no pattern matches.
    """
    # Try each pattern
    for pattern, replacement in NEGATION_PATTERNS:
        if re.search(pattern, statement, re.IGNORECASE):
            # Apply the replacement
            negated = re.sub(pattern, replacement, statement, count=1, flags=re.IGNORECASE)
            if negated != statement:
                return negated

    # Fallback: Try adding "not" or "does not"
    # Find key verbs and negate them
    verb_patterns = [
        (r"\bis\b", "is not"),
        (r"\bare\b", "are not"),
        (r"\bprovides\b", "does not provide"),
        (r"\buses\b", "does not use"),
        (r"\bsupports\b", "does not support"),
        (r"\bcontains\b", "does not contain"),
        (r"\boperates\b", "does not operate"),
    ]

    for pattern, replacement in verb_patterns:
        if re.search(pattern, statement, re.IGNORECASE):
            negated = re.sub(pattern, replacement, statement, count=1, flags=re.IGNORECASE)
            if negated != statement:
                return negated

    return None


def get_true_atoms_for_conversion(conn, target_count: int) -> list:
    """
    Select TRUE atoms to convert, spread across modules/concepts.
    """
    result = conn.execute(
        text("""
        SELECT ca.id, ca.front, ca.back, ca.concept_id, cs.module_number
        FROM clean_atoms ca
        LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type = 'true_false'
    """)
    )

    true_atoms = []
    for row in result:
        try:
            data = json.loads(row.back)
            if data.get("answer"):
                true_atoms.append(
                    {
                        "id": str(row.id),
                        "front": row.front,
                        "back": row.back,
                        "concept_id": str(row.concept_id) if row.concept_id else None,
                        "module": row.module_number,
                    }
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Shuffle and select
    random.shuffle(true_atoms)

    # Try to spread across modules
    by_module = {}
    for atom in true_atoms:
        mod = atom.get("module") or 0
        if mod not in by_module:
            by_module[mod] = []
        by_module[mod].append(atom)

    # Select proportionally from each module
    selected = []
    total_true = len(true_atoms)
    for mod, atoms in sorted(by_module.items()):
        proportion = len(atoms) / total_true
        to_select = int(target_count * proportion) + 1
        selected.extend(atoms[:to_select])

    return selected[:target_count]


def main():
    """Rebalance TRUE/FALSE atoms."""
    logger.info("Starting TRUE/FALSE rebalancing...")

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        # Get current distribution
        result = conn.execute(
            text("""
            SELECT back FROM clean_atoms WHERE atom_type = 'true_false'
        """)
        )

        true_count = 0
        false_count = 0
        for row in result:
            try:
                data = json.loads(row.back)
                if data.get("answer"):
                    true_count += 1
                else:
                    false_count += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        total = true_count + false_count
        logger.info(
            f"Current distribution: TRUE={true_count} ({100 * true_count / total:.1f}%), FALSE={false_count} ({100 * false_count / total:.1f}%)"
        )

        # Calculate how many to convert
        target_each = total // 2
        to_convert = true_count - target_each

        if to_convert <= 0:
            logger.info("Already balanced or FALSE-heavy. No conversion needed.")
            return

        logger.info(f"Need to convert {to_convert} TRUE atoms to FALSE")

        # Get atoms for conversion
        atoms = get_true_atoms_for_conversion(conn, to_convert)
        logger.info(f"Selected {len(atoms)} atoms for conversion")

        # Convert each atom
        converted = 0
        failed = 0

        for atom in atoms:
            front = atom["front"]

            # Remove "True or False: " prefix if present
            clean_front = front
            if clean_front.lower().startswith("true or false:"):
                clean_front = clean_front[14:].strip()

            # Apply negation
            negated = apply_negation(clean_front)

            if negated:
                # Reconstruct with prefix
                new_front = f"True or False: {negated}"
                new_back = json.dumps(
                    {
                        "answer": False,
                        "explanation": "This statement has been modified to be false for assessment purposes.",
                    }
                )

                # Update database
                conn.execute(
                    text("""
                    UPDATE clean_atoms
                    SET front = :front, back = :back
                    WHERE id = :id
                """),
                    {"front": new_front, "back": new_back, "id": atom["id"]},
                )

                converted += 1

                if converted % 100 == 0:
                    logger.info(f"  Converted {converted}/{len(atoms)} atoms...")
            else:
                failed += 1

        conn.commit()

        logger.info("\nConversion complete:")
        logger.info(f"  Successfully converted: {converted}")
        logger.info(f"  Failed (no pattern match): {failed}")

        # Verify new distribution
        result = conn.execute(
            text("""
            SELECT back FROM clean_atoms WHERE atom_type = 'true_false'
        """)
        )

        new_true = 0
        new_false = 0
        for row in result:
            try:
                data = json.loads(row.back)
                if data.get("answer"):
                    new_true += 1
                else:
                    new_false += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        new_total = new_true + new_false
        logger.info(
            f"\nNew distribution: TRUE={new_true} ({100 * new_true / new_total:.1f}%), FALSE={new_false} ({100 * new_false / new_total:.1f}%)"
        )


if __name__ == "__main__":
    main()
