"""
Final Hydration Pipeline.

Master script to fully populate the CCNA learning database.
"""
import asyncio
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation.ccna_atom_factory import CCNAAtomFactory
from scripts.fix_schema import main as fix_schema
from scripts.db_to_deck import main as db_to_deck

async def main():
    """Run the full hydration pipeline."""
    logger.info("🚀 Starting Final Hydration Pipeline...")

    # 1. Fix Schema
    logger.info("1. Running Schema Fix...")
    try:
        fix_schema()
    except Exception as e:
        logger.error(f"Schema fix failed: {e}")
        return

    # 2. Initialize Factory
    factory = CCNAAtomFactory(concurrency=1) # Use serial processing

    # 3. Generation Passes
    passes = {
        "Math": [5, 11, 12],
        "Parsons": [2, 7, 10, 12, 16, 17],
        "Concept": [1, 3, 4, 6, 8, 9],
    }

    for pass_name, modules in passes.items():
        logger.info(f"🎬 Starting {pass_name} Pass for modules: {modules}")
        for module_num in modules:
            try:
                # Here you would add logic to check if the pass is needed, e.g., by checking atom counts
                # For now, we run it every time.
                logger.info(f"  > Processing Module {module_num}...")
                result = await factory.process_module(module_num)
                factory.export_results(result)
            except Exception as e:
                logger.error(f"  > Failed to process module {module_num}: {e}")

    # 4. Visual Hydration (Simplified for this example)
    logger.info("🎨 Starting Visual Hydration Pass...")
    # In a real scenario, you would iterate through atoms needing visuals.
    # For this example, we'll just re-process a module known to have visuals.
    try:
        logger.info("  > Processing Module 4 for visuals...")
        result = await factory.process_module(4)
        factory.export_results(result)
    except Exception as e:
        logger.error(f"  > Visual hydration for module 4 failed: {e}")

    # 5. Deck Sync
    logger.info(" syncing deck to outputs/...")
    try:
        db_to_deck()
    except Exception as e:
        logger.error(f"Deck sync failed: {e}")

    logger.info("✅ Final Hydration Pipeline Complete!")

if __name__ == "__main__":
    asyncio.run(main())
