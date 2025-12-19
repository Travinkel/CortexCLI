"""
Generate MANY matching atoms for discrimination practice.

Matching is ideal for:
- OSI layer discrimination
- Protocol comparison
- Cable type identification
- Address type discrimination
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
# MATCHING PROMPTS - ONE FOR EACH TOPIC AREA
# =============================================================================

OSI_LAYERS_MATCHING = """Generate 5 matching exercises for OSI Model discrimination.

=== MATCHING SET 1: Layer to Function ===
Match OSI layers to their PRIMARY function:
- Layer 7 (Application) -> Process-to-process communications, user interfaces
- Layer 6 (Presentation) -> Data encryption, compression, format translation
- Layer 5 (Session) -> Dialog control, session management
- Layer 4 (Transport) -> Segmentation, flow control, error recovery
- Layer 3 (Network) -> Logical addressing, routing between networks
- Layer 2 (Data Link) -> Physical addressing, frame delivery, error detection
- Layer 1 (Physical) -> Bit transmission, cables, signals, connectors

=== MATCHING SET 2: Layer to PDU Name ===
- Application/Presentation/Session -> Data
- Transport -> Segment (TCP) / Datagram (UDP)
- Network -> Packet
- Data Link -> Frame
- Physical -> Bits

=== MATCHING SET 3: Protocol to Layer ===
- HTTP, FTP, DNS, DHCP -> Application (Layer 7)
- TCP, UDP -> Transport (Layer 4)
- IP, ICMP, ARP -> Network (Layer 3)
- Ethernet, 802.11 -> Data Link (Layer 2)

=== MATCHING SET 4: Device to Layer ===
- Hub, Repeater -> Physical (Layer 1)
- Switch, Bridge -> Data Link (Layer 2)
- Router, Layer 3 Switch -> Network (Layer 3)

=== MATCHING SET 5: Layer to Address Type ===
- Layer 2 -> MAC Address (48-bit, burned-in)
- Layer 3 -> IP Address (logical, hierarchical)
- Layer 4 -> Port Number (identifies application)

=== OUTPUT FORMAT ===
[
  {
    "card_id": "3.5-MAT-001",
    "atom_type": "matching",
    "front": "Match each OSI layer to its PRIMARY function:",
    "pairs": [
      {"left": "Layer 7 - Application", "right": "Process-to-process communications"},
      {"left": "Layer 4 - Transport", "right": "Segmentation and reliable delivery"},
      {"left": "Layer 3 - Network", "right": "Logical addressing and routing"},
      {"left": "Layer 2 - Data Link", "right": "Physical addressing and framing"}
    ],
    "module": 3
  }
]

Generate exactly 5 matching exercises covering all the sets above.
"""

PDU_ENCAPSULATION_MATCHING = """Generate 4 matching exercises for PDU and Encapsulation.

=== SET 1: PDU Name to Layer ===
- Data -> Application layer
- Segment -> Transport layer (TCP)
- Datagram -> Transport layer (UDP)
- Packet -> Network layer
- Frame -> Data Link layer
- Bits -> Physical layer

=== SET 2: Header Added at Each Layer ===
- Application -> Application protocol header (HTTP, FTP)
- Transport -> Source/Dest port, sequence numbers
- Network -> Source/Dest IP addresses
- Data Link -> Source/Dest MAC, FCS trailer

=== SET 3: Encapsulation Order (Top to Bottom) ===
- Step 1 -> Application creates data
- Step 2 -> Transport adds segment header
- Step 3 -> Network adds IP header (packet)
- Step 4 -> Data Link adds MAC header + FCS trailer (frame)
- Step 5 -> Physical converts to bits

=== SET 4: De-encapsulation Order (Bottom to Top) ===
- Step 1 -> Physical receives bits
- Step 2 -> Data Link removes Ethernet header/trailer
- Step 3 -> Network removes IP header
- Step 4 -> Transport removes TCP/UDP header
- Step 5 -> Application receives data

