"""
DB to Deck Sync.
Exports the 'learning_atoms' table to JSON files in 'outputs/' for the CLI.
"""
import json
import os
import sys
from pathlib import Path
from sqlalchemy import text

# Fix Windows encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import get_db

def main():
    print("📥 SYNCING DATABASE TO CORTEX DECK...")
    
    output_dir = PROJECT_ROOT / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    db = next(get_db())
    
    # Fetch valid atoms (quality_score is 0-1 scale, not 0-100)
    sql = text("""
        SELECT
            id, card_id, atom_type, front, back,
            quality_score, quiz_question_metadata,
            media_type, media_code, source_fact_basis
        FROM learning_atoms
        WHERE front IS NOT NULL AND back IS NOT NULL
    """)
    
    rows = db.execute(sql).fetchall()
    print(f"  > Exporting {len(rows)} atoms...")
    
    deck_data = []
    for row in rows:
        deck_data.append({
            "id": str(row.id),
            "card_id": row.card_id or f"CARD-{str(row.id)[:8]}",
            "atom_type": row.atom_type or "flashcard",
            "front": row.front,
            "back": row.back,
            "quality_score": float(row.quality_score) if row.quality_score else 0.7,
            "content_json": row.quiz_question_metadata,
            "media_type": row.media_type,
            "media_code": row.media_code,
            "difficulty": 3,
            "knowledge_type": "factual",
            "source_refs": [{"excerpt": row.source_fact_basis}] if row.source_fact_basis else [],
        })

    # Save to file
    out_file = output_dir / "cortex_master.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"atoms": deck_data}, f, indent=2)
        
    print(f"✅ Saved {len(deck_data)} atoms to {out_file}")
    print("\n👉 Now run: nls cortex start")

if __name__ == "__main__":
    main()