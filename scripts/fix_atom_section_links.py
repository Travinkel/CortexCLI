#!/usr/bin/env python
"""
Fix Atom-to-Section Links and Recalculate Mastery Counts.

This script:
1. Links learning_atoms to ccna_sections using multiple matching strategies
2. Recalculates ccna_section_mastery.atoms_total from actual atom counts
3. Validates data integrity

Usage:
    python scripts/fix_atom_section_links.py --dry-run   # Preview changes
    python scripts/fix_atom_section_links.py             # Apply changes
    python scripts/fix_atom_section_links.py --verify    # Verify after fix
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
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlalchemy import text

console = Console()


# =============================================================================
# SECTION MATCHING CONFIGURATION
# =============================================================================

# Primary keywords for each section (high confidence)
SECTION_PRIMARY_KEYWORDS = {
    # Module 1: Networking Today
    "1.2": ["client", "server", "host", "end device", "intermediary device"],
    "1.4": ["lan", "wan", "internet", "intranet", "extranet", "metropolitan area"],
    "1.5": ["dsl", "cable modem", "fiber optic", "cellular", "satellite", "dial-up"],
    "1.6": ["fault tolerance", "scalability", "qos", "quality of service", "redundancy"],
    "1.7": ["byod", "cloud computing", "powerline", "smart home", "iot"],
    "1.8": ["security threat", "malware", "virus", "worm", "trojan", "firewall", "intrusion"],

    # Module 3: Protocols and Models
    "3.2": ["protocol suite", "tcp/ip model", "protocol stack"],
    "3.3": ["application layer", "transport layer", "internet layer", "network access layer"],
    "3.4": ["encapsulation", "de-encapsulation", "pdu", "segment", "packet", "frame"],
    "3.5": ["osi model", "seven layer", "presentation layer", "session layer"],

    # Module 4: Physical Layer
    "4.2": ["physical layer", "signaling", "encoding", "bandwidth", "throughput"],
    "4.3": ["copper cable", "utp", "stp", "coaxial", "rj-45", "straight-through", "crossover"],
    "4.4": ["fiber optic", "single-mode", "multimode", "smf", "mmf"],
    "4.5": ["wireless", "wi-fi", "wlan", "802.11", "radio frequency"],

    # Module 5: Number Systems
    "5.1": ["binary", "decimal", "positional notation", "base 2"],
    "5.2": ["hexadecimal", "hex", "base 16", "nibble"],

    # Module 6: Data Link Layer
    "6.1": ["data link layer", "layer 2", "llc", "mac sublayer"],
    "6.2": ["llc sublayer", "logical link control", "802.2"],
    "6.3": ["mac sublayer", "media access control", "csma/cd", "csma/ca"],
    "6.4": ["ethernet frame", "header", "trailer", "fcs", "frame check sequence"],

    # Module 7: Ethernet Switching
    "7.1": ["ethernet", "ieee 802.3", "legacy ethernet", "10base-t"],
    "7.2": ["ethernet frame", "preamble", "sfd", "destination mac", "type field", "ethertype"],
    "7.3": ["mac address table", "dynamic mac", "switch forwarding", "flooding"],

    # Module 8: Network Layer
    "8.1": ["network layer", "layer 3", "routing", "path determination", "packet forwarding"],
    "8.2": ["ip packet", "ipv4 header", "ipv6 header", "ttl", "hop limit"],

    # Module 9: Address Resolution
    "9.1": ["destination mac", "broadcast mac", "arp request"],
    "9.2": ["arp", "address resolution protocol", "arp table", "arp cache"],
    "9.3": ["neighbor discovery", "ndp", "icmpv6", "neighbor solicitation"],

    # Module 10: Basic Router Configuration
    "10.1": ["router", "routing table", "packet forwarding decision"],
    "10.2": ["router interface", "ip address interface", "no shutdown"],
    "10.3": ["default gateway", "gateway of last resort", "ip default-gateway"],
    "10.4": ["switch svi", "vlan interface", "management interface", "switch virtual interface"],

    # Module 11: IPv4 Addressing
    "11.1": ["ipv4 address", "network portion", "host portion", "dotted decimal"],
    "11.2": ["network address", "broadcast address", "first usable", "last usable"],
    "11.3": ["unicast", "broadcast", "multicast", "224."],
    "11.4": ["public address", "private address", "nat", "10.", "172.16", "192.168"],
    "11.5": ["subnet", "subnetting", "subnet mask", "cidr", "/24", "/16"],
    "11.6": ["vlsm", "variable length subnet mask", "address allocation"],
    "11.7": ["address scheme", "ip addressing design", "hierarchical addressing"],

    # Module 12: IPv6 Addressing
    "12.1": ["ipv6", "128-bit", "colon hexadecimal", "hextet"],
    "12.2": ["ipv6 address type", "global unicast", "link-local", "loopback", "::1"],
    "12.3": ["gua", "global unicast address", "2000::", "global routing prefix"],
    "12.4": ["link-local address", "fe80::", "lla"],
    "12.5": ["slaac", "stateless address autoconfiguration", "eui-64"],
    "12.6": ["dhcpv6", "stateful dhcpv6", "stateless dhcpv6"],

    # Module 13: ICMP
    "13.1": ["icmp", "echo request", "echo reply", "ping", "type 8", "type 0"],
    "13.2": ["icmpv6", "router solicitation", "router advertisement", "rs", "ra"],
    "13.3": ["traceroute", "tracert", "ttl exceeded", "time exceeded"],

    # Module 14: Transport Layer
    "14.1": ["transport layer", "layer 4", "tcp", "udp", "port number", "socket"],
    "14.2": ["tcp", "reliable delivery", "flow control", "ordered delivery", "error recovery"],
    "14.3": ["udp", "connectionless", "best effort", "unreliable", "low overhead"],
    "14.4": ["port number", "well-known port", "registered port", "dynamic port", "socket pair"],
    "14.5": ["tcp segment", "sequence number", "acknowledgment number", "window size"],
    "14.6": ["three-way handshake", "syn", "syn-ack", "ack", "session establishment"],
    "14.7": ["flow control", "window", "congestion avoidance", "slow start"],

    # Module 15: Application Layer
    "15.1": ["application layer", "layer 7", "client-server", "peer-to-peer", "p2p"],
    "15.2": ["dns", "domain name system", "name resolution", "fqdn", "a record", "aaaa record"],
    "15.3": ["dhcp", "dynamic host configuration", "dhcp discover", "dhcp offer", "dora"],
    "15.4": ["email", "smtp", "pop3", "imap", "mua", "mta", "mda"],
    "15.5": ["http", "https", "web server", "url", "uri", "get", "post"],
    "15.6": ["ftp", "file transfer protocol", "tftp", "sftp", "active mode", "passive mode"],

    # Module 16: Network Security
    "16.1": ["security threat", "attack vector", "vulnerability", "exploit"],
    "16.2": ["social engineering", "phishing", "spear phishing", "pretexting", "vishing"],
    "16.3": ["network attack", "ddos", "dos", "man-in-the-middle", "mitm", "reconnaissance"],
    "16.4": ["firewall", "ids", "ips", "acl", "access control list", "security appliance"],

    # Module 17: Build a Small Network
    "17.1": ["network device selection", "router selection", "switch selection", "capacity"],
    "17.2": ["ip addressing scheme", "address planning", "addressing strategy"],
    "17.3": ["network redundancy", "failover", "stp", "spanning tree", "etherchannel"],
    "17.4": ["traffic management", "qos", "bandwidth management", "priority queuing"],
    "17.5": ["connectivity test", "ping test", "traceroute test", "network verification"],
    "17.6": ["ipconfig", "netstat", "nslookup", "host command"],
    "17.7": ["troubleshooting", "diagnose", "network problem", "connectivity issue"],
    "17.8": ["network documentation", "network diagram", "baseline", "topology diagram"],
}

# Module number from section ID (e.g., "11.4" -> 11)
def get_module_from_section(section_id: str) -> int:
    """Extract module number from section ID."""
    return int(section_id.split(".")[0])


@dataclass
class LinkResult:
    """Result of linking an atom to a section."""
    atom_id: str
    section_id: Optional[str]
    confidence: float
    method: str  # "keyword", "module", "none"


def score_section_match(content: str, section_id: str) -> float:
    """Score how well content matches a section's keywords."""
    content_lower = content.lower()
    keywords = SECTION_PRIMARY_KEYWORDS.get(section_id, [])

    if not keywords:
        return 0.0

    score = 0.0
    matched_keywords = 0

    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in content_lower:
            matched_keywords += 1
            # Bonus for word boundary match
            if re.search(rf'\b{re.escape(keyword_lower)}\b', content_lower):
                score += 1.5
            else:
                score += 1.0

    # Normalize by keyword count
    if keywords:
        score = score / len(keywords)

    return score


