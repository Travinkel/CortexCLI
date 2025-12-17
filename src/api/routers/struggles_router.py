"""
API router for managing struggle weights.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.db.database import get_db
from src.adaptive import struggle_service

router = APIRouter()

@router.get("/")
def get_all_struggles(db: Session = Depends(get_db)):
    """
    Get all struggle weights.
    """
    return struggle_service.get_all_struggles(db)

@router.post("/import")
def import_struggles_from_yaml(db: Session = Depends(get_db)):
    """
    Import struggles from struggles.yaml.
    """
    try:
        result = struggle_service.import_struggles_from_yaml(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
