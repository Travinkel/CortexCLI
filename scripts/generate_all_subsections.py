"""
Comprehensive atom generation for ALL struggling subsections.

Based on practice exam results:
- Module 3: 0% Communications (de-encapsulation, PDUs, packet walk)
- Module 4: 30% Connectivity (physical layer, cabling)
- Module 5: 16.7% Ethernet (MAC, frame fields, switching)
- Module 7: Frame fields, MAC types, unicast/broadcast/multicast
- Module 8: 28.6% IPv4 (subnetting, network vs host)
- Module 9: ARP process
- Module 14: TCP window, port ranges
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
    """Load CCNA module content."""
    module_file = Path(f"docs/source-materials/CCNA/CCNA Module {module_num}.txt")
    if module_file.exists():
        return module_file.read_text(encoding="utf-8")
    return ""


# =============================================================================
# MODULE-SPECIFIC PROMPTS
# =============================================================================

MODULE_4_PROMPT = """Generate atoms for Physical Layer concepts (Module 4).
Student scored 30% on Connectivity - focus on cabling types and characteristics.

=== SPECIFIC TOPICS TO COVER ===
1. Copper cabling (UTP, STP, coaxial)
2. Fiber optic (Single-mode vs Multimode)
3. T568A vs T568B wiring standards
4. Straight-through vs Crossover cables
5. Bandwidth vs Throughput
6. Full-duplex vs Half-duplex
7. Collision domains

=== OUTPUT ===
Generate 8 flashcards and 4 MCQs:
[
  {{"card_id": "4.X-FC-001", "atom_type": "flashcard", "front": "...", "back": "..."}},
  {{"card_id": "4.X-MCQ-001", "atom_type": "mcq", "front": "...", "correct_answer": "...", "distractors": ["...", "...", "..."], "explanation": "..."}}
]

CONTENT:
{content}
"""

MODULE_5_PROMPT = """Generate atoms for Ethernet/Switching concepts (Module 5).
Student scored 16.7% on Ethernet - focus on MAC addresses and frame structure.

=== SPECIFIC TOPICS TO COVER ===
1. MAC Address structure (OUI + Device ID)
2. Ethernet Frame Fields (Preamble, SFD, DA, SA, Type/Length, Data, FCS)
3. FCS & CRC error detection
4. MAC Address Table / CAM Table
5. MAC Learning process
6. Unknown unicast flooding
7. Store-and-Forward vs Cut-through switching
8. Duplex Mismatch symptoms

=== OUTPUT ===
Generate 10 flashcards, 5 MCQs, and 2 matching:
[
  {{"card_id": "5.X-FC-001", "atom_type": "flashcard", "front": "...", "back": "..."}},
  {{"card_id": "5.X-MCQ-001", "atom_type": "mcq", "front": "...", "correct_answer": "...", "distractors": ["...", "...", "..."], "explanation": "..."}},
  {{"card_id": "5.X-MAT-001", "atom_type": "matching", "front": "Match...", "pairs": [{{"left": "...", "right": "..."}}]}}
]

CONTENT:
{content}
"""

MODULE_7_PROMPT = """Generate atoms for Frame Processing and MAC types (Module 7).
Focus on unicast, broadcast, multicast handling.

=== SPECIFIC TOPICS TO COVER ===
1. CSMA/CD operation
2. Ethernet Frame Fields (detailed)
3. Unicast MAC forwarding
4. Broadcast MAC (FF:FF:FF:FF:FF:FF)
5. Multicast MAC (01:00:5e for IPv4, 33:33 for IPv6)
6. Unknown unicast handling
7. Frame processing on switches

=== OUTPUT ===
Generate 8 flashcards, 4 MCQs, and 2 matching:
[
  {{"card_id": "7.X-FC-001", "atom_type": "flashcard", "front": "...", "back": "..."}},
  {{"card_id": "7.X-MCQ-001", "atom_type": "mcq", "front": "...", "correct_answer": "...", "distractors": ["...", "...", "..."], "explanation": "..."}},
  {{"card_id": "7.X-MAT-001", "atom_type": "matching", "front": "Match MAC address type...", "pairs": [{{"left": "...", "right": "..."}}]}}
]

CONTENT:
{content}
"""

MODULE_8_PROMPT = """Generate atoms for IPv4 Addressing and Subnetting (Module 8).
Student scored 28.6% - focus on network/broadcast addresses and subnet calculations.

=== CRITICAL CONFUSION TO ADDRESS ===
Student confused network address (all 0s) with broadcast address (all 1s).

=== SPECIFIC TOPICS TO COVER ===
1. IPv4 Structure (network vs host portions)
2. Subnet Masks & CIDR notation
3. Network address calculation (host bits = all 0s)
4. Broadcast address calculation (host bits = all 1s)
5. Hosts per subnet formula (2^h - 2)
6. Subnets per network formula (2^n)
7. VLSM design
8. Private vs Public IP ranges