def find_best_section_for_atom(front: str, back: str, module_id: Optional[str] = None) -> LinkResult:
    """Find the best matching section for an atom."""
    content = f"{front} {back}"

    best_section = None
    best_score = 0.0

    for section_id in SECTION_PRIMARY_KEYWORDS.keys():
        score = score_section_match(content, section_id)

        if score > best_score:
            best_score = score
            best_section = section_id

    # Require minimum confidence
    if best_score >= 0.15:  # At least ~15% keyword match
        return LinkResult(
            atom_id="",
            section_id=best_section,
            confidence=min(best_score, 1.0),
            method="keyword"
        )

    return LinkResult(
        atom_id="",
        section_id=None,
        confidence=0.0,
        method="none"
    )


def link_atoms_to_sections(dry_run: bool = False) -> dict:
    """Link all unlinked atoms to their appropriate sections."""
    from src.db.database import engine

    stats = {
        "total_atoms": 0,
        "already_linked": 0,
        "newly_linked": 0,
        "unmatched": 0,
        "by_section": {},
    }

    with engine.connect() as conn:
        # Get all atoms
        result = conn.execute(text("""
            SELECT id, front, back, ccna_section_id, module_id
            FROM learning_atoms
            WHERE front IS NOT NULL
        """))
        atoms = list(result)
        stats["total_atoms"] = len(atoms)

        rprint(f"\n[bold]Analyzing {len(atoms)} atoms...[/bold]\n")

        # Get valid section IDs
        sections_result = conn.execute(text("SELECT section_id FROM ccna_sections"))
        valid_sections = {row.section_id for row in sections_result}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Linking atoms...", total=len(atoms))

            for row in atoms:
                progress.advance(task)

                # Skip if already linked
                if row.ccna_section_id:
                    stats["already_linked"] += 1
                    continue

                # Find best section
                result = find_best_section_for_atom(
                    row.front or "",
                    row.back or "",
                    str(row.module_id) if row.module_id else None
                )

                if result.section_id and result.section_id in valid_sections:
                    if not dry_run:
                        conn.execute(
                            text("UPDATE learning_atoms SET ccna_section_id = :section WHERE id = :id"),
                            {"section": result.section_id, "id": row.id}
                        )

                    stats["newly_linked"] += 1
                    stats["by_section"][result.section_id] = stats["by_section"].get(result.section_id, 0) + 1
                else:
                    stats["unmatched"] += 1

        if not dry_run:
            conn.commit()

    return stats


