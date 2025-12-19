"""
Generate additional atoms - focusing on Parsons and more calculations.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

OUTPUT_DIR = Path("outputs/generated_atoms")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_module_content(module_num: int) -> str:
    """Load CCNA module content from text file."""
    ccna_dir = Path("docs/source-materials/CCNA")
    module_file = ccna_dir / f"CCNA Module {module_num}.txt"
    if module_file.exists():
        return module_file.read_text(encoding="utf-8")
    return ""


PARSONS_PROMPT = """Generate Cisco IOS CLI command ordering problems (Parsons problems).

TASK: Create 8 problems where the user must put CLI commands in the correct order.

CRITICAL: These are COMMAND SEQUENCES that students must order correctly.

=== EXAMPLES OF GOOD PARSONS PROBLEMS ===

Example 1 - Console Password Setup:
{{
  "card_id": "2.4-PAR-001",
  "front": "Configure console password 'cisco' on a router with login required.",
  "correct_sequence": [
    "enable",
    "configure terminal",
    "line console 0",
    "password cisco",
    "login"
  ],
  "distractors": ["line vty 0 4"],
  "explanation": "Enter privileged EXEC, then global config, then line config, set password, enable login check."
}}

Example 2 - SSH Configuration:
{{
  "card_id": "2.5-PAR-002",
  "front": "Configure SSH access on a router with domain 'cisco.com' and RSA key.",
  "correct_sequence": [
    "enable",
    "configure terminal",
    "ip domain-name cisco.com",
    "crypto key generate rsa",
    "username admin secret cisco123",
    "line vty 0 4",
    "transport input ssh",
    "login local"
  ],
  "distractors": ["transport input telnet"],
  "explanation": "Domain name must be set before RSA key generation. VTY lines need SSH transport and local authentication."
}}

Example 3 - Interface Configuration:
{{
  "card_id": "2.6-PAR-003",
  "front": "Configure interface GigabitEthernet0/0 with IP 192.168.1.1/24 and enable it.",
  "correct_sequence": [
    "enable",
    "configure terminal",
    "interface GigabitEthernet0/0",
    "ip address 192.168.1.1 255.255.255.0",
    "no shutdown"
  ],
  "distractors": ["shutdown"],
  "explanation": "Must enter interface config mode before setting IP. 'no shutdown' enables the interface."
}}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "2.X-PAR-00N",
    "front": "Task description requiring command ordering",
    "correct_sequence": ["cmd1", "cmd2", "cmd3", ...],
    "distractors": ["wrong_cmd1"],
    "explanation": "Why this order is correct"
  }}
]

Generate 8 varied CLI ordering problems covering:
- Password configuration (console, VTY, enable secret)
- SSH/Telnet setup
- Interface configuration
- Banner messages
- Service password-encryption
- Hostname configuration

CONTENT:
{content}
"""

SUBNETTING_PROMPT = """Generate subnetting calculation problems for CCNA.

Create 10 calculation-based problems with ACTUAL IP addresses and subnet calculations.

=== PROBLEM TYPES TO INCLUDE ===

1. Find Network Address:
   Q: "Given IP 192.168.50.75/26, what is the network address?"
   A: "/26 = 255.255.255.192. Block size = 64. 75 falls in the 64-127 range. Network: 192.168.50.64"

2. Find Broadcast Address:
   Q: "Given IP 172.16.35.100/27, what is the broadcast address?"
   A: "/27 = 255.255.255.224. Block size = 32. 100 falls in 96-127 range. Broadcast: 172.16.35.127"

3. Usable Host Range:
   Q: "For network 10.0.0.0/28, what is the usable host range?"
   A: "/28 = 16 addresses. Network: 10.0.0.0, Broadcast: 10.0.0.15. Usable: 10.0.0.1 to 10.0.0.14 (14 hosts)"

4. CIDR to Subnet Mask:
   Q: "Convert /22 to dotted decimal subnet mask."
   A: "/22 = 22 ones = 11111111.11111111.11111100.00000000 = 255.255.252.0"

5. Hosts per Subnet:
   Q: "How many usable hosts can a /29 subnet support?"
   A: "/29 = 3 host bits. 2^3 - 2 = 6 usable hosts"

=== OUTPUT FORMAT ===
[
  {{
    "card_id": "11.X-NUM-00N",
    "front": "Specific calculation question with IP/mask",
    "back": "Step-by-step solution showing the math",
    "calculation_type": "network_address|broadcast|host_range|cidr_conversion|host_count",
    "difficulty": 1-5
  }}
]