=== OUTPUT ===
Generate 8 numeric (calculation) problems and 4 MCQs:
[
  {{"card_id": "8.X-NUM-001", "atom_type": "numeric", "front": "Calculate network address for...", "back": "Step-by-step solution..."}},
  {{"card_id": "8.X-MCQ-001", "atom_type": "mcq", "front": "...", "correct_answer": "...", "distractors": ["...", "...", "..."], "explanation": "..."}}
]

CONTENT:
{content}
"""

MODULE_9_PROMPT = """Generate atoms for ARP and Neighbor Discovery (Module 9).

=== SPECIFIC TOPICS TO COVER ===
1. ARP Request (broadcast to FF:FF:FF:FF:FF:FF)
2. ARP Reply (unicast)
3. ARP Cache/Table
4. Gratuitous ARP
5. IPv6 Neighbor Solicitation (NS)
6. IPv6 Neighbor Advertisement (NA)
7. Solicited-node multicast (FF02::1:FFxx:xxxx)

=== OUTPUT ===
Generate 8 flashcards and 4 MCQs:
[
  {{"card_id": "9.X-FC-001", "atom_type": "flashcard", "front": "...", "back": "..."}},
  {{"card_id": "9.X-MCQ-001", "atom_type": "mcq", "front": "...", "correct_answer": "...", "distractors": ["...", "...", "..."], "explanation": "..."}}
]

CONTENT:
{content}
"""

MODULE_14_PROMPT = """Generate atoms for Transport Layer - TCP/UDP (Module 14).
Student missed Q38 (TCP Window Size) and Q41 (Port Ranges).

=== SPECIFIC TOPICS TO COVER ===
1. TCP Window Size (flow control mechanism)
2. Port number ranges:
   - Well-known: 0-1023
   - Registered: 1024-49151
   - Dynamic/Ephemeral: 49152-65535
3. TCP 3-way handshake (SYN, SYN-ACK, ACK)
4. TCP vs UDP characteristics
5. Common port numbers (HTTP 80, HTTPS 443, DNS 53, etc.)

=== OUTPUT ===
Generate 6 flashcards, 4 MCQs, and 2 numeric:
[
  {{"card_id": "14.X-FC-001", "atom_type": "flashcard", "front": "...", "back": "..."}},
  {{"card_id": "14.X-MCQ-001", "atom_type": "mcq", "front": "Port 414 falls in which range?", "correct_answer": "Registered (1024-49151)", "distractors": ["Well-known", "Dynamic", "Reserved"], "explanation": "..."}},
  {{"card_id": "14.X-NUM-001", "atom_type": "numeric", "front": "A TCP window size of 16384 bytes...", "back": "..."}}
]

CONTENT:
{content}
"""


async def generate_for_module(prompt: str, content: str, module_num: int) -> list[dict]:
    """Generate atoms for a specific module."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="You are an expert CCNA instructor. Generate high-quality learning atoms. Return ONLY valid JSON array."
    )

    full_prompt = prompt.format(content=content[:15000])

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
        for a in atoms:
            a["module"] = module_num
        return atoms if isinstance(atoms, list) else []

    except Exception as e:
        print(f"    Error: {e}")
        return []


async def main():
    print("=" * 70)
    print("COMPREHENSIVE ATOM GENERATION FOR ALL STRUGGLING SUBSECTIONS")
    print("=" * 70)

    all_atoms = []
    modules_to_process = [
        (4, MODULE_4_PROMPT, "Physical Layer (30% Connectivity)"),
        (5, MODULE_5_PROMPT, "Ethernet/MAC (16.7%)"),
        (7, MODULE_7_PROMPT, "Frame Processing/MAC Types"),
        (8, MODULE_8_PROMPT, "IPv4 Subnetting (28.6%)"),
        (9, MODULE_9_PROMPT, "ARP/Neighbor Discovery"),
        (14, MODULE_14_PROMPT, "TCP Window/Port Ranges"),
    ]

    for i, (mod_num, prompt, description) in enumerate(modules_to_process, 1):
        print(f"\n[{i}/{len(modules_to_process)}] Module {mod_num}: {description}")

        content = load_module_content(mod_num)
        if not content:
            print(f"    WARNING: No content file for Module {mod_num}")
            continue

        atoms = await generate_for_module(prompt, content, mod_num)
        all_atoms.extend(atoms)
        print(f"    Generated {len(atoms)} atoms")

        # Rate limiting
        if i < len(modules_to_process):
            time.sleep(5)

    # Save all atoms
    output_file = OUTPUT_DIR / "all_subsections_atoms.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"COMPLETE: Generated {len(all_atoms)} atoms across all modules")
    print(f"Saved to: {output_file}")
    print("=" * 70)

    # Summary by module and type
    by_module = {}
    by_type = {}
    for a in all_atoms:
        m = a.get("module", 0)
        t = a.get("atom_type", "unknown")
        by_module[m] = by_module.get(m, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1

    print("\nBy Module:")
    for m, c in sorted(by_module.items()):
        print(f"  Module {m}: {c} atoms")

    print("\nBy Type:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")

    return all_atoms


if __name__ == "__main__":
    asyncio.run(main())