def recalculate_mastery_counts(dry_run: bool = False) -> dict:
    """
    Recalculate atoms_total in ccna_section_mastery from actual atom counts.

    Atoms are linked to parent sections (e.g., "10.1") but mastery records may exist
    for subsections (e.g., "10.1.1"). We aggregate atoms to their parent section and
    also roll up to subsections based on hierarchy.
    """
    from src.db.database import engine

    stats = {
        "sections_updated": 0,
        "total_atoms_before": 0,
        "total_atoms_after": 0,
        "changes": [],
    }

    with engine.connect() as conn:
        # Get current totals
        result = conn.execute(text("SELECT COALESCE(SUM(atoms_total), 0) FROM ccna_section_mastery"))
        stats["total_atoms_before"] = result.scalar()

        # Calculate actual counts per section (atoms link to parent sections like "10.1")
        result = conn.execute(text("""
            SELECT
                ccna_section_id,
                COUNT(*) as actual_count
            FROM learning_atoms
            WHERE ccna_section_id IS NOT NULL
            GROUP BY ccna_section_id
        """))
        actual_counts = {row.ccna_section_id: row.actual_count for row in result}

        # Get all sections for hierarchy mapping
        result = conn.execute(text("SELECT section_id, parent_section_id FROM ccna_sections"))
        section_parents = {row.section_id: row.parent_section_id for row in result}

        # For subsections, inherit parent's atom count (proportionally divided)
        # This is a simplification - subsections share their parent's atoms
        def get_atom_count_for_section(section_id: str) -> int:
            """Get atom count for a section, checking parent if needed."""
            if section_id in actual_counts:
                return actual_counts[section_id]

            # Check if this is a subsection (X.Y.Z format)
            parts = section_id.split(".")
            if len(parts) >= 3:
                # Parent is X.Y
                parent_id = f"{parts[0]}.{parts[1]}"
                if parent_id in actual_counts:
                    # Count siblings to divide atoms
                    siblings = [s for s in section_parents.keys()
                               if s.startswith(f"{parent_id}.") and len(s.split(".")) == 3]
                    if siblings:
                        return actual_counts[parent_id] // len(siblings)

            return 0

        # Get current mastery records
        result = conn.execute(text("""
            SELECT section_id, atoms_total, atoms_new
            FROM ccna_section_mastery
        """))
        mastery_records = list(result)

        for record in mastery_records:
            actual = get_atom_count_for_section(record.section_id)
            current = record.atoms_total or 0

            if actual != current:
                stats["changes"].append({
                    "section_id": record.section_id,
                    "before": current,
                    "after": actual,
                })

                if not dry_run:
                    conn.execute(
                        text("""
                            UPDATE ccna_section_mastery
                            SET atoms_total = :total, atoms_new = :total
                            WHERE section_id = :section_id
                        """),
                        {"total": actual, "section_id": record.section_id}
                    )

                stats["sections_updated"] += 1

        if not dry_run:
            conn.commit()

        # Get new totals
        if not dry_run:
            result = conn.execute(text("SELECT COALESCE(SUM(atoms_total), 0) FROM ccna_section_mastery"))
            stats["total_atoms_after"] = result.scalar()
        else:
            # Estimate for dry run
            stats["total_atoms_after"] = sum(actual_counts.values())

    return stats


