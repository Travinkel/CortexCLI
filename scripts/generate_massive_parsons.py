"""
Generate 150+ Parsons problems for CLI command ordering.

Parsons = Put commands in correct sequence.
Critical for your CLI struggles.
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
# BATCH 1: BASIC DEVICE SETUP (20 parsons)
# =============================================================================
BATCH_1_PROMPT = """Generate 20 Parsons problems for basic Cisco device setup.

A Parsons problem gives scrambled commands - student must put them in correct order.

=== TOPICS (4 problems each) ===

1. HOSTNAME & BASIC SETUP
   - Set hostname
   - Disable DNS lookup
   - Set banner MOTD
   - Save configuration

2. CONSOLE PASSWORD
   - Enter line console 0
   - Set password
   - Enable login
   - Exit

3. ENABLE SECRET
   - Enter global config
   - Set enable secret (NOT enable password)
   - Set minimum password length
   - Exit

4. SERVICE PASSWORD-ENCRYPTION
   CRITICAL: This command goes AFTER setting passwords!
   - Set line passwords first
   - Then apply service password-encryption
   - Order matters!

5. SAVE CONFIGURATION
   - copy running-config startup-config
   - Or: write memory
   - Verify with show startup-config

=== OUTPUT FORMAT ===
[
  {
    "card_id": "2.1-PAR-001",
    "atom_type": "parsons",
    "scenario": "Configure hostname 'R1' and disable DNS lookup on a new router.",
    "correct_sequence": [
      "enable",
      "configure terminal",
      "hostname R1",
      "no ip domain-lookup",
      "end"
    ],
    "distractors": ["ip domain-lookup", "name R1"],
    "explanation": "Must enter privileged EXEC, then global config before setting hostname.",
    "module": 2
  }
]

Generate 20 Parsons problems with 1-2 distractors each.
"""

# =============================================================================
# BATCH 2: SSH CONFIGURATION (20 parsons)
# =============================================================================
BATCH_2_PROMPT = """Generate 20 Parsons problems for SSH configuration.

=== KEY SEQUENCE FOR SSH ===
1. enable
2. configure terminal
3. hostname (required for RSA)
4. ip domain-name company.com (required for RSA)
5. crypto key generate rsa [modulus 1024]
6. username admin secret cisco123
7. line vty 0 4
8. transport input ssh
9. login local
10. end

=== VARIATIONS TO COVER ===

1. FULL SSH SETUP (5 problems)
   - Complete sequence from scratch
   - Different hostnames/domains
   - Different modulus sizes (1024, 2048)

2. RSA KEY GENERATION (4 problems)
   - Domain name MUST come before crypto key
   - Hostname MUST be set
   - Different key sizes

3. VTY LINE CONFIGURATION (4 problems)
   - transport input ssh (disable telnet)
   - login local vs login
   - exec-timeout settings
   - access-class for ACL

4. LOCAL USER DATABASE (4 problems)
   - username with secret (not password)
   - privilege levels
   - Multiple users

5. SSH VERSION (3 problems)
   - ip ssh version 2
   - Placement in sequence

=== DISTRACTORS TO INCLUDE ===
- transport input telnet
- login (without local)
- enable password (instead of secret)
- crypto key generate dsa

=== OUTPUT FORMAT ===
[
  {
    "card_id": "2.5-PAR-001",
    "atom_type": "parsons",
    "scenario": "Configure SSH version 2 on router R1 with domain 'cisco.com'.",
    "correct_sequence": ["enable", "configure terminal", "hostname R1", "ip domain-name cisco.com", "crypto key generate rsa", "ip ssh version 2"],
    "distractors": ["crypto key generate dsa"],
    "explanation": "Domain name must be set before generating RSA keys.",
    "module": 2
  }
]

Generate 20 Parsons problems.
"""

# =============================================================================
# BATCH 3: INTERFACE CONFIGURATION (20 parsons)
# =============================================================================
BATCH_3_PROMPT = """Generate 20 Parsons problems for interface configuration.

=== ROUTER INTERFACE IPv4 ===
1. enable
2. configure terminal
3. interface GigabitEthernet0/0
4. description Link to LAN
5. ip address 192.168.1.1 255.255.255.0
6. no shutdown
7. end

=== ROUTER INTERFACE IPv6 ===
1. enable
2. configure terminal
3. ipv6 unicast-routing (global - enables IPv6 routing)
4. interface GigabitEthernet0/0
5. ipv6 address 2001:db8:1::1/64
6. ipv6 address fe80::1 link-local
7. no shutdown

=== SWITCH SVI (Management) ===
1. enable
2. configure terminal
3. interface vlan 1
4. ip address 192.168.1.2 255.255.255.0
5. no shutdown
6. exit
7. ip default-gateway 192.168.1.1 (global config!)

=== VARIATIONS (20 problems) ===
- Different interface types (Gi, Fa, Serial)
- IPv4 only, IPv6 only, dual-stack
- With descriptions
- With clock rate (for serial DCE)
- Switch SVI with default gateway
- Loopback interfaces
- Subinterfaces for VLANs

