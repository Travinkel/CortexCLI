"""
Service for managing struggle weights.
"""

import yaml
from pathlib import Path
from sqlalchemy.orm import Session
from src.db.models import StruggleWeight
from rich.console import Console

console = Console()

def get_all_struggles(db: Session):
    """
    Get all struggle weights.
    """
    return db.query(StruggleWeight).all()

def import_struggles_from_yaml(db: Session):
    """
    Import struggles from struggles.yaml.
    """
    project_root = Path(__file__).parent.parent.parent
    yaml_path = project_root / "struggles.yaml"
    if not yaml_path.exists():
        return {"imported": 0, "error": "struggles.yaml not found"}

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not data or "struggles" not in data:
        return {"imported": 0, "error": "No struggles found in struggles.yaml"}

    struggles = data["struggles"]
    severity_to_weight = {
        "critical": 1.0,
        "high": 0.75,
        "medium": 0.5,
        "low": 0.25,
    }

    imported = 0
    errors = []

    for struggle in struggles:
        module = struggle.get("module")
        if not module:
            continue

        severity = struggle.get("severity", "medium")
        weight = severity_to_weight.get(severity, 0.5)
        failure_modes = struggle.get("failure_modes", [])
        notes = struggle.get("notes", "")
        sections = struggle.get("sections", [])

        try:
            # Insert module-level weight
            db.merge(StruggleWeight(
                module_number=module,
                section_id=None,
                severity=severity,
                weight=weight,
                failure_modes=failure_modes,
                notes=notes,
            ))
            imported += 1

            # Also insert section-level weights if specified
            for section_id in sections:
                db.merge(StruggleWeight(
                    module_number=module,
                    section_id=str(section_id),
                    severity=severity,
                    weight=weight,
                    failure_modes=failure_modes,
                    notes=notes,
                ))
                imported += 1

        except Exception as e:
            errors.append(f"Module {module}: {e}")

    db.commit()

    return {"imported": imported, "errors": errors}