def verify_data_integrity() -> dict:
    """Verify data integrity after fixes."""
    from src.db.database import engine

    results = {}

    with engine.connect() as conn:
        # Check learning_atoms
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(ccna_section_id) as with_section,
                COUNT(DISTINCT ccna_section_id) as unique_sections
            FROM learning_atoms
        """))
        row = result.fetchone()
        results["learning_atoms"] = {
            "total": row.total,
            "with_section": row.with_section,
            "without_section": row.total - row.with_section,
            "unique_sections": row.unique_sections,
        }

        # Check mastery table
        result = conn.execute(text("""
            SELECT
                COUNT(*) as section_count,
                SUM(atoms_total) as claimed_atoms,
                SUM(atoms_mastered) as mastered,
                SUM(atoms_new) as new
            FROM ccna_section_mastery
        """))
        row = result.fetchone()
        results["ccna_section_mastery"] = {
            "section_count": row.section_count,
            "claimed_atoms": row.claimed_atoms,
            "mastered": row.mastered,
            "new": row.new,
        }

        # Verify counts match
        results["integrity"] = {
            "atoms_match": results["learning_atoms"]["with_section"] == results["ccna_section_mastery"]["claimed_atoms"],
            "actual_atoms": results["learning_atoms"]["with_section"],
            "claimed_atoms": results["ccna_section_mastery"]["claimed_atoms"],
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="Fix atom-section links and mastery counts")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--verify", action="store_true", help="Only verify current state")
    parser.add_argument("--link-only", action="store_true", help="Only link atoms, don't recalculate")
    parser.add_argument("--recalc-only", action="store_true", help="Only recalculate, don't link")
    args = parser.parse_args()

    console.print("\n[bold cyan]CCNA Data Integrity Fix[/bold cyan]\n")

    if args.verify:
        console.print("[bold]Verifying data integrity...[/bold]\n")
        results = verify_data_integrity()

        # Display results
        table = Table(title="Data Integrity Check")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Atoms", str(results["learning_atoms"]["total"]))
        table.add_row("Atoms with Section", str(results["learning_atoms"]["with_section"]))
        table.add_row("Atoms without Section", str(results["learning_atoms"]["without_section"]))
        table.add_row("Unique Sections", str(results["learning_atoms"]["unique_sections"]))
        table.add_row("---", "---")
        table.add_row("Mastery Sections", str(results["ccna_section_mastery"]["section_count"]))
        table.add_row("Claimed Atoms", str(results["ccna_section_mastery"]["claimed_atoms"]))
        table.add_row("---", "---")

        if results["integrity"]["atoms_match"]:
            table.add_row("[green]Integrity[/green]", "[green]OK[/green]")
        else:
            table.add_row("[red]Integrity[/red]", "[red]MISMATCH[/red]")
            table.add_row("Actual", str(results["integrity"]["actual_atoms"]))
            table.add_row("Claimed", str(results["integrity"]["claimed_atoms"]))

        console.print(table)
        return 0

    if args.dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")

    # Step 1: Link atoms to sections
    if not args.recalc_only:
        console.print("[bold]Step 1: Linking atoms to sections...[/bold]")
        link_stats = link_atoms_to_sections(dry_run=args.dry_run)

        console.print(f"\n  Total atoms: {link_stats['total_atoms']}")
        console.print(f"  Already linked: {link_stats['already_linked']}")
        console.print(f"  [green]Newly linked: {link_stats['newly_linked']}[/green]")
        console.print(f"  [yellow]Unmatched: {link_stats['unmatched']}[/yellow]")

        if link_stats['by_section']:
            console.print("\n  Top sections by new links:")
            sorted_sections = sorted(link_stats['by_section'].items(), key=lambda x: -x[1])[:10]
            for section, count in sorted_sections:
                console.print(f"    {section}: {count}")

    # Step 2: Recalculate mastery counts
    if not args.link_only:
        console.print("\n[bold]Step 2: Recalculating mastery counts...[/bold]")
        mastery_stats = recalculate_mastery_counts(dry_run=args.dry_run)

        console.print(f"\n  Total before: {mastery_stats['total_atoms_before']}")
        console.print(f"  Total after: {mastery_stats['total_atoms_after']}")
        console.print(f"  Sections updated: {mastery_stats['sections_updated']}")

        if mastery_stats['changes'][:5]:
            console.print("\n  Sample changes:")
            for change in mastery_stats['changes'][:5]:
                console.print(f"    {change['section_id']}: {change['before']} -> {change['after']}")

    # Verify after changes
    if not args.dry_run:
        console.print("\n[bold]Verifying results...[/bold]")
        results = verify_data_integrity()

        if results["integrity"]["atoms_match"]:
            console.print("[green]Data integrity: OK[/green]")
        else:
            console.print("[red]Data integrity: MISMATCH - manual review needed[/red]")

    if args.dry_run:
        console.print("\n[yellow]Run without --dry-run to apply changes[/yellow]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
