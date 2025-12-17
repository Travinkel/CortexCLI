"""
Database utility functions.
"""
from sqlalchemy import create_engine, inspect, text
from loguru import logger

from config import get_settings

def ensure_schema_compliance():
    """
    Checks the learning_atoms table for media_code and media_type columns,
    and adds them if they are missing.
    """
    logger.info("🚀 Checking database schema compliance...")
    
    settings = get_settings()
    engine = create_engine(settings.db_url)
    
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('learning_atoms')]
    
    added_columns = False
    with engine.connect() as connection:
        if 'media_code' not in columns:
            logger.info("  > 'media_code' column not found. Adding it...")
            connection.execute(text("ALTER TABLE learning_atoms ADD COLUMN media_code TEXT"))
            added_columns = True
            
        if 'media_type' not in columns:
            logger.info("  > 'media_type' column not found. Adding it...")
            connection.execute(text("ALTER TABLE learning_atoms ADD COLUMN media_type TEXT"))
            added_columns = True
        
        if added_columns:
            connection.commit()
            logger.info("✅ Schema updated successfully.")
        else:
            logger.info("✅ Schema is already up to date.")

if __name__ == "__main__":
    ensure_schema_compliance()
