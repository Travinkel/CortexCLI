"""
Generate targeted drill atoms for specific failure modes.

Focus areas:
1. NUMERIC: Network vs Broadcast address (the user's critical confusion)
2. PARSONS: More CLI command sequences
3. MCQ: OSI/Protocol discrimination
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


# =============================================================================
# NUMERIC: Network vs Broadcast Address Drills
# =============================================================================
NETWORK_BROADCAST_PROMPT = """Generate calculation problems specifically about NETWORK ADDRESS vs BROADCAST ADDRESS.

CRITICAL CONTEXT: The student answered TRUE to "network address has all 1s in host portion" - this is WRONG.
They confuse network address with broadcast address. These drills MUST fix this.

=== THE RULE TO DRILL ===
- NETWORK ADDRESS: All ZEROS in host portion (e.g., 192.168.1.0/24)
- BROADCAST ADDRESS: All ONES in host portion (e.g., 192.168.1.255/24)

Memory anchor: "Network = Nothing (zeros), Broadcast = Blast to all (ones)"

=== REQUIRED PROBLEM TYPES ===

1. "Given IP X.X.X.X/Y, what is the NETWORK address?" (must calculate host bits, set to 0)
2. "Given IP X.X.X.X/Y, what is the BROADCAST address?" (must calculate host bits, set to 1)
3. "Is X.X.X.X a network, broadcast, or host address for /Y?" (classification)
4. "How many host bits in /X? What values make network vs broadcast?" (conceptual)

=== FEW-SHOT EXAMPLES ===

GOOD EXAMPLE 1 (Network Address):
Q: "Host 192.168.50.75 has subnet mask 255.255.255.192 (/26). Calculate the network address."
A: "/26 means 26 network bits, 6 host bits. Block size = 64. 75 is in the 64-127 block. Network address = 192.168.50.64 (host portion set to all zeros within that block)."

GOOD EXAMPLE 2 (Broadcast Address):
Q: "For the network 172.16.32.0/20, what is the broadcast address?"
A: "/20 = 12 host bits. The network spans 172.16.32.0 to 172.16.47.255. Broadcast = 172.16.47.255 (all host bits set to 1)."

GOOD EXAMPLE 3 (Classification):
Q: "Is 10.0.0.255 a network address, broadcast address, or valid host for 10.0.0.0/24?"
A: "It's the BROADCAST address. In /24, the last octet is all host bits. .255 = all 1s in binary = broadcast. Network would be .0, hosts are .1-.254."

GOOD EXAMPLE 4 (Conceptual):
Q: "In a /28 subnet, how many addresses are network, broadcast, and usable hosts?"
A: "/28 = 4 host bits = 16 total addresses. 1 network (all 0s), 1 broadcast (all 1s), 14 usable hosts (16-2=14)."

=== OUTPUT FORMAT ===
[
  {{
    "card_id": "11.4-NUM-0XX",
    "front": "Specific calculation with IP and mask",
    "back": "Step-by-step showing network vs broadcast logic",
    "tags": ["subnetting", "network-address", "broadcast-address"],
    "metadata": {{"difficulty": 3, "calculation_type": "network_broadcast"}}
  }}
]

Generate 12 problems: 4 network address, 4 broadcast address, 4 classification/conceptual.
Use varied subnets: /24, /25, /26, /27, /28, /29, /30, /20, /22.
"""

# =============================================================================
# PARSONS: CLI Command Sequences
# =============================================================================
CLI_PARSONS_PROMPT = """Generate Cisco IOS CLI command ordering problems (Parsons problems).

CRITICAL CONTEXT: The student missed the password encryption sequence. They need to understand:
- service password-encryption is applied AFTER setting passwords
- Commands must be in correct mode (user > privileged > global > specific config)

=== REQUIRED SEQUENCES ===

1. Password encryption flow (the one they missed):
   enable -> conf t -> line con 0 -> password X -> login -> exit -> service password-encryption

2. SSH configuration:
   enable -> conf t -> hostname -> ip domain-name -> crypto key generate rsa -> username/secret -> line vty -> transport input ssh -> login local

3. Interface IP configuration:
   enable -> conf t -> interface X -> ip address X X -> no shutdown

4. VLAN configuration:
   enable -> conf t -> vlan X -> name X -> exit -> interface X -> switchport mode access -> switchport access vlan X

5. Banner configuration:
   enable -> conf t -> banner motd # message #

6. Enable secret vs enable password:
   enable -> conf t -> enable secret X (preferred over enable password)

=== FEW-SHOT EXAMPLES ===

GOOD EXAMPLE (Password Encryption - their weakness):
{{
  "card_id": "2.4-PAR-010",
  "scenario": "Configure console password 'cisco123', require login, then encrypt ALL passwords on the device.",
  "correct_sequence": [
    "enable",
    "configure terminal",
    "line console 0",
    "password cisco123",
    "login",
    "exit",
    "service password-encryption"
  ],
  "distractors": ["service password-encryption", "login local"],
  "explanation": "CRITICAL: service password-encryption must come AFTER setting passwords. It encrypts existing plaintext passwords. If run first, there's nothing to encrypt."
}}

GOOD EXAMPLE (SSH):
{{
  "card_id": "2.5-PAR-011",
  "scenario": "Configure SSH on router R1 with domain 'company.com', RSA 1024-bit key, and local user 'admin'.",
  "correct_sequence": [
    "enable",
    "configure terminal",
    "hostname R1",
    "ip domain-name company.com",
    "crypto key generate rsa general-keys modulus 1024",
    "username admin secret cisco123",
    "line vty 0 4",
    "transport input ssh",
    "login local"
  ],
  "distractors": ["transport input telnet", "login"],
  "explanation": "Domain name MUST be set before RSA key generation. 'login local' uses local database; 'login' alone requires line password."
}}

