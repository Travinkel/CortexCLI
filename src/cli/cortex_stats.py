"""
Cortex Stats: Statistics calculation and display for the Cortex CLI.

Extracted from cortex.py for better maintainability.
Provides pre-session stats, struggle stats, and severity calculations.
"""

from __future__ import annotations

from loguru import logger
from rich.console import Console
from sqlalchemy import text

from src.db.database import engine

console = Console()


def determine_severity(weight: float, db_severity: str | None = None) -> str:
    """
    Derive severity from weight if not explicitly provided in DB.

    Args:
        weight: Struggle weight (0.0 to 1.0)
        db_severity: Severity from database (may be empty or None)

    Returns:
        Severity level: "critical", "high", "medium", or "low"
    """
    if db_severity:
        return db_severity
    if weight >= 0.9:
        return "critical"
    if weight >= 0.7:
        return "high"
    if weight >= 0.4:
        return "medium"
    return "low"


def get_pre_session_stats() -> dict:
    """
    Get pre-session statistics for the dashboard.

    Returns:
        Dict with overall_mastery, sections_total, sections_complete,
        streak_days, struggle_zones, struggle_count, due_count, new_count
    """
    try:
        with engine.connect() as conn:
            # Get overall mastery
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN nls_correct_count > nls_incorrect_count THEN 1 ELSE 0 END) as mastered
                FROM learning_atoms
                WHERE atom_type IN ('mcq', 'true_false', 'numeric', 'parsons')
            """))
            row = result.fetchone()
            total = row[0] or 1
            mastered = row[1] or 0
            overall_mastery = int((mastered / total) * 100) if total > 0 else 0

            # Get streak (placeholder)
            streak_days = 0

            # Get struggle zones (grouped by module to avoid duplicates)
            result = conn.execute(text("""
                SELECT module_number, MAX(weight) as max_weight, AVG(weight) as avg_weight
                FROM struggle_weights
                WHERE weight > 0.5
                GROUP BY module_number
                ORDER BY max_weight DESC
                LIMIT 5
            """))
            struggle_zones = [
                {
                    "module_number": row[0],
                    "weight": float(row[1]) if row[1] else 0.0,
                    "avg_priority": float(row[2]) if row[2] else 0.0,
                }
                for row in result.fetchall()
            ]

            return {
                "overall_mastery": overall_mastery,
                "sections_total": total,
                "sections_complete": mastered,
                "streak_days": streak_days,
                "struggle_zones": struggle_zones,
                "struggle_count": len(struggle_zones),
                "due_count": 0,
                "new_count": 0,
            }
    except Exception as e:
        logger.warning(f"Failed to get pre-session stats: {e}")
        return {
            "overall_mastery": 0,
            "sections_total": 0,
            "sections_complete": 0,
            "streak_days": 0,
            "struggle_zones": [],
            "struggle_count": 0,
            "due_count": 0,
            "new_count": 0,
        }


def get_struggle_stats() -> list[dict]:
    """
    Get struggle weight statistics by module with severity and mastery.

    Returns:
        List of dicts with module_number, section_id, weight, severity,
        avg_mastery, notes
    """
    try:
        with engine.connect() as conn:
            # Try full query first, fallback to minimal if columns missing
            try:
                result = conn.execute(text("""
                    SELECT module_number, section_id, weight,
                           COALESCE(severity, '') as severity,
                           COALESCE(notes, '') as notes
                    FROM struggle_weights
                    ORDER BY module_number, section_id
                """))
                rows = result.fetchall()
                has_extra = True
            except Exception:
                result = conn.execute(text("""
                    SELECT module_number, section_id, weight
                    FROM struggle_weights
                    ORDER BY module_number, section_id
                """))
                rows = result.fetchall()
                has_extra = False

            stats = []
            for row in rows:
                weight = float(row[2]) if row[2] else 0.0
                raw_severity = row[3] if has_extra and len(row) > 3 else ""
                severity = determine_severity(weight, raw_severity)
                notes = row[4] if has_extra and len(row) > 4 else ""
                # Calculate avg_mastery as inverse of weight
                avg_mastery = max(0, 100 - (weight * 100))
                stats.append({
                    "module_number": row[0],
                    "section_id": row[1],
                    "weight": weight,
                    "severity": severity,
                    "avg_mastery": avg_mastery,
                    "notes": notes or "",
                })
            return stats
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to get struggle stats: {e}[/yellow]")
        return []


def get_module_stats() -> list[dict]:
    """
    Get per-module learning statistics.

    Returns:
        List of dicts with module_number, atom_count, reviewed_count,
        mastery_pct, struggle_weight
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    cs.module_number,
                    COUNT(la.id) as atom_count,
                    COUNT(la.id) FILTER (WHERE la.anki_review_count > 0) as reviewed_count,
                    ROUND(
                        COUNT(la.id) FILTER (WHERE la.nls_correct_count > la.nls_incorrect_count)::numeric /
                        NULLIF(COUNT(la.id), 0) * 100,
                        1
                    ) as mastery_pct,
                    COALESCE(MAX(sw.weight), 0) as max_struggle
                FROM ccna_sections cs
                LEFT JOIN learning_atoms la ON la.ccna_section_id = cs.section_id
                LEFT JOIN struggle_weights sw ON sw.section_id = cs.section_id
                GROUP BY cs.module_number
                ORDER BY cs.module_number
            """))

            return [
                {
                    "module_number": row[0],
                    "atom_count": row[1] or 0,
                    "reviewed_count": row[2] or 0,
                    "mastery_pct": float(row[3]) if row[3] else 0.0,
                    "struggle_weight": float(row[4]) if row[4] else 0.0,
                }
                for row in result.fetchall()
            ]
    except Exception as e:
        logger.warning(f"Failed to get module stats: {e}")
        return []


def get_atom_type_stats() -> dict[str, int]:
    """
    Get count of atoms by type.

    Returns:
        Dict mapping atom_type to count
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT atom_type, COUNT(*) as count
                FROM learning_atoms
                WHERE front IS NOT NULL AND front != ''
                GROUP BY atom_type
                ORDER BY count DESC
            """))
            return {row[0]: row[1] for row in result.fetchall()}
    except Exception as e:
        logger.warning(f"Failed to get atom type stats: {e}")
        return {}


def get_session_history(days: int = 7) -> list[dict]:
    """
    Get recent study session history.

    Args:
        days: Number of days to look back

    Returns:
        List of session summaries
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    DATE(created_at) as session_date,
                    COUNT(*) as questions_answered,
                    SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_count,
                    AVG(response_time_ms) as avg_response_time
                FROM quiz_responses
                WHERE created_at >= CURRENT_DATE - INTERVAL ':days days'
                GROUP BY DATE(created_at)
                ORDER BY session_date DESC
            """), {"days": days})

            return [
                {
                    "date": str(row[0]),
                    "questions": row[1],
                    "correct": row[2] or 0,
                    "accuracy": round(((row[2] or 0) / max(1, row[1])) * 100, 1),
                    "avg_time_ms": int(row[3]) if row[3] else 0,
                }
                for row in result.fetchall()
            ]
    except Exception as e:
        logger.warning(f"Failed to get session history: {e}")
        return []
