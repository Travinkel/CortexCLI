"""
Generate 200+ matching atoms for comprehensive discrimination practice.
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
# BATCH 1: OSI & NETWORKING FUNDAMENTALS (25 matching)
# =============================================================================
BATCH_1_PROMPT = """Generate 25 matching exercises for OSI model and networking fundamentals.

RULES:
- Each exercise has 4-6 pairs
- Pairs must be unambiguous
- Cover different aspects of each topic

=== TOPICS TO COVER (generate 3-4 matching per topic) ===

1. OSI LAYER FUNCTIONS (4 exercises)
   - Layer number to function
   - Layer to what it handles (addressing, routing, framing, etc.)
   - Layer to example action
   - Layer to device that operates there

2. PDU NAMES (3 exercises)
   - Layer to PDU name
   - PDU to description
   - PDU to what gets added/removed

3. PROTOCOLS PER LAYER (4 exercises)
   - Protocol to layer
   - Application protocols to port
   - Transport protocols to characteristics
   - Network protocols to function

4. TCP/IP vs OSI MODEL (3 exercises)
   - TCP/IP layer to OSI equivalent
   - TCP/IP layer to function
   - Protocol to TCP/IP layer

5. ENCAPSULATION PROCESS (4 exercises)
   - Step number to action
   - Layer to what header is added
   - Sending vs receiving process steps
   - Data transformation at each layer

6. ADDRESSING TYPES (4 exercises)
   - Address type to layer
   - Address to format/length
   - Address to scope (local vs end-to-end)
   - Logical vs physical addressing

7. NETWORK DEVICES (3 exercises)
   - Device to OSI layer
   - Device to function
   - Device to what it examines (MAC vs IP)

=== OUTPUT FORMAT ===
Return ONLY a JSON array, no markdown:
[
  {"card_id": "OSI-MAT-001", "atom_type": "matching", "front": "Match OSI layers to functions:", "pairs": [{"left": "...", "right": "..."}], "module": 3},
  ...
]
"""

# =============================================================================
# BATCH 2: ETHERNET & SWITCHING (25 matching)
# =============================================================================
BATCH_2_PROMPT = """Generate 25 matching exercises for Ethernet and switching concepts.

=== TOPICS TO COVER ===

1. ETHERNET FRAME FIELDS (5 exercises)
   - Field name to size in bytes
   - Field to function
   - Field to position in frame
   - Field to what it contains
   - Preamble/SFD/FCS details

2. MAC ADDRESS TYPES (4 exercises)
   - Address type to description (unicast/broadcast/multicast)
   - MAC prefix to meaning (01:00:5E, 33:33, FF:FF:FF)
   - First octet bit to address type
   - Destination type to switch action

3. SWITCHING METHODS (4 exercises)
   - Method to description
   - Method to latency level
   - Method to error handling
   - Method to when it forwards

4. SWITCH OPERATIONS (4 exercises)
   - Operation to description (learn, flood, forward, filter)
   - Frame destination to switch action
   - MAC table state to action
   - Unknown unicast vs broadcast handling

5. DUPLEX & COLLISION (4 exercises)
   - Duplex mode to description
   - Collision domain characteristics
   - Half-duplex vs full-duplex
   - CSMA/CD steps

6. ETHERTYPE VALUES (4 exercises)
   - Hex value to protocol (0x0800, 0x86DD, 0x0806)
   - Protocol to EtherType
   - Frame type field values
   - 802.1Q tag identification

