"""
Finish Hydration Script.

Retries failed Parsons and Concept passes with safe concurrency (3) to avoid
429 rate limits. Skips math (already completed).

Usage:
    python scripts/finish_hydration.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.generation.ccna_atom_factory import CCNAAtomFactory


class TargetedAtomFactory(CCNAAtomFactory):
    """Specialized factory that forces a fixed set of atom types."""

    def __init__(self, target_types: list[str], **kwargs):
        super().__init__(**kwargs)
        self.target_types = target_types

    def get_module_settings(self, module_number: int) -> dict:
        return {
            "validate_math": False,
            "atom_types": self.target_types,
        }


async def main() -> None:
    print(" STARTING HYDRATION RECOVERY (Low Concurrency mode)...")
    ccna_dir = Path("docs/source-materials/CCNA")
    if not ccna_dir.exists():
        raise SystemExit(f"CCNA modules path not found: {ccna_dir}")

    # 1) Retry Parsons (Procedural CLI ordering)
    print("\n[1/2] Retrying PARSONS PASS (CLI Ordering)...")
    parsons_factory = TargetedAtomFactory(target_types=["parsons"], concurrency=3, ccna_dir=ccna_dir)
    for mod in [2, 7, 10, 16, 17]:
        print(f"  > Processing Module {mod}...")
        await parsons_factory.process_module(mod)

    # 2) Retry Concepts (MCQ/Matching discrimination)
    print("\n[2/2] Retrying CONCEPT PASS (MCQ/Matching)...")
    concept_factory = TargetedAtomFactory(target_types=["mcq", "matching"], concurrency=3, ccna_dir=ccna_dir)
    for mod in [1, 3, 4, 6, 8, 9]:
        print(f"  > Processing Module {mod}...")
        await concept_factory.process_module(mod)

    print("\n✅ RECOVERY COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
