"""
Compute learnability readiness and emit a JSON report.

Rules:
- Counts atoms with front/back present.
- Ready if quality_score >= 70 (or null) AND
  (difficulty < 3 OR explanation exists in quiz_question_metadata/content_json).
- Target: >=95% ready.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, text

from config import get_settings
from src.delivery.atom_deck import AtomDeck


def _from_db() -> dict[str, float | bool | int]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(
                        CASE
                            WHEN (quality_score IS NULL OR quality_score >= 70)
                             AND (
                                COALESCE(quiz_question_metadata->'content_json'->>'explanation',
                                         quiz_question_metadata->>'explanation',
                                         '') <> ''
                                OR COALESCE(difficulty, 0) < 3
                             )
                            THEN 1 ELSE 0
                        END
                    ) AS ready
                FROM learning_atoms
                WHERE front IS NOT NULL AND back IS NOT NULL
                """
            )
        ).fetchone()
        total = int(row.total or 0)
        ready = int(row.ready or 0)
        pct = 0.0 if total == 0 else round((ready / total) * 100, 2)
        return {"total": total, "ready": ready, "ready_pct": pct, "meets_goal": pct >= 95.0}


def _from_deck() -> dict[str, float | bool | int]:
    deck = AtomDeck()
    deck.load()
    atoms = deck.filter_learnable_ready(min_quality=70)
    total = len(deck.atoms)
    ready = len(atoms)
    pct = 0.0 if total == 0 else round((ready / total) * 100, 2)
    return {"total": total, "ready": ready, "ready_pct": pct, "meets_goal": pct >= 95.0}


def main() -> None:
    try:
        metrics = _from_db()
    except Exception:
        metrics = _from_deck()

    out_path = Path("data") / "learnability_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Learnability readiness: {metrics['ready_pct']}% (goal >=95%) -> {metrics['meets_goal']}")


if __name__ == "__main__":
    main()
