"""
CCNA Curriculum Linker.

Links CCNA content to the curriculum structure:
Program → Track → Module → Atom

Creates necessary database records and provides mapping functions
for the generation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from loguru import logger

from src.ccna.content_parser import CCNAContentParser
from src.db.database import session_scope
from src.db.models.canonical import CleanModule, CleanProgram, CleanTrack


@dataclass
class CurriculumMapping:
    """Mapping from module string IDs to database UUIDs."""

    program_id: UUID | None
    track_id: UUID
    module_id_map: dict[str, UUID]  # "NET-M7" → UUID


class CurriculumLinker:
    """Link CCNA content to curriculum database records."""

    # Correct naming per user specification:
    # Program = EASV Datamatiker (the degree program)
    # Course = CCNA: Introduction to Networks (the course within the program)
    # Track = ITN (abbreviation for Introduction to Networks)
    CCNA_PROGRAM_NAME = "EASV Datamatiker (Computer Science AB at ErhvervsAkademi SydVest)"
    CCNA_TRACK_NAME = "ITN"  # Introduction to Networks abbreviation

    def __init__(self):
        """Initialize curriculum linker."""
        self.parser = CCNAContentParser()

    def ensure_curriculum_structure(self) -> CurriculumMapping:
        """
        Ensure CCNA curriculum structure exists in database.

        Creates Program, Track, and Module records if they don't exist.

        Returns:
            CurriculumMapping with all database IDs
        """
        with session_scope() as session:
            # 1. Find or create Program
            program = self._ensure_program(session)

            # 2. Find or create Track
            track = self._ensure_track(session, program.id if program else None)

            # 3. Find or create Modules
            module_map = self._ensure_modules(session, track.id)

            session.commit()

            return CurriculumMapping(
                program_id=program.id if program else None,
                track_id=track.id,
                module_id_map=module_map,
            )

    def _ensure_program(self, session) -> CleanProgram | None:
        """Find or create CCNA program."""
        program = (
            session.query(CleanProgram)
            .filter(CleanProgram.name.ilike(f"%{self.CCNA_PROGRAM_NAME}%"))
            .first()
        )

        if program:
            logger.info(f"Found existing program: {program.name}")
            return program

        # Create new program
        program = CleanProgram(
            name=self.CCNA_PROGRAM_NAME,
            description=(
                "Computer Science AB degree program (Datamatiker) at ErhvervsAkademi SydVest (EASV). "
                "2-year vocational degree covering software development, databases, and networking."
            ),
            status="active",
        )
        session.add(program)
        session.flush()

        logger.info(f"Created program: {program.name}")
        return program

    def _ensure_track(self, session, program_id: UUID | None) -> CleanTrack:
        """Find or create CCNA ITN track."""
        track = (
            session.query(CleanTrack)
            .filter(CleanTrack.name.ilike(f"%{self.CCNA_TRACK_NAME}%"))
            .first()
        )

        if not track:
            # Also check for partial matches
            track = session.query(CleanTrack).filter(CleanTrack.name.ilike("%CCNA%")).first()

        if track:
            logger.info(f"Found existing track: {track.name}")
            return track

        # Create new track
        track = CleanTrack(
            program_id=program_id,
            name=self.CCNA_TRACK_NAME,
            description=(
                "CCNA: Introduction to Networks (ITN) - First course in the Cisco Certified Network Associate curriculum. "
                "Covers networking fundamentals, protocols, and device configuration across 17 modules."
            ),
            display_order=1,
        )
        session.add(track)
        session.flush()

        logger.info(f"Created track: {track.name}")
        return track

    def _ensure_modules(self, session, track_id: UUID) -> dict[str, UUID]:
        """Find or create module records for all 17 CCNA modules."""
        module_map = {}

        # Parse all modules to get titles
        parsed_modules = self.parser.parse_all_modules()

        for parsed in parsed_modules:
            module_id = parsed.module_id  # e.g., "NET-M7"
            module_num = parsed.module_number

            # Check if module exists
            existing = (
                session.query(CleanModule)
                .filter(
                    CleanModule.track_id == track_id,
                    CleanModule.week_order == module_num,
                )
                .first()
            )

            if existing:
                module_map[module_id] = existing.id
                continue

            # Create new module
            title = parsed.title or f"Module {module_num}"
            module = CleanModule(
                track_id=track_id,
                name=f"Module {module_num}: {title}",
                description=parsed.description or f"CCNA ITN Module {module_num}",
                week_order=module_num,
                status="not_started",
            )
            session.add(module)
            session.flush()

            module_map[module_id] = module.id
            logger.debug(f"Created module: {module.name}")

        logger.info(f"Module mapping: {len(module_map)} modules ready")
        return module_map

    def get_module_uuid(self, module_id: str) -> UUID | None:
        """
        Get the database UUID for a module string ID.

        Args:
            module_id: String ID like "NET-M7"

        Returns:
            UUID of the CleanModule record, or None if not found
        """
        with session_scope() as session:
            # Extract module number
            try:
                module_num = int(module_id.replace("NET-M", ""))
            except ValueError:
                logger.warning(f"Invalid module_id format: {module_id}")
                return None

            module = session.query(CleanModule).filter(CleanModule.week_order == module_num).first()

            if module:
                return module.id

            logger.warning(f"Module not found in DB: {module_id}")
            return None

    def get_all_module_mappings(self) -> dict[str, UUID]:
        """
        Get all module string ID → UUID mappings.

        Returns:
            Dict mapping "NET-M1" → UUID, etc.
        """
        with session_scope() as session:
            # Find the CCNA track
            track = session.query(CleanTrack).filter(CleanTrack.name.ilike("%CCNA%")).first()

            if not track:
                logger.warning("CCNA track not found")
                return {}

            # Get all modules in track
            modules = session.query(CleanModule).filter(CleanModule.track_id == track.id).all()

            mapping = {}
            for module in modules:
                module_id = f"NET-M{module.week_order}"
                mapping[module_id] = module.id

            return mapping

    def update_module_status(self, module_id: str, status: str) -> bool:
        """
        Update the status of a module.

        Args:
            module_id: String ID like "NET-M7"
            status: New status ('not_started', 'in_progress', 'completed')

        Returns:
            True if successful, False otherwise
        """
        with session_scope() as session:
            module_num = int(module_id.replace("NET-M", ""))

            module = session.query(CleanModule).filter(CleanModule.week_order == module_num).first()

            if not module:
                return False

            module.status = status
            session.commit()

            logger.info(f"Updated {module_id} status to '{status}'")
            return True

    def get_track_progress(self) -> dict:
        """
        Get progress summary for the CCNA track.

        Returns:
            Dict with module counts by status
        """
        with session_scope() as session:
            track = session.query(CleanTrack).filter(CleanTrack.name.ilike("%CCNA%")).first()

            if not track:
                return {"error": "Track not found"}

            modules = session.query(CleanModule).filter(CleanModule.track_id == track.id).all()

            status_counts = {
                "not_started": 0,
                "in_progress": 0,
                "completed": 0,
                "total": len(modules),
            }

            for module in modules:
                if module.status in status_counts:
                    status_counts[module.status] += 1

            return {
                "track_id": str(track.id),
                "track_name": track.name,
                **status_counts,
            }


def setup_ccna_curriculum() -> CurriculumMapping:
    """
    One-time setup for CCNA curriculum structure.

    Creates Program, Track, and Module records.

    Returns:
        CurriculumMapping with all database IDs
    """
    linker = CurriculumLinker()
    mapping = linker.ensure_curriculum_structure()

    logger.info(
        f"CCNA curriculum ready: track={mapping.track_id}, modules={len(mapping.module_id_map)}"
    )

    return mapping