=== OUTPUT FORMAT ===
[
  {{
    "card_id": "2.X-PAR-0XX",
    "scenario": "Clear task description",
    "correct_sequence": ["cmd1", "cmd2", ...],
    "distractors": ["wrong1", "wrong2"],
    "explanation": "Why this order matters",
    "metadata": {{"difficulty": 3, "knowledge_type": "procedural"}}
  }}
]

Generate 10 Parsons problems covering different configuration scenarios.
"""

# =============================================================================
# MCQ: OSI/Protocol Discrimination
# =============================================================================
DISCRIMINATION_MCQ_PROMPT = """Generate MCQs that test DISCRIMINATION between similar concepts.

CRITICAL: The student needs to distinguish between:
- OSI layers and their functions
- TCP vs UDP characteristics
- Network address vs Broadcast address vs Host address
- MAC address vs IP address usage
- Segment vs Packet vs Frame

=== REQUIRED DISCRIMINATION TYPES ===

1. Layer discrimination: "At which layer does X happen?"
2. Protocol discrimination: "Which protocol provides X?"
3. Address type discrimination: "What type of address is X?"
4. PDU discrimination: "What is the PDU called at layer X?"
5. Device discrimination: "Which device operates at layer X?"

=== FEW-SHOT EXAMPLES ===

GOOD EXAMPLE (Layer Discrimination):
Stem: "A router examines the destination IP address to determine the next hop. At which OSI layer is this decision made?"
Options: [
  "Network layer (Layer 3) - IP addressing and routing",
  "Data Link layer (Layer 2) - MAC addressing",
  "Transport layer (Layer 4) - port numbers",
  "Application layer (Layer 7) - user data"
]
Correct: 0
Explanation: "Routers operate at Layer 3 using IP addresses for routing decisions. Switches use Layer 2 MAC addresses."

GOOD EXAMPLE (Protocol Discrimination):
Stem: "An application needs guaranteed, ordered delivery of data with error recovery. Which transport protocol should it use?"
Options: [
  "TCP - provides sequencing, acknowledgments, and retransmission",
  "UDP - provides fast, connectionless delivery",
  "ICMP - provides error messaging between network devices",
  "ARP - provides address resolution"
]
Correct: 0
Explanation: "TCP's reliability features (ACK, sequencing, retransmission) guarantee ordered delivery. UDP sacrifices reliability for speed."

GOOD EXAMPLE (Address Discrimination):
Stem: "The address 192.168.1.0 in a /24 network is:"
Options: [
  "The network address - host portion is all zeros",
  "The broadcast address - host portion is all ones",
  "A valid host address - can be assigned to a device",
  "The default gateway - first usable address"
]
Correct: 0
Explanation: "In /24, the last octet is host bits. .0 = all zeros = network address. .255 would be broadcast. .1-.254 are usable hosts."

=== OUTPUT FORMAT ===
[
  {{
    "card_id": "3.X-MCQ-0XX",
    "front": "Discrimination question",
    "correct_answer": "Correct option with brief explanation",
    "distractors": ["Plausible wrong 1", "Plausible wrong 2", "Plausible wrong 3"],
    "explanation": "Why correct answer is right and others are wrong",
    "metadata": {{"difficulty": 3, "knowledge_type": "conceptual"}}
  }}
]

Generate 12 MCQs: 4 layer discrimination, 4 protocol discrimination, 4 address/PDU discrimination.
"""


async def generate_with_prompt(prompt: str) -> list[dict]:
    """Generate atoms using custom prompt."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="You are an expert CCNA instructor creating targeted practice problems."
    )

    try:
        response = await model.generate_content_async(prompt)
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
    print("TARGETED DRILL GENERATION FOR YOUR FAILURE MODES")
    print("=" * 60)

    all_atoms = []

    # 1. Network vs Broadcast (NUMERIC)
    print("\n[1/3] Generating Network vs Broadcast Drills (NUMERIC)...")
    atoms = await generate_with_prompt(NETWORK_BROADCAST_PROMPT)
    for a in atoms:
        a["module"] = 11
        a["atom_type"] = "numeric"
    all_atoms.extend(atoms)
    print(f"  Generated {len(atoms)} numeric problems")
    time.sleep(5)

    # 2. CLI Command Sequences (PARSONS)
    print("\n[2/3] Generating CLI Sequence Drills (PARSONS)...")
    atoms = await generate_with_prompt(CLI_PARSONS_PROMPT)
    for a in atoms:
        a["module"] = 2
        a["atom_type"] = "parsons"
    all_atoms.extend(atoms)
    print(f"  Generated {len(atoms)} parsons problems")
    time.sleep(5)

    # 3. Discrimination MCQs
    print("\n[3/3] Generating Discrimination MCQs...")
    atoms = await generate_with_prompt(DISCRIMINATION_MCQ_PROMPT)
    for a in atoms:
        a["module"] = 3
        a["atom_type"] = "mcq"
    all_atoms.extend(atoms)
    print(f"  Generated {len(atoms)} MCQ problems")

    # Save
    output_file = OUTPUT_DIR / "targeted_drills.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Generated {len(all_atoms)} targeted drill atoms")
    print(f"Saved to: {output_file}")
    print("=" * 60)

    # Summary
    by_type = {}
    for a in all_atoms:
        t = a.get("atom_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\nBreakdown:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")

    return all_atoms


if __name__ == "__main__":
    asyncio.run(main())