=== OUTPUT FORMAT ===
[
  {
    "card_id": "3.6-MAT-001",
    "atom_type": "matching",
    "front": "Match each PDU name to its OSI layer:",
    "pairs": [
      {"left": "Segment", "right": "Transport layer (Layer 4)"},
      {"left": "Packet", "right": "Network layer (Layer 3)"},
      {"left": "Frame", "right": "Data Link layer (Layer 2)"},
      {"left": "Bits", "right": "Physical layer (Layer 1)"}
    ],
    "module": 3
  }
]

Generate exactly 4 matching exercises.
"""

CABLE_TYPES_MATCHING = """Generate 4 matching exercises for Physical Layer cabling.

=== SET 1: Cable Type to Characteristics ===
- UTP (Unshielded Twisted Pair) -> Most common LAN cable, RJ-45 connector, susceptible to EMI
- STP (Shielded Twisted Pair) -> Better EMI protection, more expensive, requires grounding
- Coaxial -> Used for cable TV/internet, BNC/F-type connectors, single conductor
- Fiber Optic -> Uses light, immune to EMI, longest distances

=== SET 2: Fiber Type to Characteristics ===
- Single-mode (SMF) -> Laser light source, small core (9 micron), longest distance (100+ km)
- Multimode (MMF) -> LED light source, larger core (50/62.5 micron), shorter distance (< 2 km)

=== SET 3: Cable Wiring to Usage ===
- Straight-through -> Unlike devices (PC to Switch, Router to Switch)
- Crossover -> Like devices (Switch to Switch, PC to PC, Router to Router)
- Rollover (Console) -> PC to Router/Switch console port

=== SET 4: Wiring Standard to Pin Configuration ===
- T568A -> Green pair on pins 1-2
- T568B -> Orange pair on pins 1-2 (most common)
- Straight-through -> Same standard on both ends
- Crossover -> T568A on one end, T568B on other

=== OUTPUT FORMAT ===
[
  {
    "card_id": "4.2-MAT-001",
    "atom_type": "matching",
    "front": "Match each cable type to its characteristics:",
    "pairs": [...]
    "module": 4
  }
]

Generate exactly 4 matching exercises.
"""

MAC_ADDRESS_MATCHING = """Generate 4 matching exercises for MAC addresses and Ethernet.

=== SET 1: MAC Address Type to Description ===
- Unicast -> Single specific destination (first octet bit 0 = 0)
- Broadcast -> All devices (FF:FF:FF:FF:FF:FF)
- Multicast IPv4 -> Group address (01:00:5E:xx:xx:xx)
- Multicast IPv6 -> Group address (33:33:xx:xx:xx:xx)

=== SET 2: Frame Field to Function ===
- Preamble (7 bytes) -> Synchronization pattern (10101010...)
- SFD (1 byte) -> Start Frame Delimiter (10101011)
- Destination MAC (6 bytes) -> Where the frame is going
- Source MAC (6 bytes) -> Where the frame came from
- Type/Length (2 bytes) -> Identifies upper layer protocol (0x0800=IPv4)
- FCS (4 bytes) -> Error detection using CRC

=== SET 3: Switching Method to Characteristic ===
- Store-and-Forward -> Receives entire frame, checks FCS, highest latency, most reliable
- Cut-Through -> Forwards after reading destination MAC, lowest latency, may forward errors
- Fragment-Free -> Reads first 64 bytes (collision window), compromise approach

=== SET 4: EtherType Value to Protocol ===
- 0x0800 -> IPv4
- 0x86DD -> IPv6
- 0x0806 -> ARP
- 0x8100 -> 802.1Q VLAN tag

=== OUTPUT FORMAT ===
[
  {
    "card_id": "5.1-MAT-001",
    "atom_type": "matching",
    "front": "Match each MAC address type to its description:",
    "pairs": [...]
    "module": 5
  }
]

