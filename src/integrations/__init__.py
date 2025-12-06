"""
External integrations for the Cortex study system.

Modules:
- google_calendar: OAuth-based Google Calendar scheduling
"""
from .google_calendar import CortexCalendar

__all__ = ["CortexCalendar"]
