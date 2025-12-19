"""
Force Hydration Script.

Targeted generation for missing atom types (Numeric, Parsons) to fully populate the DB.

Usage:
    python scripts/force_hydrate.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.content.generation.ccna_atom_factory import CCNAAtomFactory


class TargetedAtomFactory(CCNAAtomFactory):
    """
    Specialized factory that overrides routing to force specific atom types.
    """

    def __init__(self, target_types: list[str], **kwargs):
        super().__init__(**kwargs)
        self.target_types = target_types

    def get_module_settings(self, module_number: int) -> dict:
        """Override module settings to enforce target types."""
        return {
            "validate_math": "numeric" in self.target_types,
            "atom_types": self.target_types,
        }


async def _run_math_pass(ccna_dir: Path) -> None:
    print("\n[1/3] Executing MATH PASS (Binary, Hex, Subnetting)...")
    math_factory = TargetedAtomFactory(target_types=["numeric"], concurrency=10, ccna_dir=ccna_dir)
    for mod in [5, 11, 12]:
        print(f"  > Processing Module {mod} for Calculation Atoms...")
        await math_factory.process_module(mod)


async def _run_parsons_pass(ccna_dir: Path) -> None:
    print("\n[2/3] Executing PROCEDURAL PASS (CLI Ordering)...")
    # Lower concurrency to reduce 429s on heavier Parsons prompts
    parsons_factory = TargetedAtomFactory(target_types=["parsons"], concurrency=3, ccna_dir=ccna_dir)
    for mod in [2, 7, 10, 12, 16, 17]:
        print(f"  > Processing Module {mod} for Parsons Problems...")
        await parsons_factory.process_module(mod)


async def _run_concept_pass(ccna_dir: Path) -> None:
    print("\n[3/3] Executing CONCEPT PASS (MCQ/Matching mix)...")
    concept_factory = TargetedAtomFactory(
        target_types=["mcq", "matching"], concurrency=3, ccna_dir=ccna_dir
    )
    for mod in [1, 3, 4, 6, 8, 9, 13, 14, 15]:
        print(f"  > Processing Module {mod} for Concept Discrimination...")
        await concept_factory.process_module(mod)


async def main() -> None:
    print(" STARTING DB HYDRATION PROTOCOL...")
    ccna_dir = Path("docs/source-materials/CCNA")
    if not ccna_dir.exists():
        raise SystemExit(f"CCNA modules path not found: {ccna_dir}")

    await _run_math_pass(ccna_dir)
    await _run_parsons_pass(ccna_dir)
    await _run_concept_pass(ccna_dir)
    print("\n✅ HYDRATION COMPLETE. The database is now fully populated.")


if __name__ == "__main__":
    asyncio.run(main())
