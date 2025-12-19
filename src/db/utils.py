"""
Database Utility Functions.
Provides self-healing capabilities for schema drift.
"""
from loguru import logger
from sqlalchemy import text
from src.db.database import get_db

def ensure_schema_compliance():
    """
    Check for critical schema columns and add them if missing.
    Prevents crashes during visual hydration.
    """
    logger.info("🛡️ Checking database schema compliance...")
    
    # We use a raw connection to force immediate commits
    db = next(get_db())
    
    try:
        # Check 1: Media columns for Diagrams
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS media_code TEXT;"))
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS media_type TEXT;"))
        
        # Check 2: Fidelity tracking columns (if older DB)
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS is_hydrated BOOLEAN DEFAULT FALSE;"))
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS fidelity_type TEXT DEFAULT 'verbatim_extract';"))
        db.execute(text("ALTER TABLE learning_atoms ADD COLUMN IF NOT EXISTS source_fact_basis TEXT;"))
        
        db.commit()
        logger.info("✅ Database schema verified and patched.")
        
    except Exception as e:
        logger.error(f"Schema check failed: {e}")
        db.rollback()
    finally:
        db.close()