=== DISTRACTORS ===
- shutdown (instead of no shutdown)
- Wrong mask format
- ipv6 address without /prefix
- default-gateway in interface mode (wrong!)

=== OUTPUT FORMAT ===
[
  {
    "card_id": "2.6-PAR-001",
    "atom_type": "parsons",
    "scenario": "Configure interface G0/0 with IP 10.1.1.1/24 and enable it.",
    "correct_sequence": [...],
    "distractors": [...],
    "explanation": "...",
    "module": 2
  }
]

Generate 20 Parsons problems.
"""

# =============================================================================
# BATCH 4: VTY & CONSOLE SECURITY (20 parsons)
# =============================================================================
BATCH_4_PROMPT = """Generate 20 Parsons problems for line security (VTY/Console).

=== CONSOLE LINE ===
1. enable
2. configure terminal
3. line console 0
4. password cisco
5. login
6. exec-timeout 5 0
7. logging synchronous
8. exit

=== VTY LINES (Telnet/SSH) ===
1. enable
2. configure terminal
3. line vty 0 4
4. password cisco
5. login
6. transport input ssh (or telnet or all)
7. exec-timeout 5 0
8. exit

=== VTY WITH LOCAL AUTH ===
1. username admin secret cisco123 (global config first!)
2. line vty 0 4
3. login local
4. transport input ssh

=== VTY WITH ACL ===
1. access-list 10 permit 192.168.1.0 0.0.0.255 (global)
2. line vty 0 4
3. access-class 10 in
4. login local

=== VARIATIONS (20 problems) ===
- Console only
- VTY only
- Both console and VTY
- With exec-timeout
- With logging synchronous
- With ACL restriction
- Local vs line password authentication

=== OUTPUT FORMAT ===
[
  {
    "card_id": "2.4-PAR-001",
    "atom_type": "parsons",
    "scenario": "Secure VTY lines 0-4 with password 'cisco' and 5-minute timeout.",
    "correct_sequence": [...],
    "distractors": [...],
    "explanation": "...",
    "module": 2
  }
]

Generate 20 Parsons problems.
"""

# =============================================================================
# BATCH 5: VLAN CONFIGURATION (20 parsons)
# =============================================================================
BATCH_5_PROMPT = """Generate 20 Parsons problems for VLAN configuration.

=== CREATE VLAN ===
1. enable
2. configure terminal
3. vlan 10
4. name SALES
5. exit

=== ACCESS PORT ===
1. interface FastEthernet0/1
2. switchport mode access
3. switchport access vlan 10
4. exit

=== TRUNK PORT ===
1. interface GigabitEthernet0/1
2. switchport mode trunk
3. switchport trunk native vlan 99
4. switchport trunk allowed vlan 10,20,30
5. exit

=== VOICE VLAN ===
1. interface FastEthernet0/5
2. switchport mode access
3. switchport access vlan 10
4. switchport voice vlan 150
5. exit

=== INTER-VLAN ROUTING (Router-on-a-Stick) ===
1. interface GigabitEthernet0/0.10
2. encapsulation dot1q 10
3. ip address 192.168.10.1 255.255.255.0
4. exit

=== VARIATIONS (20 problems) ===
- Create single VLAN
- Create multiple VLANs
- Configure access port
- Configure trunk port
- Native VLAN configuration
- Allowed VLANs on trunk
- Voice VLAN setup
- Router subinterface for VLAN

=== OUTPUT FORMAT ===
[
  {
    "card_id": "6.1-PAR-001",
    "atom_type": "parsons",
    "scenario": "Create VLAN 20 named 'HR' and assign port Fa0/5 to it.",
    "correct_sequence": [...],
    "distractors": [...],
    "explanation": "...",
    "module": 6
  }
]

Generate 20 Parsons problems.
"""

# =============================================================================
# BATCH 6: STATIC ROUTING (15 parsons)
# =============================================================================
BATCH_6_PROMPT = """Generate 15 Parsons problems for static routing.

=== BASIC STATIC ROUTE ===
1. enable
2. configure terminal
3. ip route 192.168.2.0 255.255.255.0 10.1.1.2
4. end

=== DEFAULT ROUTE ===
1. enable
2. configure terminal
3. ip route 0.0.0.0 0.0.0.0 10.1.1.1
4. end

=== IPv6 STATIC ROUTE ===
1. enable
2. configure terminal
3. ipv6 unicast-routing
4. ipv6 route 2001:db8:2::/64 2001:db8:1::2
5. end

=== FLOATING STATIC (Backup Route) ===
1. ip route 192.168.2.0 255.255.255.0 10.1.1.2 (primary)
2. ip route 192.168.2.0 255.255.255.0 10.2.2.2 5 (backup with AD 5)

=== VARIATIONS (15 problems) ===
- Next-hop IP address
- Exit interface
- Fully specified (both)
- Default route (quad zero)
- IPv6 static routes
- Floating static routes
- Directly connected static

=== OUTPUT FORMAT ===
[
  {
    "card_id": "15.1-PAR-001",
    "atom_type": "parsons",
    "scenario": "Configure a default route pointing to next-hop 10.0.0.1",
    "correct_sequence": [...],
    "distractors": [...],
    "explanation": "...",
    "module": 15
  }
]

