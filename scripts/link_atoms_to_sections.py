#!/usr/bin/env python
"""
Link Existing Atoms to CCNA Sections.

Analyzes atom content and links them to the appropriate CCNA sections
based on keyword matching and content analysis.

Usage:
    python scripts/link_atoms_to_sections.py
    python scripts/link_atoms_to_sections.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

console = Console()


# Section keywords mapping - maps content keywords to section IDs
SECTION_KEYWORDS = {
    # Module 1: Networking Today
    "1.2": ["network components", "client", "server", "host", "end device"],
    "1.4": ["lan", "wan", "internet", "intranet", "extranet"],
    "1.5": ["dsl", "cable", "fiber", "internet connection", "isp"],
    "1.6": ["fault tolerance", "scalability", "qos", "quality of service"],
    "1.7": ["byod", "cloud", "wireless", "trend"],
    "1.8": ["security threat", "malware", "virus", "firewall"],

    # Module 3: Protocols and Models
    "3.2": ["protocol suite", "tcp/ip"],
    "3.3": ["data access", "transport", "internet layer", "network access"],
    "3.4": ["encapsulation", "de-encapsulation", "pdu", "segment"],
    "3.5": ["osi model", "seven layer", "application layer", "presentation layer"],

    # Module 4: Physical Layer
    "4.2": ["physical layer", "signaling", "encoding", "bandwidth"],
    "4.3": ["copper cabling", "utp", "stp", "coaxial"],
    "4.4": ["fiber optic", "single-mode", "multimode"],
    "4.5": ["wireless", "wi-fi", "wlan", "802.11"],

    # Module 5: Number Systems
    "5.1": ["binary", "decimal", "positional notation"],
    "5.2": ["hexadecimal", "hex", "base 16"],

    # Module 6: Data Link Layer
    "6.1": ["data link layer", "llc", "mac sublayer", "frame"],
    "6.2": ["llc sublayer", "logical link control", "upper layer"],
    "6.3": ["mac sublayer", "media access control", "addressing"],
    "6.4": ["frame", "header", "trailer", "fcs", "frame check sequence"],
    "6.5": ["wan topology", "point-to-point", "hub and spoke"],

    # Module 7: Ethernet Switching
    "7.1": ["ethernet", "ieee 802.3", "legacy ethernet"],
    "7.2": ["ethernet frame", "preamble", "destination mac", "type field"],
    "7.3": ["mac address", "mac table", "arp", "address resolution"],

    # Module 8: Network Layer
    "8.1": ["network layer", "routing", "forwarding", "path determination"],
    "8.2": ["ip protocol", "ipv4", "ipv6", "packet header"],

    # Module 9: Address Resolution
    "9.1": ["mac address", "ipv4 address", "broadcast", "unicast"],
    "9.2": ["arp", "address resolution protocol", "arp table"],
    "9.3": ["neighbor discovery", "nd", "icmpv6"],

    # Module 10: Basic Router Configuration
    "10.1": ["router", "routing table", "default gateway"],
    "10.2": ["router configuration", "interface", "ip address"],
    "10.3": ["default gateway", "packet forwarding"],
    "10.4": ["switch configuration", "vlan", "management interface"],

    # Module 11: IPv4 Addressing
    "11.1": ["ipv4 address", "network portion", "host portion"],
    "11.2": ["network address", "host address", "broadcast address"],
    "11.3": ["unicast", "broadcast", "multicast"],
    "11.4": ["public address", "private address", "nat"],
    "11.5": ["subnet", "subnetting", "subnet mask"],
    "11.6": ["variable length subnet", "vlsm"],
    "11.7": ["structured design", "address allocation"],

    # Module 12: IPv6 Addressing
    "12.1": ["ipv6", "128-bit", "address format"],
    "12.2": ["ipv6 address types", "global unicast", "link-local"],
    "12.3": ["gua", "global unicast address"],
    "12.4": ["lla", "link-local address", "fe80"],
    "12.5": ["slaac", "stateless address autoconfiguration"],
    "12.6": ["dhcpv6", "stateful dhcp"],

    # Module 13: ICMP
    "13.1": ["icmp", "echo request", "echo reply", "ping"],
    "13.2": ["icmpv6", "router solicitation", "router advertisement"],
    "13.3": ["traceroute", "tracert", "ttl exceeded"],

    # Module 14: Transport Layer
    "14.1": ["transport layer", "tcp", "udp", "port number"],
    "14.2": ["tcp", "reliable", "flow control", "three-way handshake"],
    "14.3": ["udp", "connectionless", "unreliable", "best effort"],
    "14.4": ["port number", "well-known port", "socket"],
    "14.5": ["tcp segment", "sequence number", "acknowledgment"],
    "14.6": ["tcp session", "syn", "ack", "fin"],
    "14.7": ["flow control", "window size", "congestion"],

    # Module 15: Application Layer
    "15.1": ["application layer", "client-server", "peer-to-peer"],
    "15.2": ["dns", "domain name", "name resolution"],
    "15.3": ["dhcp", "dynamic host configuration", "ip address assignment"],
    "15.4": ["email", "smtp", "pop3", "imap"],
    "15.5": ["http", "https", "web server", "url"],
    "15.6": ["ftp", "file transfer", "tftp"],

    # Module 16: Network Security
    "16.1": ["security threat", "attack", "vulnerability"],
    "16.2": ["social engineering", "phishing", "pretexting"],
    "16.3": ["network attack", "ddos", "mitm", "reconnaissance"],
    "16.4": ["firewall", "ids", "ips", "security appliance"],

    # Module 17: Build a Small Network
    "17.1": ["network device", "router selection", "switch selection"],
    "17.2": ["ip addressing scheme", "address planning"],
    "17.3": ["network redundancy", "failover"],
    "17.4": ["traffic management", "qos", "bandwidth"],
    "17.5": ["network verification", "connectivity test"],
    "17.6": ["host verification", "ipconfig", "netstat"],
    "17.7": ["troubleshooting", "network problem", "diagnose"],
    "17.8": ["documentation", "network diagram", "baseline"],
}


def find_best_section(front: str, back: str) -> Optional[str]:
    """Find the best matching section for an atom based on content."""
    content = (front + " " + back).lower()

    best_match = None
    best_score = 0

    for section_id, keywords in SECTION_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in content:
                score += 1
                # Bonus for exact phrase match
                if f" {keyword.lower()} " in f" {content} ":
                    score += 0.5

        if score > best_score:
            best_score = score
            best_match = section_id

    # Require at least 2 keyword matches for confidence
    if best_score >= 2:
        return best_match
    return None


def link_atoms_to_sections(dry_run: bool = False) -> tuple[int, int]:
    """Link atoms to sections based on content analysis."""
    from src.db.database import engine

    linked = 0
    skipped = 0

    with engine.connect() as conn:
        # Get atoms without section links
        result = conn.execute(text("""
            SELECT id, front, back, ccna_section_id
            FROM clean_atoms
            WHERE ccna_section_id IS NULL
        """))

        atoms = list(result)
        rprint(f"\n[bold]Analyzing {len(atoms)} atoms without section links[/bold]\n")

        for row in atoms:
            section_id = find_best_section(row.front or "", row.back or "")

            if section_id:
                # Verify section exists
                check = conn.execute(
                    text("SELECT 1 FROM ccna_sections WHERE section_id = :id"),
                    {"id": section_id}
                )
                if not check.fetchone():
                    rprint(f"  [yellow]Section {section_id} not in database[/yellow]")
                    skipped += 1
                    continue

                if not dry_run:
                    conn.execute(
                        text("UPDATE clean_atoms SET ccna_section_id = :section WHERE id = :id"),
                        {"section": section_id, "id": row.id}
                    )
                    conn.commit()

                rprint(f"  [green][+][/green] Linked atom to {section_id}: {row.front[:50]}...")
                linked += 1
            else:
                rprint(f"  [yellow][-][/yellow] No match: {row.front[:50]}...")
                skipped += 1

    return linked, skipped


def main():
    parser = argparse.ArgumentParser(description="Link atoms to CCNA sections")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    rprint("\n[bold]Link Atoms to CCNA Sections[/bold]\n")

    if args.dry_run:
        rprint("[yellow]DRY RUN - No changes will be made[/yellow]")

    linked, skipped = link_atoms_to_sections(dry_run=args.dry_run)

    rprint(f"\n[bold]Results:[/bold]")
    rprint(f"  Linked: {linked}")
    rprint(f"  Skipped: {skipped}")

    if args.dry_run and linked > 0:
        rprint(f"\n[yellow]Run without --dry-run to apply changes[/yellow]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
