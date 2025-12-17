"""
Safely adds missing columns to the learning_atoms table.
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings

def main():
    """Adds media_code and media_type to learning_atoms if they don't exist."""
    print("🚀 Checking database schema...")
    
    settings = get_settings()
    engine = create_engine(settings.db_url)
    
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('learning_atoms')]
    
    added_columns = False
    with engine.connect() as connection:
        if 'media_code' not in columns:
            print("  > Adding 'media_code' column...")
            connection.execute(text("ALTER TABLE learning_atoms ADD COLUMN media_code TEXT"))
            added_columns = True
            
        if 'media_type' not in columns:
            print("  > Adding 'media_type' column...")
            connection.execute(text("ALTER TABLE learning_atoms ADD COLUMN media_type TEXT"))
            added_columns = True
        
        if added_columns:
            connection.commit()
            print("✅ Schema updated successfully.")
        else:
            print("✅ Schema is already up to date.")

if __name__ == "__main__":
    main()
