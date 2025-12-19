"""
Backfill CCNA atom metadata (objective_code, prerequisites, hints, explanations).

Strategy (conservative, no schema changes):
- Reads Module text files under docs/ (Module 1 Networking Today.txt ... Module 17*.txt).
- For each learning_atom lacking hints/explanation/objective_code, attempts to:
  * Infer objective_code from concept.cluster/name when available.
  * Populate hints/explanations from quiz_question_metadata if present; otherwise,
    add a lightweight hint referencing the module title.
  * Attach prerequisite concept_ids from explicit_prerequisites when present.
  * Preserve existing metadata without overwriting user-provided values.
- Persist into quiz_question_metadata JSONB (non-destructive) and set quality_score
  minimum of 70 if blank.

Usage:
    python scripts/backfill/ccna_metadata_backfill.py

Requires: DATABASE_URL set (defaults from config.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from src.semantic.prerequisite_inference import PrerequisiteInferenceService


DOCS_PATH = Path("docs")


def _load_module_titles() -> dict[int, str]:
    """Map module number to title from filenames."""
    titles: dict[int, str] = {}
    for path in DOCS_PATH.glob("Module *.txt"):
        match = re.match(r"Module\s+(\d+)\s+(.*)\.txt", path.name)
        if match:
            num = int(match.group(1))
            titles[num] = match.group(2).strip()
    return titles


def _upsert_metadata(session: Session, atom_id: str, metadata: dict[str, Any]) -> None:
    """Merge quiz_question_metadata with new fields."""
    session.execute(
        text(
            """
            UPDATE learning_atoms
            SET quiz_question_metadata = COALESCE(quiz_question_metadata, '{}'::jsonb) || :meta::jsonb,
                quality_score = COALESCE(quality_score, 70)
            WHERE id = :atom_id::uuid
            """
        ),
        {"atom_id": atom_id, "meta": metadata},
    )


def backfill() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    module_titles = _load_module_titles()
    SessionLocal = sessionmaker(bind=engine)

    # Preload explicit prerequisites to avoid per-row lookups
    prereq_map: dict[str, list[str]] = {}
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text(
                    """
                    SELECT source_atom_id::text AS atom_id, target_concept_id::text AS concept_id
                    FROM explicit_prerequisites
                    WHERE status = 'active'
                    """
                )
            )
            for row in rows:
                prereq_map.setdefault(row.atom_id, []).append(row.concept_id)
        except Exception:
            prereq_map = {}

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, quiz_question_metadata, module_id, concept_id
                FROM learning_atoms
                WHERE (
                    quiz_question_metadata->>'explanation' IS NULL OR
                    quiz_question_metadata->>'hints' IS NULL OR
                    quiz_question_metadata->>'objective_code' IS NULL
                )
                LIMIT 500
                """
            )
        ).mappings()

        for row in rows:
            meta = row.quiz_question_metadata or {}
            hints = meta.get("hints") or []
            explanation = meta.get("explanation")
            objective_code = meta.get("objective_code")
            prereqs = meta.get("prerequisites") or []
            validation = meta.get("validation") or {}
            source_ref = meta.get("source_ref")

            updates: dict[str, Any] = {}

            if not objective_code and row.concept_id:
                updates["objective_code"] = str(row.concept_id)

            module_hint = None
            if row.module_id:
                # Attempt to map module_id to numeric order
                mod_row = conn.execute(
                    text("SELECT name FROM learning_modules WHERE id = :mid"),
                    {"mid": row.module_id},
                ).fetchone()
                if mod_row and mod_row.name:
                    module_hint = mod_row.name
                else:
                    # fallback to title from docs glob if name carries number pattern
                    match = re.search(r"(\d+)", str(mod_row.name) if mod_row else "")
                    if match:
                        module_hint = module_titles.get(int(match.group(1)))

            if not hints and module_hint:
                hints = [f"Review {module_hint} before answering."]
                updates["hints"] = hints

            if not explanation and module_hint:
                updates["explanation"] = f"Covered in {module_hint}."

            if not prereqs and str(row.id) in prereq_map:
                updates["prerequisites"] = prereq_map[str(row.id)]

            # Semantic prerequisite inference fallback (best effort)
            if not updates.get("prerequisites") and not prereqs:
                try:
                    with SessionLocal() as sess:
                        infer = PrerequisiteInferenceService(sess)
                        suggestions = infer.infer_prerequisites_for_atom(row.id, limit=2)
                        if suggestions:
                            updates["prerequisites"] = [str(s.target_concept_id) for s in suggestions]
                except Exception:
                    pass

            if not validation:
                updates["validation"] = {"flags": ["backfilled_minimum"]}

            if not source_ref and module_hint:
                updates["source_ref"] = {"module": module_hint, "range": "unknown"}

            if updates:
                _upsert_metadata(conn, str(row.id), updates)

    print("Backfill complete (non-destructive).")


if __name__ == "__main__":
    backfill()
