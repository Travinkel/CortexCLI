"""
Resilient Hydration Pipeline.

Master script to fully populate the CCNA learning database with enhanced resilience.
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings
from src.generation.ccna_atom_factory import CCNAAtomFactory
from src.db.utils import ensure_schema_compliance
from scripts.db_to_deck import main as db_to_deck_sync

# Configure logging to also write to a file
logger.add("logs/resilient_hydrate.log", rotation="500 MB", level="INFO")

async def main():
    """Run the full resilient hydration pipeline."""
    logger.info("🚀 Starting Resilient Hydration Pipeline...")

    settings = get_settings()
    engine = create_engine(settings.db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 1. Run Schema Fix (Self-Healing DB)
    logger.info("1. Running Schema Compliance Check...")
    try:
        ensure_schema_compliance()
    except Exception as e:
        logger.error(f"Schema compliance check failed: {e}")
        sys.exit(1)

    # 2. Initialize Factory with strict serial processing
    factory = CCNAAtomFactory(concurrency=1)

    # 3. Generation Passes
    # Define generation passes with module numbers and atom types
    # We'll fetch existing counts to skip if enough atoms already exist
    generation_config = [
        {"name": "Numeric Pass", "modules": [5, 11, 12], "atom_type": "numeric", "min_count": 50},
        {"name": "Parsons Pass", "modules": [2, 7, 10, 12, 16, 17], "atom_type": "parsons", "min_count": 50},
        {"name": "Concept Pass (MCQ)", "modules": [1, 3, 4, 6, 8, 9], "atom_type": "mcq", "min_count": 50},
        # Add other passes as needed, e.g., for visuals
    ]

    for config in generation_config:
        pass_name = config["name"]
        modules_to_process = config["modules"]
        target_atom_type = config["atom_type"]
        min_count = config["min_count"]

        logger.info(f"🎬 Starting {pass_name} for modules: {modules_to_process}")

        for module_num in modules_to_process:
            with SessionLocal() as session:
                # Check existing atom count for this type and module
                existing_count_query = text(
                    "SELECT COUNT(*) FROM learning_atoms WHERE module_number = :module_num AND atom_type = :atom_type"
                )
                existing_count = session.execute(
                    existing_count_query, {"module_num": module_num, "atom_type": target_atom_type}
                ).scalar_one()

                if existing_count >= min_count:
                    logger.info(
                        f"  > Module {module_num} already has {existing_count} {target_atom_type} atoms. Skipping."
                    )
                    continue

            logger.info(f"  > Processing Module {module_num} for {target_atom_type} atoms...")
            try:
                # Process module, but only generate the target atom type
                # This requires a modification to CCNAAtomFactory.process_module or a new method
                # For now, we'll call process_module and filter atom_types in its settings
                
                # Temporarily override atom_types for this pass
                original_get_module_settings = factory.get_module_settings
                def custom_get_module_settings(mn):
                    settings = original_get_module_settings(mn)
                    settings["atom_types"] = [target_atom_type]
                    return settings
                factory.get_module_settings = custom_get_module_settings

                result = await factory.process_module(module_num, chunk_limit=1) # Process one chunk at a time
                
                # Restore original get_module_settings
                factory.get_module_settings = original_get_module_settings

                if result.atoms:
                    logger.info(
                        f"  > Generated {len(result.atoms)} {target_atom_type} atoms for Module {module_num}."
                    )
                    # In a real scenario, you'd save these to the DB here.
                    # For now, we're just generating and exporting at the end.
                else:
                    logger.warning(f"  > No {target_atom_type} atoms generated for Module {module_num}.")

            except Exception as e:
                logger.error(f"  > Failed to process module {module_num} for {target_atom_type}: {e}")

    # 4. Visual Hydration (Integrated Loop)
    logger.info("🎨 Starting Visual Hydration Pass...")
    # This part would typically involve querying the DB for atoms needing visuals,
    # generating Mermaid code, and updating those atoms in the DB.
    # For this example, we'll simulate by reprocessing a module known to have visuals.
    # A more robust solution would involve a dedicated visual hydration factory.
    visual_modules = [4, 10, 17] # Example modules that might have visuals
    for module_num in visual_modules:
        logger.info(f"  > Simulating visual hydration for Module {module_num}...")
        try:
            # This would ideally be a separate process that takes existing atoms and adds media_code
            # For now, we'll just run process_module again, assuming it can generate visuals if prompted
            # and the schema is now compliant.
            result = await factory.process_module(module_num, chunk_limit=1)
            if result.atoms:
                visual_atoms_count = sum(1 for atom in result.atoms if atom.media_type == "mermaid")
                logger.info(f"    > Generated/Processed {visual_atoms_count} visual atoms for Module {module_num}.")
        except Exception as e:
            logger.error(f"  > Visual hydration for module {module_num} failed: {e}")


    # 5. Auto-Export (Deck Sync)
    logger.info(" syncing deck to outputs/...")
    try:
        db_to_deck_sync()
    except Exception as e:
        logger.error(f"Deck sync failed: {e}")
        sys.exit(1)

    logger.info("✅ Resilient Hydration Pipeline Complete!")

if __name__ == "__main__":
    asyncio.run(main())