Generate 10 subnetting problems with increasing difficulty.

CONTENT:
{content}
"""

MATCHING_PROMPT = """Generate matching problems for OSI model and networking concepts.

Create 6 matching problems where students match terms to definitions/functions.

=== FORMAT ===
Each problem has 4-6 pairs to match.

Example:
{{
  "card_id": "3.2-MAT-001",
  "front": "Match each OSI layer to its primary function.",
  "pairs": [
    {{"term": "Physical Layer", "definition": "Transmits raw bit stream over physical medium"}},
    {{"term": "Data Link Layer", "definition": "Provides node-to-node data transfer, handles MAC addressing"}},
    {{"term": "Network Layer", "definition": "Routes packets between networks using IP addresses"}},
    {{"term": "Transport Layer", "definition": "Provides end-to-end communication, segmentation, flow control"}}
  ]
}}

=== TOPICS TO COVER ===
1. OSI Layer functions
2. PDU names per layer (Data, Segment, Packet, Frame, Bits)
3. Protocols per layer (HTTP, TCP, IP, Ethernet)
4. Device per layer (Hub, Switch, Router)
5. Addressing types (MAC vs IP)
6. Encapsulation process

=== OUTPUT FORMAT ===
[
  {{
    "card_id": "3.X-MAT-00N",
    "front": "Matching task description",
    "pairs": [
      {{"term": "Term1", "definition": "Definition1"}},
      {{"term": "Term2", "definition": "Definition2"}}
    ]
  }}
]

Generate 6 matching problems.

CONTENT:
{content}
"""


async def generate_with_prompt(prompt: str, content: str) -> list[dict]:
    """Generate atoms using custom prompt."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="You are an expert CCNA instructor. Generate high-quality learning content."
    )

    full_prompt = prompt.format(content=content[:12000])

    try:
        response = await model.generate_content_async(full_prompt)
        text = response.text

        import re
        match = re.search(r"```json\s*([\s\S]*?)```", text)
        if match:
            json_str = match.group(1).strip()
        else:
            match_list = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
            if match_list:
                json_str = match_list.group(0)
            else:
                json_str = text

        atoms = json.loads(json_str)
        return atoms if isinstance(atoms, list) else []

    except Exception as e:
        print(f"  Error: {e}")
        return []


async def main():
    print("=" * 60)
    print("GENERATING MORE ATOMS - PARSONS, SUBNETTING, MATCHING")
    print("=" * 60)

    all_atoms = []

    # =========================================================================
    # PARSONS - CLI Command Ordering (Module 2)
    # =========================================================================
    print("\n[1/3] Generating Parsons Problems (CLI Ordering)...")
    content_2 = load_module_content(2)
    if content_2:
        atoms = await generate_with_prompt(PARSONS_PROMPT, content_2)
        for a in atoms:
            a["module"] = 2
            a["atom_type"] = "parsons"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} parsons problems")
        time.sleep(5)

    # =========================================================================
    # SUBNETTING - Calculations (Module 11)
    # =========================================================================
    print("\n[2/3] Generating Subnetting Calculations...")
    content_11 = load_module_content(11)
    if content_11:
        atoms = await generate_with_prompt(SUBNETTING_PROMPT, content_11)
        for a in atoms:
            a["module"] = 11
            a["atom_type"] = "numeric"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} subnetting problems")
        time.sleep(5)

    # =========================================================================
    # MATCHING - OSI Discrimination (Module 3)
    # =========================================================================
    print("\n[3/3] Generating Matching Problems (OSI)...")
    content_3 = load_module_content(3)
    if content_3:
        atoms = await generate_with_prompt(MATCHING_PROMPT, content_3)
        for a in atoms:
            a["module"] = 3
            a["atom_type"] = "matching"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} matching problems")

    # =========================================================================
    # SAVE AND MERGE
    # =========================================================================
    # Load existing atoms
    existing_file = OUTPUT_DIR / "targeted_atoms.json"
    existing_atoms = []
    if existing_file.exists():
        with open(existing_file, "r", encoding="utf-8") as f:
            existing_atoms = json.load(f)

    # Merge
    combined = existing_atoms + all_atoms

    # Save combined
    output_file = OUTPUT_DIR / "all_generated_atoms.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Generated {len(all_atoms)} new atoms")
    print(f"Total atoms: {len(combined)}")
    print(f"Saved to: {output_file}")
    print("=" * 60)

    # Summary
    by_type = {}
    for a in combined:
        t = a.get("atom_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\nTotal Breakdown:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    asyncio.run(main())
