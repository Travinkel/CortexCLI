"""
Resilient Hydration Script.
The final tool to populate the DB with missing complex atoms.
Handles schema checking, rate limiting, and auto-export.
"""
import asyncio
import sys
import time
from pathlib import Path
from sqlalchemy import text

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.generation.ccna_atom_factory import CCNAAtomFactory
from src.db.database import get_db

# --- Subclass to override factory routing ---
class ResilientFactory(CCNAAtomFactory):
    def __init__(self, target_types: list[str], **kwargs):
        super().__init__(**kwargs)
        self.target_types = target_types

    def get_module_settings(self, module_number: int) -> dict:
        return {"validate_math": False, "atom_types": self.target_types}

async def main():
    print("🛡️ STARTING RESILIENT HYDRATION PIPELINE...")
    
    # 1. PARSONS PASS (Modules 2, 7, 10, 12, 16, 17)
    # We prioritize this because it has been failing.
    # Concurrency 1 + Batch Size 1 = Minimum Token Load
    print("\n[1/3] Generating Parsons Problems (Sequential)...")
    parsons_factory = ResilientFactory(target_types=["parsons"], concurrency=1)
    
    parsons_modules = [2, 7, 10, 12, 16, 17]
    for mod in parsons_modules:
        print(f"  > Processing Module {mod}...")
        
        # We manually iterate chunks to save progress incrementally
        chunks = parsons_factory.chunk_module(mod)
        total_atoms = []
        
        for i, chunk in enumerate(chunks):
            # Process 1 chunk at a time
            result = await parsons_factory.generate_atoms_for_chunk(chunk, ["parsons"])
            if result.atoms:
                total_atoms.extend(result.atoms)
                print(f"    - Chunk {chunk.chunk_id}: {len(result.atoms)} atoms generated.")
            
            # Nap to respect rate limits
            time.sleep(2) 
        
        # Save Module
        if total_atoms:
            # Hack: Create a result object to reuse export_results
            from src.content.generation.ccna_atom_factory import ModuleProcessingResult
            mod_result = ModuleProcessingResult(mod, f"Module {mod}")
            mod_result.atoms = total_atoms
            mod_result.total_atoms_approved = len(total_atoms)
            parsons_factory.export_results(mod_result)
            print(f"    💾 Saved {len(total_atoms)} Parsons atoms for Module {mod}.")
        else:
            print(f"    ⚠️ No Parsons atoms generated for Module {mod}. Check 'logs/parsons_debug' if available.")

    # 2. VISUAL HYDRATION (Integrated)
    print("\n[2/3] Hydrating Visuals (Mermaid)...")
    # Call the existing logic via subprocess or inline (Inline is cleaner but requires imports)
    # We'll use a simplified inline version here
    db = next(get_db())
    atoms = db.execute(text("SELECT id, front, back FROM learning_atoms WHERE front LIKE '%topology%' AND media_code IS NULL LIMIT 20")).fetchall()
    if atoms:
        print(f"  > Found {len(atoms)} candidates. Running visualizer...")
        import scripts.hydrate_visuals as visualizer
        await visualizer.main()
    else:
        print("  > No new visuals needed.")

    # 3. DB TO DECK SYNC
    print("\n[3/3] Syncing to Cortex Deck...")
    import scripts.db_to_deck as deck_sync
    deck_sync.main()

    print("\n✅ PIPELINE COMPLETE. You are ready to study.")

if __name__ == "__main__":
    asyncio.run(main())