Generate exactly 4 matching exercises.
"""

TCP_UDP_MATCHING = """Generate 4 matching exercises for Transport Layer (TCP vs UDP).

=== SET 1: Protocol to Characteristic ===
- TCP -> Connection-oriented, reliable, sequenced, flow control, 3-way handshake
- UDP -> Connectionless, unreliable, best-effort, no handshake, lower overhead

=== SET 2: TCP Header Field to Function ===
- Source Port -> Identifies sending application
- Destination Port -> Identifies receiving application
- Sequence Number -> Tracks byte position in stream
- Acknowledgment Number -> Confirms received bytes
- Window Size -> Flow control (how much data can be sent)
- Checksum -> Error detection

=== SET 3: Port Range to Category ===
- 0-1023 -> Well-known ports (system services)
- 1024-49151 -> Registered ports (user applications)
- 49152-65535 -> Dynamic/Ephemeral ports (client-side)

=== SET 4: Application to Port Number ===
- HTTP -> Port 80
- HTTPS -> Port 443
- FTP Data -> Port 20
- FTP Control -> Port 21
- SSH -> Port 22
- Telnet -> Port 23
- DNS -> Port 53
- DHCP Server -> Port 67
- DHCP Client -> Port 68

=== OUTPUT FORMAT ===
[
  {
    "card_id": "14.1-MAT-001",
    "atom_type": "matching",
    "front": "Match TCP vs UDP to their characteristics:",
    "pairs": [...]
    "module": 14
  }
]

Generate exactly 4 matching exercises.
"""

ARP_MATCHING = """Generate 3 matching exercises for ARP and Address Resolution.

=== SET 1: ARP Operation to Description ===
- ARP Request -> Broadcast to FF:FF:FF:FF:FF:FF asking "Who has this IP?"
- ARP Reply -> Unicast response with MAC address
- Gratuitous ARP -> Device announces its own IP-to-MAC mapping
- ARP Cache -> Table storing IP-to-MAC mappings

=== SET 2: IPv6 Neighbor Discovery to IPv4 ARP Equivalent ===
- Neighbor Solicitation (NS) -> Similar to ARP Request
- Neighbor Advertisement (NA) -> Similar to ARP Reply
- Router Solicitation (RS) -> Host asking for routers
- Router Advertisement (RA) -> Router announcing itself

=== SET 3: Address Type to Scope ===
- MAC Address -> Local network only, changes at each hop
- IP Address -> End-to-end, stays same through routing
- Port Number -> Identifies application/process

=== OUTPUT FORMAT ===
[
  {
    "card_id": "9.1-MAT-001",
    "atom_type": "matching",
    "front": "Match each ARP operation to its description:",
    "pairs": [...]
    "module": 9
  }
]

Generate exactly 3 matching exercises.
"""

SUBNETTING_MATCHING = """Generate 4 matching exercises for IPv4 Addressing.

=== SET 1: CIDR Notation to Subnet Mask ===
- /8 -> 255.0.0.0
- /16 -> 255.255.0.0
- /24 -> 255.255.255.0
- /25 -> 255.255.255.128
- /26 -> 255.255.255.192
- /27 -> 255.255.255.224
- /28 -> 255.255.255.240
- /30 -> 255.255.255.252

=== SET 2: Address Type to Host Portion ===
- Network Address -> All host bits set to 0
- Broadcast Address -> All host bits set to 1
- First Usable Host -> Network address + 1
- Last Usable Host -> Broadcast address - 1

=== SET 3: Private IP Range to Class ===
- 10.0.0.0/8 -> Class A private (1 network, 16M hosts)
- 172.16.0.0/12 -> Class B private (16 networks)
- 192.168.0.0/16 -> Class C private (256 networks)
- 169.254.0.0/16 -> APIPA (link-local)

