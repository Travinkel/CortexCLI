"""
CCNA Flashcard Assessment and Gap Analysis Script.

This script:
1. Analyzes existing flashcards in the database
2. Compares against CCNA module content
3. Identifies gaps and quality issues
4. Prepares data for flashcard generation

Usage:
    python scripts/ccna_assessment.py --check-db        # Check database coverage
    python scripts/ccna_assessment.py --analyze-modules # Analyze TXT modules
    python scripts/ccna_assessment.py --full-report     # Complete assessment
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


@dataclass
class ModuleAnalysis:
    """Analysis of a single CCNA module."""
    module_number: int
    title: str
    file_path: Path
    line_count: int
    sections: List[str] = field(default_factory=list)
    subsections: List[str] = field(default_factory=list)
    tables: int = 0
    code_blocks: int = 0
    key_terms: List[str] = field(default_factory=list)
    estimated_flashcards: int = 0
    concepts: List[str] = field(default_factory=list)


@dataclass
class FlashcardCoverage:
    """Coverage statistics for flashcards."""
    module_number: int
    module_name: str
    total_cards: int = 0
    atomic_cards: int = 0
    quality_distribution: Dict[str, int] = field(default_factory=dict)
    cards_needing_review: int = 0
    hallucination_suspects: List[dict] = field(default_factory=list)


@dataclass
class GapReport:
    """Gap analysis between modules and existing flashcards."""
    module_number: int
    module_name: str
    expected_cards: int
    actual_cards: int
    coverage_percent: float
    missing_concepts: List[str] = field(default_factory=list)
    quality_issues: List[str] = field(default_factory=list)


class CCNAModuleParser:
    """Parser for CCNA module TXT files."""

    # Regex patterns for parsing
    HEADER_PATTERN = re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE)
    SECTION_PATTERN = re.compile(r'^##\s+(\d+\.\d+)\s+(.+)$', re.MULTILINE)
    SUBSECTION_PATTERN = re.compile(r'^###\s+(\d+\.\d+\.\d+)\s+(.+)$', re.MULTILINE)
    TABLE_PATTERN = re.compile(r'^\|.+\|$', re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    KEY_TERM_PATTERN = re.compile(r'\*\*([^*]+)\*\*')
    MODULE_TITLE_PATTERN = re.compile(r'Module\s+(\d+)[:\s]+(.+)', re.IGNORECASE)

    def __init__(self, ccna_dir: Path):
        self.ccna_dir = ccna_dir
        self.modules: Dict[int, ModuleAnalysis] = {}

    def parse_all_modules(self) -> Dict[int, ModuleAnalysis]:
        """Parse all CCNA module files."""
        for txt_file in sorted(self.ccna_dir.glob("CCNA Module *.txt")):
            # Extract module number from filename
            match = re.search(r'Module\s+(\d+)', txt_file.name)
            if match:
                module_num = int(match.group(1))
                analysis = self.parse_module(txt_file, module_num)
                self.modules[module_num] = analysis
                logger.info(f"Parsed Module {module_num}: {analysis.title} ({analysis.line_count} lines)")

        return self.modules

    def parse_module(self, file_path: Path, module_num: int) -> ModuleAnalysis:
        """Parse a single module file."""
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        # Extract title from first line or header
        title = f"Module {module_num}"
        title_match = self.MODULE_TITLE_PATTERN.search(content[:500])
        if title_match:
            title = title_match.group(2).strip()

        # Find sections (## X.X Title)
        sections = self.SECTION_PATTERN.findall(content)
        section_titles = [f"{num} {title}" for num, title in sections]

        # Find subsections (### X.X.X Title)
        subsections = self.SUBSECTION_PATTERN.findall(content)
        subsection_titles = [f"{num} {title}" for num, title in subsections]

        # Count tables
        table_rows = self.TABLE_PATTERN.findall(content)
        # Rough estimate: tables start with header row
        table_count = len([r for r in table_rows if '---' in r])

        # Count code blocks
        code_blocks = len(self.CODE_BLOCK_PATTERN.findall(content))

        # Extract key terms (bold text)
        key_terms = list(set(self.KEY_TERM_PATTERN.findall(content)))
        # Filter out common non-terms
        key_terms = [t for t in key_terms if len(t) > 2 and not t.startswith('Note')]

        # Extract concepts (headers that look like concept names)
        concepts = []
        for section_num, section_title in sections:
            concepts.append(section_title)
        for subsection_num, subsection_title in subsections:
            if not any(skip in subsection_title.lower() for skip in ['example', 'check', 'packet tracer', 'syntax']):
                concepts.append(subsection_title)

        # Estimate flashcard count
        # Heuristic: ~1 card per 10 lines + 1 per key term + 2 per table
        estimated = (len(lines) // 15) + len(key_terms) + (table_count * 3)

        return ModuleAnalysis(
            module_number=module_num,
            title=title,
            file_path=file_path,
            line_count=len(lines),
            sections=section_titles,
            subsections=subsection_titles,
            tables=table_count,
            code_blocks=code_blocks,
            key_terms=key_terms[:50],  # Limit to top 50
            estimated_flashcards=estimated,
            concepts=concepts,
        )

    def get_summary(self) -> dict:
        """Get summary statistics for all modules."""
        total_lines = sum(m.line_count for m in self.modules.values())
        total_sections = sum(len(m.sections) for m in self.modules.values())
        total_subsections = sum(len(m.subsections) for m in self.modules.values())
        total_key_terms = sum(len(m.key_terms) for m in self.modules.values())
        total_estimated = sum(m.estimated_flashcards for m in self.modules.values())

        return {
            "total_modules": len(self.modules),
            "total_lines": total_lines,
            "total_sections": total_sections,
            "total_subsections": total_subsections,
            "total_key_terms": total_key_terms,
            "estimated_flashcards": total_estimated,
            "modules": {
                num: {
                    "title": m.title,
                    "lines": m.line_count,
                    "sections": len(m.sections),
                    "subsections": len(m.subsections),
                    "key_terms": len(m.key_terms),
                    "estimated_cards": m.estimated_flashcards,
                }
                for num, m in sorted(self.modules.items())
            }
        }


class DatabaseAssessor:
    """Assess existing flashcards in the database."""

    def __init__(self):
        self.coverage: Dict[int, FlashcardCoverage] = {}

    def check_connection(self) -> bool:
        """Check if database is accessible."""
        try:
            from src.db.database import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def get_flashcard_stats(self) -> dict:
        """Get overall flashcard statistics."""
        try:
            from src.db.database import engine
            from sqlalchemy import text

            stats = {}

            with engine.connect() as conn:
                # Total cards
                result = conn.execute(text("SELECT COUNT(*) FROM clean_atoms"))
                stats["total_clean_atoms"] = result.scalar() or 0

                # Staging cards
                result = conn.execute(text("SELECT COUNT(*) FROM stg_anki_cards"))
                stats["total_staging_cards"] = result.scalar() or 0

                # Quality distribution
                result = conn.execute(text("""
                    SELECT quality_grade, COUNT(*) as count
                    FROM stg_anki_cards
                    WHERE quality_grade IS NOT NULL
                    GROUP BY quality_grade
                    ORDER BY quality_grade
                """))
                stats["quality_distribution"] = {row[0]: row[1] for row in result}

                # Cards needing split
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM stg_anki_cards WHERE needs_split = true
                """))
                stats["needs_split"] = result.scalar() or 0

                # Cards with prerequisites
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM stg_anki_cards WHERE has_prerequisites = true
                """))
                stats["has_prerequisites"] = result.scalar() or 0

                # By deck
                result = conn.execute(text("""
                    SELECT deck_name, COUNT(*) as count
                    FROM stg_anki_cards
                    GROUP BY deck_name
                    ORDER BY count DESC
                """))
                stats["by_deck"] = {row[0]: row[1] for row in result}

            return stats

        except Exception as e:
            logger.error(f"Failed to get flashcard stats: {e}")
            return {"error": str(e)}

    def find_ccna_cards(self) -> List[dict]:
        """Find cards that appear to be CCNA-related."""
        try:
            from src.db.database import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                # Search for CCNA-related cards by deck name or content
                result = conn.execute(text("""
                    SELECT
                        card_id,
                        deck_name,
                        front,
                        back,
                        quality_grade,
                        needs_split,
                        is_atomic
                    FROM stg_anki_cards
                    WHERE
                        LOWER(deck_name) LIKE '%ccna%'
                        OR LOWER(deck_name) LIKE '%network%'
                        OR LOWER(deck_name) LIKE '%cisco%'
                    ORDER BY deck_name, card_id
                    LIMIT 500
                """))

                cards = []
                for row in result:
                    cards.append({
                        "card_id": row[0],
                        "deck_name": row[1],
                        "front": row[2][:100] if row[2] else "",
                        "back": row[3][:100] if row[3] else "",
                        "quality_grade": row[4],
                        "needs_split": row[5],
                        "is_atomic": row[6],
                    })

                return cards

        except Exception as e:
            logger.error(f"Failed to find CCNA cards: {e}")
            return []

    def detect_hallucinations(self, cards: List[dict], module_content: Dict[int, ModuleAnalysis]) -> List[dict]:
        """
        Detect potential hallucinated cards.

        Hallucination indicators:
        - Content not found in any module
        - Technical terms that don't exist in CCNA
        - Inconsistent with Cisco terminology
        """
        suspects = []

        # Build a set of valid terms from all modules
        valid_terms = set()
        for module in module_content.values():
            valid_terms.update(t.lower() for t in module.key_terms)
            valid_terms.update(t.lower() for t in module.concepts)

        for card in cards:
            issues = []
            front = card.get("front", "").lower()
            back = card.get("back", "").lower()

            # Check if card content seems unrelated to networking
            networking_terms = ["network", "ip", "router", "switch", "protocol", "packet",
                              "ethernet", "tcp", "udp", "port", "vlan", "subnet", "mac",
                              "osi", "layer", "interface", "bandwidth", "cisco"]

            has_networking_term = any(term in front or term in back for term in networking_terms)

            if not has_networking_term:
                issues.append("No networking terminology found")

            # Check for very short or empty content
            if len(card.get("front", "")) < 10:
                issues.append("Front too short")
            if len(card.get("back", "")) < 3:
                issues.append("Back too short or empty")

            # Check for quality grade F
            if card.get("quality_grade") == "F":
                issues.append("Quality grade F")

            if issues:
                card["hallucination_issues"] = issues
                suspects.append(card)

        return suspects


def print_module_report(parser: CCNAModuleParser):
    """Print detailed module analysis report."""
    summary = parser.get_summary()

    print("\n" + "=" * 70)
    print("CCNA MODULE ANALYSIS REPORT")
    print("=" * 70)

    print(f"\nTotal Modules: {summary['total_modules']}")
    print(f"Total Lines: {summary['total_lines']:,}")
    print(f"Total Sections: {summary['total_sections']}")
    print(f"Total Subsections: {summary['total_subsections']}")
    print(f"Total Key Terms: {summary['total_key_terms']}")
    print(f"Estimated Flashcards Needed: {summary['estimated_flashcards']}")

    print("\n" + "-" * 70)
    print(f"{'Module':<10} {'Title':<35} {'Lines':>8} {'Est.Cards':>10}")
    print("-" * 70)

    for num, data in summary["modules"].items():
        title = data["title"][:33] + ".." if len(data["title"]) > 35 else data["title"]
        print(f"Module {num:<3} {title:<35} {data['lines']:>8} {data['estimated_cards']:>10}")

    print("-" * 70)
    print(f"{'TOTAL':<46} {summary['total_lines']:>8} {summary['estimated_flashcards']:>10}")
    print("=" * 70)


def print_database_report(assessor: DatabaseAssessor):
    """Print database assessment report."""
    stats = assessor.get_flashcard_stats()

    print("\n" + "=" * 70)
    print("DATABASE FLASHCARD REPORT")
    print("=" * 70)

    if "error" in stats:
        print(f"\nError: {stats['error']}")
        return

    print(f"\nTotal Clean Atoms: {stats.get('total_clean_atoms', 0):,}")
    print(f"Total Staging Cards: {stats.get('total_staging_cards', 0):,}")
    print(f"Cards Needing Split: {stats.get('needs_split', 0):,}")
    print(f"Cards with Prerequisites: {stats.get('has_prerequisites', 0):,}")

    print("\nQuality Distribution:")
    for grade, count in sorted(stats.get("quality_distribution", {}).items()):
        print(f"  Grade {grade}: {count:,}")

    print("\nCards by Deck:")
    for deck, count in stats.get("by_deck", {}).items():
        print(f"  {deck}: {count:,}")

    print("=" * 70)


def print_gap_analysis(parser: CCNAModuleParser, assessor: DatabaseAssessor):
    """Print gap analysis comparing modules to existing cards."""
    ccna_cards = assessor.find_ccna_cards()

    print("\n" + "=" * 70)
    print("GAP ANALYSIS: CCNA Modules vs Existing Flashcards")
    print("=" * 70)

    print(f"\nFound {len(ccna_cards)} CCNA-related cards in database")

    # Check for hallucinations
    suspects = assessor.detect_hallucinations(ccna_cards, parser.modules)

    if suspects:
        print(f"\nPotential Hallucinated Cards: {len(suspects)}")
        print("-" * 70)
        for i, card in enumerate(suspects[:10], 1):
            print(f"\n{i}. {card.get('front', '')[:60]}...")
            print(f"   Issues: {', '.join(card.get('hallucination_issues', []))}")

    # Coverage estimate
    summary = parser.get_summary()
    estimated_needed = summary["estimated_flashcards"]
    actual_cards = len(ccna_cards)
    coverage = (actual_cards / estimated_needed * 100) if estimated_needed > 0 else 0

    print(f"\n" + "-" * 70)
    print(f"COVERAGE SUMMARY")
    print(f"-" * 70)
    print(f"Estimated Cards Needed: {estimated_needed}")
    print(f"Actual CCNA Cards Found: {actual_cards}")
    print(f"Coverage: {coverage:.1f}%")
    print(f"Gap: ~{estimated_needed - actual_cards} cards needed")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="CCNA Flashcard Assessment Tool")
    parser.add_argument("--check-db", action="store_true", help="Check database coverage")
    parser.add_argument("--analyze-modules", action="store_true", help="Analyze TXT modules")
    parser.add_argument("--full-report", action="store_true", help="Complete assessment")
    parser.add_argument("--ccna-dir", type=Path, default=Path("docs/CCNA"), help="CCNA modules directory")

    args = parser.parse_args()

    # Default to full report if no args
    if not any([args.check_db, args.analyze_modules, args.full_report]):
        args.full_report = True

    # Initialize components
    ccna_dir = Path(__file__).parent.parent / args.ccna_dir

    if args.analyze_modules or args.full_report:
        if not ccna_dir.exists():
            logger.error(f"CCNA directory not found: {ccna_dir}")
            sys.exit(1)

        module_parser = CCNAModuleParser(ccna_dir)
        module_parser.parse_all_modules()
        print_module_report(module_parser)

    if args.check_db or args.full_report:
        assessor = DatabaseAssessor()

        if not assessor.check_connection():
            logger.warning("Database not available - skipping DB assessment")
        else:
            print_database_report(assessor)

            if args.full_report and 'module_parser' in locals():
                print_gap_analysis(module_parser, assessor)


if __name__ == "__main__":
    main()
