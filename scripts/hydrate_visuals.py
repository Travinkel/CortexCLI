"""
Visual Hydration Script.
Finds atoms that need diagrams and generates Mermaid.js code for them.
"""
import asyncio
import sys
import re
from pathlib import Path
from sqlalchemy import text

# --- PATH FIX: Add project root to sys.path BEFORE importing app modules ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# ---------------------------------------------------------------------------

from src.db.database import get_db
from src.content.generation.ccna_atom_factory import CCNAAtomFactory

MERMAID_PROMPT = """
You are a technical diagram generator.
Convert this network concept into a valid Mermaid.js diagram.

Concept: {front}
Details: {back}

Requirements:
1. Use 'graph TD' for topologies or hierarchies.
2. Use 'sequenceDiagram' for protocols/handshakes.
3. Return ONLY the code block inside ```mermaid ... ``` tags.
4. Keep it simple and readable.
"""


async def main():
    print(" STARTING VISUAL HYDRATION...")
    
    try:
        factory = CCNAAtomFactory()
        db = next(get_db())
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return
    
    # Find atoms that need visuals but don't have code yet
    sql = text("""
        SELECT id, front, back FROM learning_atoms 
        WHERE (is_hydrated = true OR front LIKE '%topology%' OR front LIKE '%process%')
        AND media_code IS NULL
        AND atom_type = 'flashcard'
        LIMIT 50
    """)
    
    atoms = db.execute(sql).fetchall()
    print(f"Found {len(atoms)} candidates for visual hydration.")
    
    for row in atoms:
        atom_id, front, back = row
        print(f"  > Generating diagram for: {front[:40]}...")
        
        try:
            prompt = MERMAID_PROMPT.format(front=front, back=back)
            response = factory.client.generate_content(prompt)
            
            match = re.search(r"```mermaid\s*([\s\S]*?)```", response.text)
            if match:
                code = match.group(1).strip()
                db.execute(
                    text("UPDATE learning_atoms SET media_code = :code, media_type = 'mermaid' WHERE id = :id"),
                    {"code": code, "id": atom_id}
                )
                db.commit()
                print("    ✅ Diagram saved.")
            else:
                print("    ⚠️ No diagram generated.")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            
    print("\n✅ VISUAL HYDRATION COMPLETE.")

if __name__ == "__main__":
    asyncio.run(main())
