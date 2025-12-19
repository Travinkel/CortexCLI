"""
Generate atoms specifically for Module 3 - Communications/OSI (0% score area).

Focuses on:
- PDU names (Data, Segment, Packet, Frame, Bits)
- Encapsulation/De-encapsulation process
- OSI layer functions and discrimination
- TCP/IP vs OSI model comparison
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


# Custom prompts for Module 3 specific content
PDU_FLASHCARD_PROMPT = """Generate flashcards about Protocol Data Units (PDUs) at each OSI layer.

CRITICAL: The user scored 0% on this topic. These must be HIGH QUALITY and test DISCRIMINATION.

=== REQUIRED FLASHCARDS ===

Generate flashcards for EACH of these PDU concepts:
1. Application layer PDU = Data
2. Transport layer PDU = Segment (TCP) or Datagram (UDP)
3. Network layer PDU = Packet
4. Data Link layer PDU = Frame
5. Physical layer PDU = Bits

=== FEW-SHOT EXAMPLES ===

GOOD EXAMPLE (Scenario-Based):
Q: "When a web server sends HTML content to a browser, what is the PDU called at the Transport layer after TCP adds its header?"
A: "The PDU is called a segment. At the Transport layer, TCP adds sequencing and port information to the data, creating a segment that will be passed down to the Network layer for IP addressing." (35 words)

GOOD EXAMPLE (Process-Based):
Q: "During de-encapsulation at the receiving host, what PDU name does the data have immediately after the Ethernet header and trailer are removed?"
A: "After removing the Ethernet (Data Link) information, the PDU is called a packet. This IP packet still contains the Network layer header with source and destination IP addresses." (28 words)

BAD EXAMPLE (Too Abstract):
Q: "What is a segment?"
A: "A Transport layer PDU"
(Problem: No context, doesn't test understanding)

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "3.6-FC-001",
    "front": "Scenario-based question about PDUs (10-20 words)",
    "back": "Complete answer with context (15-35 words)",
    "tags": ["pdu", "encapsulation"],
    "source_refs": [{{"section_id": "3.6.3", "section_title": "Protocol Data Units"}}],
    "metadata": {{"difficulty": 2, "knowledge_type": "conceptual"}}
  }}
]

Generate 10 flashcards covering all 5 PDU types with different scenarios.

CONTENT:
{content}
"""

DEENCAPSULATION_MCQ_PROMPT = """Generate MCQs about the encapsulation and de-encapsulation process.

CRITICAL: The user scored 0% on Communications. Focus on PROCESS ORDER and LAYER DISCRIMINATION.

=== REQUIRED TOPICS ===
1. Order of encapsulation (top to bottom)
2. Order of de-encapsulation (bottom to top)
3. What each layer adds/removes
4. Which layer processes first during receiving

=== FEW-SHOT EXAMPLES ===

GOOD EXAMPLE (Process Order):
Stem: "A web browser receives an HTML page from a server. During de-encapsulation, which layer's header is removed FIRST?"
Options: [
  "Data Link layer - the Ethernet header/trailer is removed first",
  "Network layer - the IP header is removed first",
  "Transport layer - the TCP header is removed first",
  "Application layer - the HTTP header is removed first"
]
Correct: 0
Explanation: "De-encapsulation works from bottom to top. The frame arrives at Layer 1 (bits), then Layer 2 (Data Link) processes and removes the Ethernet header/trailer before passing the packet up."

GOOD EXAMPLE (What Gets Added):
Stem: "At which layer does a sending device add source and destination IP addresses to the data?"
Options: [
  "Network layer (Layer 3) - IP addressing is added here",
  "Transport layer (Layer 4) - addressing happens here",
  "Data Link layer (Layer 2) - logical addresses are added here",
  "Application layer (Layer 7) - addresses are part of application data"
]
Correct: 0
Explanation: "The Network layer (Layer 3) is responsible for logical addressing. IP addresses identify source and destination across networks."

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "3.6-MCQ-001",
    "front": "Scenario-based question about encapsulation process",
    "correct_answer": "The correct option with explanation",
    "distractors": ["Wrong option 1", "Wrong option 2", "Wrong option 3"],
    "explanation": "Why this is correct (1-2 sentences)",
    "source_refs": [{{"section_id": "3.6.5", "section_title": "De-encapsulation"}}],
    "metadata": {{"difficulty": 3, "knowledge_type": "procedural"}}
  }}
]