Generate 15 Parsons problems.
"""

# =============================================================================
# BATCH 7: DHCP CONFIGURATION (15 parsons)
# =============================================================================
BATCH_7_PROMPT = """Generate 15 Parsons problems for DHCP configuration.

=== DHCP SERVER ON ROUTER ===
1. enable
2. configure terminal
3. ip dhcp excluded-address 192.168.1.1 192.168.1.10
4. ip dhcp pool LAN_POOL
5. network 192.168.1.0 255.255.255.0
6. default-router 192.168.1.1
7. dns-server 8.8.8.8
8. lease 7
9. exit

=== DHCP RELAY (ip helper-address) ===
1. enable
2. configure terminal
3. interface GigabitEthernet0/0
4. ip helper-address 10.1.1.100
5. exit

=== VARIATIONS (15 problems) ===
- Basic DHCP pool
- With excluded addresses
- With DNS server
- With default gateway
- With domain name
- With lease time
- DHCP relay configuration
- Multiple pools

=== OUTPUT FORMAT ===
[
  {
    "card_id": "13.2-PAR-001",
    "atom_type": "parsons",
    "scenario": "Configure DHCP pool for 192.168.10.0/24 with gateway .1 and DNS 8.8.8.8",
    "correct_sequence": [...],
    "distractors": [...],
    "explanation": "...",
    "module": 13
  }
]

Generate 15 Parsons problems.
"""

# =============================================================================
# BATCH 8: ACL CONFIGURATION (20 parsons)
# =============================================================================
BATCH_8_PROMPT = """Generate 20 Parsons problems for ACL configuration.

=== STANDARD ACL (1-99) ===
1. enable
2. configure terminal
3. access-list 10 permit 192.168.1.0 0.0.0.255
4. access-list 10 deny any
5. interface GigabitEthernet0/0
6. ip access-group 10 in
7. exit

=== EXTENDED ACL (100-199) ===
1. enable
2. configure terminal
3. access-list 100 permit tcp 192.168.1.0 0.0.0.255 any eq 80
4. access-list 100 deny ip any any
5. interface GigabitEthernet0/0
6. ip access-group 100 out
7. exit

=== NAMED ACL ===
1. enable
2. configure terminal
3. ip access-list standard BLOCK_LIST
4. deny 10.1.1.0 0.0.0.255
5. permit any
6. exit
7. interface GigabitEthernet0/1
8. ip access-group BLOCK_LIST in

=== VARIATIONS (20 problems) ===
- Standard numbered ACL
- Extended numbered ACL
- Named standard ACL
- Named extended ACL
- Permit statements
- Deny statements
- Apply inbound
- Apply outbound
- VTY access-class

=== OUTPUT FORMAT ===
[
  {
    "card_id": "7.2-PAR-001",
    "atom_type": "parsons",
    "scenario": "Create standard ACL 10 to permit network 10.0.0.0/8 and apply inbound on G0/0.",
    "correct_sequence": [...],
    "distractors": [...],
    "explanation": "...",
    "module": 7
  }
]

Generate 20 Parsons problems.
"""


async def generate_batch(prompt: str, batch_name: str) -> list[dict]:
    """Generate a batch of parsons atoms."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction="Generate ONLY valid JSON arrays. No markdown. No explanation. Raw JSON only."
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
                json_str = text.strip()

        atoms = json.loads(json_str)
        for a in atoms:
            a["atom_type"] = "parsons"
        return atoms if isinstance(atoms, list) else []

    except Exception as e:
        print(f"    Error in {batch_name}: {e}")
        return []


async def main():
    print("=" * 70)
    print("GENERATING 150+ PARSONS PROBLEMS (CLI Command Ordering)")
    print("=" * 70)

    all_atoms = []

    batches = [
        ("Batch 1: Basic Device Setup", BATCH_1_PROMPT, 20),
        ("Batch 2: SSH Configuration", BATCH_2_PROMPT, 20),
        ("Batch 3: Interface Configuration", BATCH_3_PROMPT, 20),
        ("Batch 4: VTY & Console Security", BATCH_4_PROMPT, 20),
        ("Batch 5: VLAN Configuration", BATCH_5_PROMPT, 20),
        ("Batch 6: Static Routing", BATCH_6_PROMPT, 15),
        ("Batch 7: DHCP Configuration", BATCH_7_PROMPT, 15),
        ("Batch 8: ACL Configuration", BATCH_8_PROMPT, 20),
    ]

    for i, (name, prompt, expected) in enumerate(batches, 1):
        print(f"\n[{i}/{len(batches)}] {name} (expecting ~{expected})...")
        atoms = await generate_batch(prompt, name)
        all_atoms.extend(atoms)
        print(f"    Generated {len(atoms)} Parsons problems")

        if i < len(batches):
            print("    Waiting for rate limit...")
            time.sleep(6)

    # Save
    output_file = OUTPUT_DIR / "massive_parsons.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"COMPLETE: Generated {len(all_atoms)} Parsons problems!")
    print(f"Saved to: {output_file}")
    print("=" * 70)

    # Summary by module
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
