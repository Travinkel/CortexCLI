"""
Fix Database Schema.
Adds missing 'media_code' and 'media_type' columns to learning_atoms table.
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import get_db


def main() -> None:
    print(" Patching Database Schema...")
    db = next(get_db())

    try:
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS media_code TEXT;"))
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS media_type TEXT;"))
        db.commit()
        print("✅ Success: Added 'media_code' and 'media_type' columns.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()


if __name__ == "__main__":
    main()