=== OUTPUT FORMAT ===
[{"card_id": "ETH-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 5}, ...]
"""

# =============================================================================
# BATCH 3: CABLING & PHYSICAL LAYER (25 matching)
# =============================================================================
BATCH_3_PROMPT = """Generate 25 matching exercises for Physical Layer and cabling.

=== TOPICS TO COVER ===

1. CABLE TYPES (5 exercises)
   - Cable type to characteristics
   - Cable to connector type
   - Cable to maximum distance
   - Cable to use case
   - Cable to EMI susceptibility

2. FIBER OPTIC (5 exercises)
   - Fiber type to core size
   - Fiber to light source (laser vs LED)
   - Fiber to distance capability
   - Fiber to cost/application
   - SMF vs MMF comparisons

3. WIRING STANDARDS (5 exercises)
   - Standard to pin configuration
   - T568A vs T568B differences
   - Cable type to wiring combination
   - Straight-through vs crossover usage
   - Pin number to wire color

4. COPPER CHARACTERISTICS (5 exercises)
   - UTP categories to speed
   - STP vs UTP differences
   - Coaxial parts and function
   - RJ-45 pin functions
   - Cable length limitations

5. PHYSICAL LAYER CONCEPTS (5 exercises)
   - Term to definition (bandwidth, throughput, latency)
   - Measurement unit to concept
   - Signal type to medium
   - Encoding methods
   - Physical layer standards (100BASE-T, 1000BASE-T)

=== OUTPUT FORMAT ===
[{"card_id": "PHY-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 4}, ...]
"""

# =============================================================================
# BATCH 4: IP ADDRESSING & SUBNETTING (25 matching)
# =============================================================================
BATCH_4_PROMPT = """Generate 25 matching exercises for IP addressing and subnetting.

=== TOPICS TO COVER ===

1. CIDR TO SUBNET MASK (5 exercises)
   - /8 through /30 to dotted decimal
   - Subnet mask to CIDR
   - Prefix length to number of host bits
   - Wildcard mask relationships
   - Binary mask to decimal

2. ADDRESS TYPES (5 exercises)
   - Network address characteristics (all 0s in host)
   - Broadcast address characteristics (all 1s in host)
   - First/last usable host
   - Address type identification
   - Special addresses (0.0.0.0, 255.255.255.255)

3. PRIVATE/PUBLIC RANGES (4 exercises)
   - Private range to class
   - RFC 1918 ranges
   - APIPA range
   - Loopback range
   - Special use addresses

4. HOSTS PER SUBNET (4 exercises)
   - Prefix to number of hosts
   - Formula application
   - Usable vs total addresses
   - Point-to-point link sizing

5. SUBNET CALCULATIONS (4 exercises)
   - Given IP to network address
   - Given IP to broadcast address
   - Block size for each prefix
   - Subnet boundaries

6. IPv4 HEADER FIELDS (3 exercises)
   - Field to function
   - Field to size
   - TTL behavior

=== OUTPUT FORMAT ===
[{"card_id": "IP-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 8}, ...]
"""

# =============================================================================
# BATCH 5: TRANSPORT LAYER TCP/UDP (25 matching)
# =============================================================================
BATCH_5_PROMPT = """Generate 25 matching exercises for Transport Layer (TCP/UDP).

=== TOPICS TO COVER ===

1. TCP vs UDP (5 exercises)
   - Protocol to characteristics
   - Reliability features
   - Use cases for each
   - Header size comparison
   - Connection type

2. PORT RANGES (5 exercises)
   - Range to category name
   - Port number to range category
   - Well-known ports (0-1023)
   - Registered ports (1024-49151)
   - Dynamic ports (49152-65535)

3. COMMON PORT NUMBERS (5 exercises)
   - Service to port (HTTP, HTTPS, FTP, SSH, DNS, DHCP)
   - Port to service
   - Protocol to typical transport (TCP vs UDP)
   - Secure vs insecure versions
   - Port pairs (FTP 20/21, DHCP 67/68)

4. TCP HEADER FIELDS (5 exercises)
   - Field name to function
   - Field to size
   - Sequence/ACK numbers
   - Window size purpose
   - TCP flags meaning

5. TCP OPERATIONS (5 exercises)
   - 3-way handshake steps (SYN, SYN-ACK, ACK)
   - Connection termination (FIN, ACK)
   - Flow control mechanisms
   - Error recovery
   - Windowing/sliding window

=== OUTPUT FORMAT ===
[{"card_id": "TCP-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 14}, ...]
"""

# =============================================================================
# BATCH 6: ARP & ADDRESS RESOLUTION (20 matching)
# =============================================================================
BATCH_6_PROMPT = """Generate 20 matching exercises for ARP and address resolution.

=== TOPICS TO COVER ===

1. ARP OPERATIONS (5 exercises)
   - Operation to description
   - ARP request characteristics
   - ARP reply characteristics
   - ARP cache/table entries
   - Gratuitous ARP

2. ARP vs IPv6 ND (5 exercises)
   - ARP operation to IPv6 equivalent
   - NS/NA operations
   - Solicited-node multicast
   - RS/RA messages
   - ICMPv6 types for ND

3. ADDRESS RELATIONSHIPS (5 exercises)
   - When ARP is needed
   - Same subnet vs different subnet
   - Default gateway role
   - Proxy ARP
   - ARP table timeout

4. MAC vs IP DURING ROUTING (5 exercises)
   - What stays same end-to-end (IP)
   - What changes at each hop (MAC)
   - Router frame processing
   - New frame creation at router
   - Destination MAC for remote hosts

=== OUTPUT FORMAT ===
[{"card_id": "ARP-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 9}, ...]
"""

# =============================================================================
# BATCH 7: CLI & IOS (20 matching)
# =============================================================================
BATCH_7_PROMPT = """Generate 20 matching exercises for Cisco IOS CLI.

=== TOPICS TO COVER ===

1. CLI MODES (5 exercises)
   - Prompt to mode name
   - Mode to available commands
   - Mode to access level
   - Mode hierarchy
   - Configuration mode types

2. NAVIGATION COMMANDS (5 exercises)
   - Command to action
   - Mode transition commands
   - Exit vs end behavior
   - Keyboard shortcuts (Ctrl+Z, Ctrl+C)
   - Help commands (? usage)

3. SHOW COMMANDS (5 exercises)
   - Command to what it displays
   - Troubleshooting command selection
   - Output interpretation
   - Running vs startup config
   - Interface status commands

4. CONFIGURATION COMMANDS (5 exercises)
   - Command to configuration mode required
   - Interface commands
   - Line commands
   - Global commands
   - Security commands (password, secret)

=== OUTPUT FORMAT ===
[{"card_id": "CLI-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 2}, ...]
"""

# =============================================================================
# BATCH 8: DHCP, DNS, APPLICATION LAYER (20 matching)
# =============================================================================
BATCH_8_PROMPT = """Generate 20 matching exercises for Application Layer protocols.

=== TOPICS TO COVER ===

1. DHCP PROCESS (5 exercises)
   - DORA steps in order
   - Message type to description
   - DHCP ports (67/68)
   - Lease process
   - DHCP vs static addressing

2. DNS (5 exercises)
   - Record type to function (A, AAAA, MX, CNAME, PTR)
   - DNS query types
   - DNS port (53)
   - Recursive vs iterative
   - DNS hierarchy

3. HTTP/HTTPS (5 exercises)
   - Protocol to port
   - HTTP methods (GET, POST, PUT, DELETE)
   - Status codes (200, 404, 500)
   - Secure vs insecure
   - Request/response structure

4. OTHER APPLICATION PROTOCOLS (5 exercises)
   - FTP ports and modes
   - SMTP/POP3/IMAP differences
   - SSH vs Telnet
   - TFTP vs FTP
   - Protocol to typical use

=== OUTPUT FORMAT ===
[{"card_id": "APP-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 13}, ...]
"""

# =============================================================================
# BATCH 9: IPv6 (15 matching)
# =============================================================================
BATCH_9_PROMPT = """Generate 15 matching exercises for IPv6.

=== TOPICS TO COVER ===

1. IPv6 ADDRESS TYPES (5 exercises)
   - Prefix to address type
   - FE80::/10 -> Link-local
   - 2000::/3 -> Global unicast
   - FC00::/7 -> Unique local
   - FF00::/8 -> Multicast

2. IPv6 vs IPv4 (5 exercises)
   - Feature comparison
   - Header differences
   - Address format
   - ARP vs ND
   - Broadcast vs multicast

3. IPv6 CONFIGURATION (5 exercises)
   - SLAAC process
   - EUI-64 method
   - DHCPv6 options
   - Link-local generation
   - Router advertisement content

=== OUTPUT FORMAT ===
[{"card_id": "IPv6-MAT-001", "atom_type": "matching", "front": "...", "pairs": [...], "module": 10}, ...]
"""


async def generate_batch(prompt: str, batch_name: str) -> list[dict]:
    """Generate a batch of matching atoms."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="Generate ONLY valid JSON arrays. No markdown formatting. No explanations. Just raw JSON."
    )

    try:
        response = await model.generate_content_async(prompt)
        text = response.text

        import re
        # Try to find JSON array
        match = re.search(r"```json\s*([\s\S]*?)```", text)
        if match:
            json_str = match.group(1).strip()
        else:
            match_list = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
            if match_list:
                json_str = match_list.group(0)
            else:
                json_str = text.strip()

        atoms = json.loads(json_str)
        for a in atoms:
            a["atom_type"] = "matching"
        return atoms if isinstance(atoms, list) else []

    except Exception as e:
        print(f"    Error in {batch_name}: {e}")
        return []


async def main():
    print("=" * 70)
    print("GENERATING 200+ MATCHING ATOMS")
    print("=" * 70)

    all_atoms = []

    batches = [
        ("Batch 1: OSI & Fundamentals", BATCH_1_PROMPT, 25),
        ("Batch 2: Ethernet & Switching", BATCH_2_PROMPT, 25),
        ("Batch 3: Cabling & Physical", BATCH_3_PROMPT, 25),
        ("Batch 4: IP Addressing", BATCH_4_PROMPT, 25),
        ("Batch 5: TCP/UDP Transport", BATCH_5_PROMPT, 25),
        ("Batch 6: ARP & Resolution", BATCH_6_PROMPT, 20),
        ("Batch 7: CLI & IOS", BATCH_7_PROMPT, 20),
        ("Batch 8: Application Layer", BATCH_8_PROMPT, 20),
        ("Batch 9: IPv6", BATCH_9_PROMPT, 15),
    ]

    for i, (name, prompt, expected) in enumerate(batches, 1):
        print(f"\n[{i}/{len(batches)}] {name} (expecting ~{expected})...")
        atoms = await generate_batch(prompt, name)
        all_atoms.extend(atoms)
        print(f"    Generated {len(atoms)} matching exercises")

        if i < len(batches):
            print("    Waiting for rate limit...")
            time.sleep(6)

    # Save
    output_file = OUTPUT_DIR / "massive_matching.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"COMPLETE: Generated {len(all_atoms)} matching exercises!")
    print(f"Saved to: {output_file}")
    print("=" * 70)

    # Summary
    by_module = {}
    for a in all_atoms:
        m = a.get("module", 0)
        by_module[m] = by_module.get(m, 0) + 1

    print("\nBy Module:")
    for m, c in sorted(by_module.items()):
        print(f"  Module {m}: {c}")

    return all_atoms


if __name__ == "__main__":
    asyncio.run(main())
