"""
Generate PLM (Perceptual Learning Module) drills for binary-decimal transfer.

Target: Automate the binary<->decimal conversion that underlies subnet calculations.
Focus pairs:
- 255 vs 254 (broadcast vs last usable)
- 128 vs 127 (MSB boundary)
- 192 vs 191 (/26 boundary)
- 63 vs 64 (subnet boundary)
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Critical subnet boundary values
PLM_PAIRS = [
    # (decimal, binary, significance)
    (255, "11111111", "broadcast/all-ones"),
    (254, "11111110", "last usable host"),
    (128, "10000000", "MSB only / half"),
    (127, "01111111", "all but MSB"),
    (192, "11000000", "/26 mask or Class C range"),
    (191, "10111111", "just below /26"),
    (64, "01000000", "subnet boundary"),
    (63, "00111111", "below subnet boundary"),
    (0, "00000000", "network/all-zeros"),
    (1, "00000001", "first usable host"),
    (224, "11100000", "/27 mask or multicast"),
    (223, "11011111", "just below /27"),
    (240, "11110000", "/28 mask"),
    (248, "11111000", "/29 mask"),
    (252, "11111100", "/30 mask"),
]


def generate_decimal_to_binary():
    """Generate decimal -> binary drills."""
    atoms = []
    for dec, binary, significance in PLM_PAIRS:
        atom = {
            "card_id": f"PLM-BIN-D2B-{dec:03d}",
            "front": f"Convert to binary: {dec}",
            "back": binary,
            "atom_type": "numeric",
            "ccna_section_id": "11.4",
            "source": "plm_binary_drills",
            "plm_target_ms": 1000,
            "tags": ["binary", "decimal", "plm", "subnet-math"],
            "metadata": {
                "significance": significance,
                "drill_type": "decimal_to_binary"
            }
        }
        atoms.append(atom)
    return atoms


def generate_binary_to_decimal():
    """Generate binary -> decimal drills."""
    atoms = []
    for dec, binary, significance in PLM_PAIRS:
        atom = {
            "card_id": f"PLM-BIN-B2D-{dec:03d}",
            "front": f"Convert to decimal: {binary}",
            "back": str(dec),
            "atom_type": "numeric",
            "ccna_section_id": "11.4",
            "source": "plm_binary_drills",
            "plm_target_ms": 1000,
            "tags": ["binary", "decimal", "plm", "subnet-math"],
            "metadata": {
                "significance": significance,
                "drill_type": "binary_to_decimal"
            }
        }
        atoms.append(atom)
    return atoms


def generate_discrimination_mcqs():
    """Generate MCQs testing critical discriminations."""
    atoms = []

    # 255 vs 254 - broadcast vs last usable
    atoms.append({
        "card_id": "PLM-BIN-MCQ-001",
        "front": "In a /24 network, which decimal value represents the BROADCAST address host portion?",
        "back": json.dumps({
            "options": ["254", "255", "256", "0"],
            "correct": 1,
            "explanation": "255 (11111111) = all host bits ON = broadcast. 254 (11111110) = last usable host."
        }),
        "atom_type": "mcq",
        "ccna_section_id": "11.4",
        "source": "plm_binary_drills",
        "plm_target_ms": 2000,
        "tags": ["binary", "subnet", "plm", "discrimination"],
    })

    atoms.append({
        "card_id": "PLM-BIN-MCQ-002",
        "front": "In a /24 network, which decimal value represents the LAST USABLE HOST address host portion?",
        "back": json.dumps({
            "options": ["255", "254", "253", "1"],
            "correct": 1,
            "explanation": "254 (11111110) = last usable. 255 (11111111) = broadcast."
        }),
        "atom_type": "mcq",
        "ccna_section_id": "11.4",
        "source": "plm_binary_drills",
        "plm_target_ms": 2000,
        "tags": ["binary", "subnet", "plm", "discrimination"],
    })

    # Binary pattern recognition
    atoms.append({
        "card_id": "PLM-BIN-MCQ-003",
        "front": "Which binary pattern represents 255?",
        "back": json.dumps({
            "options": ["11111110", "11111111", "11111100", "10000000"],
            "correct": 1,
            "explanation": "255 = all 8 bits ON = 11111111"
        }),
        "atom_type": "mcq",
        "ccna_section_id": "11.4",
        "source": "plm_binary_drills",
        "plm_target_ms": 1500,
        "tags": ["binary", "plm"],
    })

    atoms.append({
        "card_id": "PLM-BIN-MCQ-004",
        "front": "What is 11111110 in decimal?",
        "back": json.dumps({
            "options": ["255", "254", "253", "252"],
            "correct": 1,
            "explanation": "11111110 = 128+64+32+16+8+4+2 = 254 (last bit OFF)"
        }),
        "atom_type": "mcq",
        "ccna_section_id": "11.4",
        "source": "plm_binary_drills",
        "plm_target_ms": 1500,
        "tags": ["binary", "plm"],
    })

    # Subnet mask recognition
    atoms.append({
        "card_id": "PLM-BIN-MCQ-005",
        "front": "Which decimal value appears in the 4th octet of a /25 subnet mask?",
        "back": json.dumps({
            "options": ["0", "128", "192", "255"],
            "correct": 1,
            "explanation": "/25 = 255.255.255.128. 25 bits = 24 + 1 more bit. 10000000 = 128"
        }),
        "atom_type": "mcq",
        "ccna_section_id": "11.4",
        "source": "plm_binary_drills",
        "plm_target_ms": 2000,
        "tags": ["subnet", "mask", "plm"],
    })

    atoms.append({
        "card_id": "PLM-BIN-MCQ-006",
        "front": "Which decimal value appears in the 4th octet of a /26 subnet mask?",
        "back": json.dumps({
            "options": ["128", "192", "224", "240"],
            "correct": 1,
            "explanation": "/26 = 255.255.255.192. 26 bits = 24 + 2 more bits. 11000000 = 192"
        }),
        "atom_type": "mcq",
        "ccna_section_id": "11.4",
        "source": "plm_binary_drills",
        "plm_target_ms": 2000,
        "tags": ["subnet", "mask", "plm"],
    })

    return atoms


def generate_all():
    """Generate all PLM drills."""
    all_atoms = []
    all_atoms.extend(generate_decimal_to_binary())
    all_atoms.extend(generate_binary_to_decimal())
    all_atoms.extend(generate_discrimination_mcqs())

    output_file = OUTPUT_DIR / "binary_plm_drills.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2)

    print(f"Generated {len(all_atoms)} PLM binary drill atoms")
    print(f"  - Decimal to Binary: {len(PLM_PAIRS)}")
    print(f"  - Binary to Decimal: {len(PLM_PAIRS)}")
    print(f"  - Discrimination MCQs: {len(all_atoms) - 2*len(PLM_PAIRS)}")
    print(f"Saved to: {output_file}")

    return all_atoms


if __name__ == "__main__":
    generate_all()
