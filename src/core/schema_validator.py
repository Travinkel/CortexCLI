"""
Schema Validator - Fail fast if required database objects don't exist.

Philosophy:
- App should NOT start if schema is broken
- No silent fallbacks - explicit failures only
- Each feature declares its schema requirements
"""

from dataclasses import dataclass
from typing import Optional

from loguru import logger
from sqlalchemy import text

from src.db.database import engine


@dataclass
class SchemaRequirement:
    """A single schema requirement (table, view, or function)."""
    name: str
    object_type: str  # 'table', 'view', 'function'
    feature_flag: str  # Which feature requires this
    required: bool = True  # If False, just warn instead of fail


# ============================================================================
# SCHEMA REQUIREMENTS BY FEATURE
# ============================================================================

CORE_REQUIREMENTS = [
    # Absolutely required for any operation
    SchemaRequirement("learning_atoms", "table", "STUDY_BASIC", required=True),
    SchemaRequirement("ccna_sections", "table", "STUDY_BASIC", required=True),
    SchemaRequirement("concepts", "table", "STUDY_BASIC", required=True),
]

MANUAL_MODE_REQUIREMENTS = [
    # Manual mode only needs core tables
]

ADAPTIVE_REQUIREMENTS = [
    SchemaRequirement("atom_responses", "table", "STUDY_ADAPTIVE"),
    SchemaRequirement("session_atom_responses", "table", "STUDY_ADAPTIVE"),
]

NCDE_REQUIREMENTS = [
    SchemaRequirement("cognitive_diagnoses", "table", "NCDE_DIAGNOSIS"),
    SchemaRequirement("record_diagnosis", "function", "NCDE_DIAGNOSIS"),
]

PERSONA_REQUIREMENTS = [
    SchemaRequirement("learner_profiles", "table", "PERSONA"),
]

STRUGGLE_REQUIREMENTS = [
    SchemaRequirement("struggle_weights", "table", "STRUGGLE_MAP"),
    SchemaRequirement("v_struggle_priority", "view", "STRUGGLE_MAP"),
]


class SchemaValidationError(Exception):
    """Raised when required schema objects are missing."""
    pass


class SchemaValidator:
    """Validates database schema against feature requirements."""

    def __init__(self):
        self._cache: dict[str, bool] = {}

    def _check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        if table_name in self._cache:
            return self._cache[table_name]

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = :name
                        )
                    """),
                    {"name": table_name}
                )
                exists = result.scalar()
                self._cache[table_name] = exists
                return exists
        except Exception as e:
            logger.error(f"Failed to check table {table_name}: {e}")
            return False

    def _check_view_exists(self, view_name: str) -> bool:
        """Check if a view exists in the database."""
        cache_key = f"view:{view_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.views
                            WHERE table_schema = 'public'
                            AND table_name = :name
                        )
                    """),
                    {"name": view_name}
                )
                exists = result.scalar()
                self._cache[cache_key] = exists
                return exists
        except Exception as e:
            logger.error(f"Failed to check view {view_name}: {e}")
            return False

    def _check_function_exists(self, func_name: str) -> bool:
        """Check if a function exists in the database."""
        cache_key = f"func:{func_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT EXISTS (
                            SELECT FROM pg_proc p
                            JOIN pg_namespace n ON p.pronamespace = n.oid
                            WHERE n.nspname = 'public'
                            AND p.proname = :name
                        )
                    """),
                    {"name": func_name}
                )
                exists = result.scalar()
                self._cache[cache_key] = exists
                return exists
        except Exception as e:
            logger.error(f"Failed to check function {func_name}: {e}")
            return False

    def check_requirement(self, req: SchemaRequirement) -> bool:
        """Check if a single requirement is satisfied."""
        if req.object_type == "table":
            return self._check_table_exists(req.name)
        elif req.object_type == "view":
            return self._check_view_exists(req.name)
        elif req.object_type == "function":
            return self._check_function_exists(req.name)
        else:
            logger.warning(f"Unknown object type: {req.object_type}")
            return False

    def validate_requirements(
        self,
        requirements: list[SchemaRequirement],
        fail_on_missing: bool = True
    ) -> tuple[list[SchemaRequirement], list[SchemaRequirement]]:
        """
        Validate a list of requirements.

        Returns: (satisfied, missing) tuples
        """
        satisfied = []
        missing = []

        for req in requirements:
            if self.check_requirement(req):
                satisfied.append(req)
            else:
                missing.append(req)
                if req.required:
                    logger.error(
                        f"SCHEMA MISSING: {req.object_type} '{req.name}' "
                        f"required by {req.feature_flag}"
                    )
                else:
                    logger.warning(
                        f"SCHEMA MISSING: {req.object_type} '{req.name}' "
                        f"(optional for {req.feature_flag})"
                    )

        if fail_on_missing and any(r.required for r in missing):
            required_missing = [r for r in missing if r.required]
            raise SchemaValidationError(
                f"Missing required schema objects: "
                f"{[r.name for r in required_missing]}. "
                f"Run migrations or disable the features that require them."
            )

        return satisfied, missing

    def validate_core(self) -> bool:
        """Validate core schema required for any operation."""
        satisfied, missing = self.validate_requirements(
            CORE_REQUIREMENTS,
            fail_on_missing=True
        )
        return len(missing) == 0

    def validate_for_feature(self, feature_flag: str) -> bool:
        """Validate schema for a specific feature."""
        requirements_map = {
            "STUDY_BASIC": CORE_REQUIREMENTS,
            "STUDY_MANUAL": CORE_REQUIREMENTS + MANUAL_MODE_REQUIREMENTS,
            "STUDY_ADAPTIVE": CORE_REQUIREMENTS + ADAPTIVE_REQUIREMENTS,
            "NCDE_DIAGNOSIS": NCDE_REQUIREMENTS,
            "PERSONA": PERSONA_REQUIREMENTS,
            "STRUGGLE_MAP": STRUGGLE_REQUIREMENTS,
        }

        reqs = requirements_map.get(feature_flag, [])
        if not reqs:
            return True

        satisfied, missing = self.validate_requirements(reqs, fail_on_missing=False)
        return len([m for m in missing if m.required]) == 0

    def get_available_features(self) -> dict[str, bool]:
        """Get which features have their schema requirements met."""
        features = [
            "STUDY_BASIC",
            "STUDY_MANUAL",
            "STUDY_ADAPTIVE",
            "NCDE_DIAGNOSIS",
            "PERSONA",
            "STRUGGLE_MAP",
        ]

        return {f: self.validate_for_feature(f) for f in features}


# Singleton
_validator: Optional[SchemaValidator] = None


def get_validator() -> SchemaValidator:
    """Get the global schema validator instance."""
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator


def validate_core_schema() -> None:
    """Validate core schema on app startup. Raises if missing."""
    get_validator().validate_core()


def check_feature_schema(feature_flag: str) -> bool:
    """Check if schema for a feature is available."""
    return get_validator().validate_for_feature(feature_flag)