=== SET 4: Prefix Length to Usable Hosts ===
- /24 -> 254 hosts (256-2)
- /25 -> 126 hosts (128-2)
- /26 -> 62 hosts (64-2)
- /27 -> 30 hosts (32-2)
- /28 -> 14 hosts (16-2)
- /29 -> 6 hosts (8-2)
- /30 -> 2 hosts (point-to-point)

=== OUTPUT FORMAT ===
[
  {
    "card_id": "8.2-MAT-001",
    "atom_type": "matching",
    "front": "Match each CIDR prefix to its subnet mask:",
    "pairs": [...]
    "module": 8
  }
]

Generate exactly 4 matching exercises.
"""

CLI_MODES_MATCHING = """Generate 3 matching exercises for Cisco IOS CLI.

=== SET 1: Prompt to Mode ===
- Router> -> User EXEC mode
- Router# -> Privileged EXEC mode
- Router(config)# -> Global configuration mode
- Router(config-if)# -> Interface configuration mode
- Router(config-line)# -> Line configuration mode
- Router(config-router)# -> Router configuration mode

=== SET 2: Command to Mode Where It's Entered ===
- show running-config -> Privileged EXEC (Router#)
- hostname -> Global config (Router(config)#)
- ip address -> Interface config (Router(config-if)#)
- password -> Line config (Router(config-line)#)
- enable secret -> Global config (Router(config)#)
- no shutdown -> Interface config (Router(config-if)#)

=== SET 3: Navigation Command to Action ===
- enable -> User EXEC to Privileged EXEC
- configure terminal -> Privileged EXEC to Global config
- interface g0/0 -> Global config to Interface config
- line console 0 -> Global config to Line config
- exit -> Go back one level
- end (Ctrl+Z) -> Return to Privileged EXEC from any config mode

=== OUTPUT FORMAT ===
[
  {
    "card_id": "2.2-MAT-001",
    "atom_type": "matching",
    "front": "Match each CLI prompt to its mode:",
    "pairs": [...]
    "module": 2
  }
]

Generate exactly 3 matching exercises.
"""


async def generate_matching(prompt: str) -> list[dict]:
    """Generate matching atoms."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="Generate ONLY valid JSON arrays. No markdown, no explanation, just the JSON."
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
        for a in atoms:
            a["atom_type"] = "matching"
        return atoms if isinstance(atoms, list) else []

    except Exception as e:
        print(f"    Error: {e}")
        return []


async def main():
    print("=" * 70)
    print("GENERATING MANY MATCHING ATOMS FOR DISCRIMINATION PRACTICE")
    print("=" * 70)

    all_atoms = []

    prompts = [
        ("OSI Layers", OSI_LAYERS_MATCHING),
        ("PDU/Encapsulation", PDU_ENCAPSULATION_MATCHING),
        ("Cable Types", CABLE_TYPES_MATCHING),
        ("MAC/Ethernet", MAC_ADDRESS_MATCHING),
        ("TCP/UDP/Ports", TCP_UDP_MATCHING),
        ("ARP/ND", ARP_MATCHING),
        ("Subnetting", SUBNETTING_MATCHING),
        ("CLI Modes", CLI_MODES_MATCHING),
    ]

    for i, (name, prompt) in enumerate(prompts, 1):
        print(f"\n[{i}/{len(prompts)}] Generating {name} matching...")
        atoms = await generate_matching(prompt)
        all_atoms.extend(atoms)
        print(f"    Generated {len(atoms)} matching exercises")
        if i < len(prompts):
            time.sleep(4)

    # Save
    output_file = OUTPUT_DIR / "matching_atoms.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"COMPLETE: Generated {len(all_atoms)} matching exercises")
    print(f"Saved to: {output_file}")
    print("=" * 70)

    # By module
    by_module = {}
    for a in all_atoms:
        m = a.get("module", 0)
        by_module[m] = by_module.get(m, 0) + 1

    print("\nBy Module:")
    for m, c in sorted(by_module.items()):
        print(f"  Module {m}: {c} matching")

    return all_atoms


if __name__ == "__main__":
    asyncio.run(main())