Generate 8 MCQs covering encapsulation and de-encapsulation.

CONTENT:
{content}
"""

OSI_LAYER_MATCHING_PROMPT = """Generate matching exercises for OSI model layers.

=== REQUIRED MATCHING SETS ===

Set 1: OSI Layer -> Function
- Layer 7 (Application) -> Process-to-process communications
- Layer 4 (Transport) -> Segmentation, flow control, reliable delivery
- Layer 3 (Network) -> Logical addressing and routing
- Layer 2 (Data Link) -> MAC addressing and frame delivery
- Layer 1 (Physical) -> Bit transmission over physical medium

Set 2: OSI Layer -> PDU Name
- Application -> Data
- Transport -> Segment/Datagram
- Network -> Packet
- Data Link -> Frame
- Physical -> Bits

Set 3: Protocol -> OSI Layer
- HTTP -> Application (Layer 7)
- TCP -> Transport (Layer 4)
- IP -> Network (Layer 3)
- Ethernet -> Data Link (Layer 2)

=== OUTPUT FORMAT ===
[
  {{
    "card_id": "3.5-MAT-001",
    "front": "Match each OSI layer to its PRIMARY function:",
    "pairs": [
      {{"left": "Layer 7 - Application", "right": "Contains protocols for process-to-process communications"}},
      {{"left": "Layer 4 - Transport", "right": "Segments data and provides reliable/unreliable delivery"}},
      {{"left": "Layer 3 - Network", "right": "Handles logical addressing and routing decisions"}},
      {{"left": "Layer 2 - Data Link", "right": "Manages MAC addressing and frame delivery"}}
    ],
    "tags": ["osi", "layers"],
    "source_refs": [{{"section_id": "3.5.2", "section_title": "The OSI Reference Model"}}],
    "metadata": {{"difficulty": 2, "knowledge_type": "factual"}}
  }}
]

Generate 4 matching exercises covering layers, PDUs, protocols, and functions.

CONTENT:
{content}
"""


async def generate_with_prompt(prompt: str, content: str) -> list[dict]:
    """Generate atoms using custom prompt."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="You are an expert CCNA instructor. Generate high-quality learning atoms."
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
        return atoms if isinstance(atoms, list) else []

    except Exception as e:
        print(f"  Error: {e}")
        return []


def load_module_content() -> str:
    """Load Module 3 content."""
    module_file = Path("docs/source-materials/CCNA/CCNA Module 3.txt")
    if module_file.exists():
        return module_file.read_text(encoding="utf-8")
    return ""


async def main():
    print("=" * 60)
    print("MODULE 3 - COMMUNICATIONS/OSI (0% AREA) ATOM GENERATION")
    print("=" * 60)

    content = load_module_content()
    if not content:
        print("ERROR: Could not load Module 3 content")
        return

    all_atoms = []

    # 1. PDU Flashcards
    print("\n[1/3] Generating PDU Flashcards...")
    atoms = await generate_with_prompt(PDU_FLASHCARD_PROMPT, content)
    for a in atoms:
        a["module"] = 3
        a["atom_type"] = "flashcard"
    all_atoms.extend(atoms)
    print(f"  Generated {len(atoms)} PDU flashcards")
    time.sleep(5)

    # 2. De-encapsulation MCQs
    print("\n[2/3] Generating De-encapsulation MCQs...")
    atoms = await generate_with_prompt(DEENCAPSULATION_MCQ_PROMPT, content)
    for a in atoms:
        a["module"] = 3
        a["atom_type"] = "mcq"
    all_atoms.extend(atoms)
    print(f"  Generated {len(atoms)} encapsulation MCQs")
    time.sleep(5)

    # 3. OSI Layer Matching
    print("\n[3/3] Generating OSI Layer Matching...")
    atoms = await generate_with_prompt(OSI_LAYER_MATCHING_PROMPT, content)
    for a in atoms:
        a["module"] = 3
        a["atom_type"] = "matching"
    all_atoms.extend(atoms)
    print(f"  Generated {len(atoms)} matching exercises")

    # Save results
    output_file = OUTPUT_DIR / "module3_atoms.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Generated {len(all_atoms)} atoms for Module 3")
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
