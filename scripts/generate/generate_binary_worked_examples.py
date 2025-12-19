"""
Generate worked examples for binary-decimal subnet calculations.

These show step-by-step reasoning to build procedural fluency.
"""
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_worked_examples():
    """Generate worked example flashcards."""
    atoms = []

    # Example 1: Find last usable host (the original struggle)
    atoms.append({
        "card_id": "WORK-BIN-001",
        "front": "Find the last usable host address in 192.168.10.0/24.\n\nShow the binary reasoning.",
        "back": """Step 1: /24 means 8 host bits (32 - 24 = 8)

Step 2: Calculate broadcast (all host bits = 1)
   Host portion: 11111111 = 255
   Broadcast: 192.168.10.255

Step 3: Last usable = Broadcast - 1
   11111111 - 1 = 11111110 = 254

ANSWER: 192.168.10.254""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "last-usable"],
    })

    # Example 2: Find first usable host
    atoms.append({
        "card_id": "WORK-BIN-002",
        "front": "Find the first usable host address in 10.0.0.0/8.\n\nShow the binary reasoning.",
        "back": """Step 1: /8 means 24 host bits (32 - 8 = 24)

Step 2: Network address = all host bits = 0
   Host portion: 00000000.00000000.00000000 = 0.0.0
   Network: 10.0.0.0

Step 3: First usable = Network + 1
   00000000.00000000.00000001 = 0.0.1

ANSWER: 10.0.0.1""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "first-usable"],
    })

    # Example 3: /25 subnet - non-octet boundary
    atoms.append({
        "card_id": "WORK-BIN-003",
        "front": "Find the broadcast address for 172.16.5.64/26.\n\nShow the binary reasoning.",
        "back": """Step 1: /26 means 6 host bits (32 - 26 = 6)

Step 2: Convert 64 to binary: 01000000
   Network portion (first 2 bits): 01
   Host portion (last 6 bits): 000000

Step 3: Broadcast = set all host bits to 1
   01 + 111111 = 01111111 = 127

ANSWER: 172.16.5.127""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "broadcast"],
    })

    # Example 4: Subnet mask to CIDR
    atoms.append({
        "card_id": "WORK-BIN-004",
        "front": "Convert subnet mask 255.255.255.192 to CIDR notation.\n\nShow the binary reasoning.",
        "back": """Step 1: Convert each octet to binary
   255 = 11111111
   255 = 11111111
   255 = 11111111
   192 = 11000000

Step 2: Count contiguous 1s
   11111111.11111111.11111111.11000000
   8 + 8 + 8 + 2 = 26 ones

ANSWER: /26""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "cidr"],
    })

    # Example 5: Calculate number of hosts
    atoms.append({
        "card_id": "WORK-BIN-005",
        "front": "How many usable hosts in a /27 network?\n\nShow the calculation.",
        "back": """Step 1: Calculate host bits
   32 - 27 = 5 host bits

Step 2: Calculate total addresses
   2^5 = 32 addresses

Step 3: Subtract network and broadcast
   32 - 2 = 30 usable hosts

Binary confirmation:
   /27 mask last octet = 11100000 = 224
   Block size = 256 - 224 = 32

ANSWER: 30 usable hosts""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "host-count"],
    })

    # Example 6: Find network address
    atoms.append({
        "card_id": "WORK-BIN-006",
        "front": "What is the network address for host 192.168.1.137/25?\n\nShow the binary reasoning.",
        "back": """Step 1: /25 means 7 host bits
   Mask: 255.255.255.128 (10000000)

Step 2: Convert 137 to binary
   137 = 10001001

Step 3: AND with mask to find network
   10001001 (137)
   10000000 (mask)
   --------
   10000000 = 128

ANSWER: 192.168.1.128""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "network-address"],
    })

    # Example 7: Quick mental math for common values
    atoms.append({
        "card_id": "WORK-BIN-007",
        "front": "Memorize: What are the subnet mask values for these CIDR notations?\n/25, /26, /27, /28, /29, /30",
        "back": """CIDR to 4th Octet Mask (memorize these!):

/25 = 128  (10000000)  - 128 hosts
/26 = 192  (11000000)  - 64 hosts
/27 = 224  (11100000)  - 32 hosts
/28 = 240  (11110000)  - 16 hosts
/29 = 248  (11111000)  - 8 hosts
/30 = 252  (11111100)  - 4 hosts

Pattern: Each additional bit doubles the mask value:
128 -> 192 -> 224 -> 240 -> 248 -> 252 -> 254""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "memorization"],
    })

    # Example 8: 254 vs 255 explicit
    atoms.append({
        "card_id": "WORK-BIN-008",
        "front": "Why is 254 the last usable host and not 255?\n\nExplain with binary.",
        "back": """Binary breakdown:

255 = 11111111 (ALL bits ON)
   = All host bits set to 1
   = BROADCAST address (reserved)

254 = 11111110 (last bit OFF)
   = 255 - 1
   = Last USABLE host address

Key insight:
- Network = all host bits 0
- Broadcast = all host bits 1
- Usable range = Network+1 to Broadcast-1

In /24: .1 to .254 are usable (254 hosts)
        .0 = network, .255 = broadcast""",
        "atom_type": "flashcard",
        "ccna_section_id": "11.4",
        "source": "binary_worked_examples",
        "tags": ["binary", "subnet", "worked-example", "255-vs-254"],
    })

    output_file = OUTPUT_DIR / "binary_worked_examples.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(atoms, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(atoms)} worked example atoms")
    print(f"Saved to: {output_file}")

    return atoms


if __name__ == "__main__":
    generate_worked_examples()
