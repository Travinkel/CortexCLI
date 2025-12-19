"""
Feature Flags - Active Configuration.
"""
from dataclasses import dataclass
import os
from loguru import logger


@dataclass
class FeatureFlags:
    # Stable Features
    STUDY_BASIC: bool = True
    STUDY_MANUAL: bool = True
    STATS_BASIC: bool = True

    # Enabled for V1 Launch
    STUDY_ADAPTIVE: bool = True      # ENABLED
    STUDY_WAR_MODE: bool = True      # ENABLED
    NEURO_LINK: bool = True          # ENABLED (Visuals working)
    NCDE_DIAGNOSIS: bool = True      # ENABLED (Pedagogy engine working)
    PERSONA: bool = True             # ENABLED
    STRUGGLE_MAP: bool = True        # ENABLED
    
    # Optional / Infrastructure
    CALENDAR_INTEGRATION: bool = False
    TELEMETRY_JSON: bool = True
    ASCII_ART: bool = True
    DENSE_HUD: bool = True           # Enable the sidebar UI

    def __post_init__(self):
        for flag_name in self.__dataclass_fields__:
            env_key = f"CORTEX_{flag_name}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                setattr(self, flag_name, env_val.lower() in ("1", "true", "yes", "on"))

    def is_enabled(self, flag_name: str) -> bool:
        return getattr(self, flag_name, False)

# Singleton
_flags = FeatureFlags()
def get_flags() -> FeatureFlags: return _flags
