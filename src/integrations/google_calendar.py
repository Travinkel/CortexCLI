"""
Google Calendar integration for Cortex study session scheduling.

Handles OAuth 2.0 authentication, Calendar API operations, and webhook notifications.

Features:
- OAuth 2.0 authentication with token persistence
- Book/cancel/update study sessions
- Check availability with conflict detection
- Webhook support for real-time schedule changes
- Smart scheduling based on chronotype and availability
- Active blocking of peak cognitive windows

Setup:
1. Create Google Cloud project at https://console.cloud.google.com/
2. Enable "Google Calendar API"
3. Create OAuth 2.0 credentials (Desktop app)
4. Download credentials.json to ~/.cortex/credentials.json
5. First run will open browser for authorization

Webhook Setup (Optional):
6. Enable Push Notifications in Google Cloud Console
7. Set up a publicly accessible endpoint for webhooks
8. Register the webhook channel with this module

Usage:
    calendar = CortexCalendar()
    if calendar.authenticate():
        event_id = calendar.book_study_session(
            start_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            modules=[11, 12, 13],
        )

Author: Cortex System
Version: 2.0.0 (Neuromorphic Architecture)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

# Lazy imports for google libraries (may not be installed)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None
    HttpError = Exception


# OAuth scopes required for Calendar access
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Default paths
CORTEX_DIR = Path.home() / ".cortex"
CREDENTIALS_PATH = CORTEX_DIR / "credentials.json"
TOKEN_PATH = CORTEX_DIR / "google_token.json"
WEBHOOK_STATE_PATH = CORTEX_DIR / "webhook_state.json"


def _get_timezone() -> str:
    """Get configured timezone from settings, with fallback."""
    try:
        from config import get_settings

        return get_settings().google_calendar_timezone
    except ImportError:
        return "America/New_York"


# =============================================================================
# ENUMERATIONS
# =============================================================================


class EventChangeType(str, Enum):
    """Types of calendar event changes."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    MOVED = "moved"


class StudyBlockType(str, Enum):
    """Types of study blocks."""

    DEEP_WORK = "deep_work"  # High cognitive load tasks
    REVIEW = "review"  # Spaced repetition review
    PLM_DRILL = "plm_drill"  # Perceptual learning drills
    REMEDIATION = "remediation"  # Focused remediation
    LIGHT_REVIEW = "light_review"  # Low energy period work


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class CalendarEvent:
    """Parsed calendar event."""

    event_id: str
    title: str
    start: datetime
    end: datetime
    description: str = ""
    is_cortex_event: bool = False
    modules: list[int] = field(default_factory=list)
    block_type: StudyBlockType = StudyBlockType.DEEP_WORK

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() / 60)


@dataclass
class ScheduleChange:
    """Represents a change to the schedule requiring adaptation."""

    change_type: EventChangeType
    event: CalendarEvent | None
    previous_event: CalendarEvent | None = None
    affected_window: tuple[datetime, datetime] | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TimeBlock:
    """An available time block for scheduling."""

    start: datetime
    end: datetime
    is_peak_hour: bool = False
    recommended_type: StudyBlockType = StudyBlockType.REVIEW

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() / 60)


@dataclass
class WebhookChannel:
    """Webhook channel registration."""

    channel_id: str
    resource_id: str
    expiration: datetime
    token: str


class CortexCalendar:
    """
    Google Calendar integration for Cortex study sessions.

    Attributes:
        service: Google Calendar API service object
        credentials: OAuth 2.0 credentials
    """

    def __init__(
        self,
        credentials_path: Path | None = None,
        token_path: Path | None = None,
    ):
        self.credentials_path = credentials_path or CREDENTIALS_PATH
        self.token_path = token_path or TOKEN_PATH
        self.service = None
        self.credentials = None
        self._authenticated = False

    @property
    def is_available(self) -> bool:
        """Check if Google libraries are installed."""
        return GOOGLE_AVAILABLE

    @property
    def has_credentials(self) -> bool:
        """Check if credentials.json exists."""
        return self.credentials_path.exists()

    def get_setup_instructions(self) -> str:
        """Return setup instructions for Google Calendar (ASCII-safe)."""
        return """
+====================================================================+
|  GOOGLE CALENDAR SETUP                                             |
+====================================================================+
|                                                                    |
|  1. Go to: https://console.cloud.google.com/                       |
|  2. Create new project: "Cortex Study"                             |
|  3. Enable "Google Calendar API"                                   |
|  4. Create OAuth 2.0 credentials (Desktop app)                     |
|  5. Download credentials.json                                      |
|  6. Place at: ~/.cortex/credentials.json                           |
|  7. Run: nls cortex schedule --time "tomorrow 9am"                 |
|     (Browser will open for authorization)                          |
|                                                                    |
+====================================================================+
"""

    def authenticate(self, force_reauth: bool = False) -> bool:
        """
        Authenticate with Google Calendar API.

        On first run, opens browser for OAuth consent.
        Stores token at ~/.cortex/google_token.json for future runs.

        Handles token refresh gracefully:
        - Attempts refresh if token expired
        - Falls back to re-authentication if refresh fails
        - Clears corrupted tokens automatically

        Args:
            force_reauth: Force re-authentication even if token exists

        Returns:
            True if authentication successful, False otherwise
        """
        if not GOOGLE_AVAILABLE:
            logger.warning(
                "Google libraries not installed. Run: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return False

        if not self.has_credentials:
            logger.warning(f"Credentials not found at {self.credentials_path}")
            return False

        # Ensure .cortex directory exists
        CORTEX_DIR.mkdir(parents=True, exist_ok=True)

        creds = None

        # Load existing token if available (unless forcing reauth)
        if self.token_path.exists() and not force_reauth:
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                logger.debug("Loaded existing token from cache")
            except Exception as e:
                logger.warning(f"Token file corrupted, will re-authenticate: {e}")
                # Remove corrupted token
                try:
                    self.token_path.unlink()
                except Exception:
                    pass
                creds = None

        # Attempt to refresh expired token
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.debug("Token expired, attempting refresh...")
                creds.refresh(Request())
                logger.info("Token refreshed successfully")
                # Save refreshed token
                self._save_token(creds)
            except Exception as e:
                logger.warning(
                    f"Token refresh failed (may be revoked or expired): {e}. "
                    f"Will attempt re-authentication."
                )
                # Clear invalid token
                try:
                    self.token_path.unlink()
                except Exception:
                    pass
                creds = None

        # Need new credentials - run OAuth flow
        if not creds or not creds.valid:
            try:
                logger.info("Starting OAuth authentication flow...")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

                # Save token for future runs
                self._save_token(creds)
                logger.info(f"Token saved to {self.token_path}")

            except Exception as e:
                logger.error(f"OAuth flow failed: {e}")
                return False

        # Build Calendar service
        try:
            self.service = build("calendar", "v3", credentials=creds)
            self.credentials = creds
            self._authenticated = True
            logger.info("Google Calendar authenticated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to build Calendar service: {e}")
            return False

    def _save_token(self, creds) -> None:
        """Save credentials token to file."""
        try:
            with open(self.token_path, "w") as token_file:
                token_file.write(creds.to_json())
        except Exception as e:
            logger.warning(f"Could not save token: {e}")

    def reauthenticate(self) -> bool:
        """
        Force re-authentication, clearing any cached tokens.

        Use this if the user wants to switch accounts or
        if tokens are consistently failing.
        """
        return self.authenticate(force_reauth=True)

    def check_availability(
        self,
        start_time: datetime,
        duration_minutes: int,
    ) -> bool:
        """
        Check if the time slot is available (no conflicts).

        Args:
            start_time: Proposed start time
            duration_minutes: Session duration

        Returns:
            True if slot is free, False if conflicts exist
        """
        if not self._authenticated or not self.service:
            return True  # Assume available if not connected

        end_time = start_time + timedelta(minutes=duration_minutes)

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_time.isoformat() + "Z",
                    timeMax=end_time.isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            return len(events) == 0

        except HttpError as e:
            logger.warning(f"Could not check availability: {e}")
            return True

    def book_study_session(
        self,
        start_time: datetime,
        duration_minutes: int,
        modules: list[int],
        title: str = "Cortex Study Session",
    ) -> str | None:
        """
        Book a study session on Google Calendar.

        Args:
            start_time: Session start time
            duration_minutes: Duration in minutes
            modules: List of module numbers to study
            title: Event title

        Returns:
            Event ID if successful, None otherwise
        """
        if not self._authenticated or not self.service:
            logger.error("Not authenticated. Call authenticate() first.")
            return None

        end_time = start_time + timedelta(minutes=duration_minutes)
        modules_str = ", ".join(str(m) for m in modules)

        event = {
            "summary": f"◉ {title}",
            "description": f"""CORTEX STUDY SESSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modules: {modules_str}
Duration: {duration_minutes} minutes
Mode: War Room (Aggressive Mastery)

Command to start:
  nls cortex start --mode war --modules {modules_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generated by The Cortex""",
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": _get_timezone(),
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": _get_timezone(),
            },
            "colorId": "9",  # Blue
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 10},
                    {"method": "popup", "minutes": 0},
                ],
            },
        }

        try:
            created_event = (
                self.service.events()
                .insert(
                    calendarId="primary",
                    body=event,
                )
                .execute()
            )

            event_id = created_event.get("id")
            logger.info(f"Created calendar event: {event_id}")
            return event_id

        except HttpError as e:
            logger.error(f"Failed to create event: {e}")
            return None

    def get_upcoming_sessions(self, days: int = 7) -> list[dict]:
        """
        Get upcoming Cortex study sessions.

        Args:
            days: Number of days to look ahead

        Returns:
            List of event dictionaries with id, title, start, end
        """
        if not self._authenticated or not self.service:
            return []

        now = datetime.utcnow()
        time_max = now + timedelta(days=days)

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat() + "Z",
                    timeMax=time_max.isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime",
                    q="Cortex",  # Filter by "Cortex" in title/description
                )
                .execute()
            )

            events = events_result.get("items", [])

            return [
                {
                    "id": e.get("id"),
                    "title": e.get("summary", "Untitled"),
                    "start": e.get("start", {}).get("dateTime"),
                    "end": e.get("end", {}).get("dateTime"),
                    "description": e.get("description", ""),
                }
                for e in events
            ]

        except HttpError as e:
            logger.warning(f"Could not fetch events: {e}")
            return []

    def cancel_session(self, event_id: str) -> bool:
        """
        Cancel a scheduled study session.

        Args:
            event_id: Google Calendar event ID

        Returns:
            True if cancelled successfully, False otherwise
        """
        if not self._authenticated or not self.service:
            return False

        try:
            self.service.events().delete(
                calendarId="primary",
                eventId=event_id,
            ).execute()
            logger.info(f"Cancelled event: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to cancel event: {e}")
            return False

    def update_session(
        self,
        event_id: str,
        start_time: datetime | None = None,
        duration_minutes: int | None = None,
        title: str | None = None,
        modules: list[int] | None = None,
    ) -> bool:
        """
        Update an existing study session.

        Args:
            event_id: Google Calendar event ID
            start_time: New start time (optional)
            duration_minutes: New duration (optional)
            title: New title (optional)
            modules: New module list (optional)

        Returns:
            True if updated successfully
        """
        if not self._authenticated or not self.service:
            return False

        try:
            # Get existing event
            event = (
                self.service.events()
                .get(
                    calendarId="primary",
                    eventId=event_id,
                )
                .execute()
            )

            # Update fields
            if start_time:
                end_time = start_time + timedelta(minutes=duration_minutes or 60)
                event["start"]["dateTime"] = start_time.isoformat()
                event["end"]["dateTime"] = end_time.isoformat()

            if title:
                event["summary"] = f"◉ {title}"

            if modules:
                modules_str = ", ".join(str(m) for m in modules)
                event["description"] = f"""CORTEX STUDY SESSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modules: {modules_str}
Duration: {duration_minutes or 60} minutes

Command to start:
  nls cortex start --modules {modules_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generated by The Cortex"""

            # Update
            self.service.events().update(
                calendarId="primary",
                eventId=event_id,
                body=event,
            ).execute()

            logger.info(f"Updated event: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to update event: {e}")
            return False

    # =========================================================================
    # SMART SCHEDULING
    # =========================================================================

    def find_available_slots(
        self,
        date: datetime,
        min_duration_minutes: int = 30,
        preferred_hours: list[int] | None = None,
        avoid_hours: list[int] | None = None,
    ) -> list[TimeBlock]:
        """
        Find available time slots on a given date.

        Args:
            date: The date to search
            min_duration_minutes: Minimum slot duration
            preferred_hours: Hours to prioritize (e.g., peak hours)
            avoid_hours: Hours to avoid (e.g., low energy)

        Returns:
            List of TimeBlock objects sorted by preference
        """
        if not self._authenticated or not self.service:
            return []

        # Set search window (6am to 11pm)
        start_of_day = date.replace(hour=6, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=0, second=0, microsecond=0)

        try:
            # Get all events for the day
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_of_day.isoformat() + "Z",
                    timeMax=end_of_day.isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])

            # Parse event times
            busy_periods = []
            for e in events:
                start_str = e.get("start", {}).get("dateTime")
                end_str = e.get("end", {}).get("dateTime")
                if start_str and end_str:
                    busy_periods.append(
                        (
                            datetime.fromisoformat(start_str.replace("Z", "+00:00")),
                            datetime.fromisoformat(end_str.replace("Z", "+00:00")),
                        )
                    )

            # Find gaps
            available_slots = []
            current_time = start_of_day

            for busy_start, busy_end in sorted(busy_periods):
                if current_time < busy_start:
                    gap_duration = (busy_start - current_time).total_seconds() / 60
                    if gap_duration >= min_duration_minutes:
                        available_slots.append(
                            TimeBlock(
                                start=current_time,
                                end=busy_start,
                                is_peak_hour=self._is_peak_hour(current_time.hour, preferred_hours),
                            )
                        )
                current_time = max(current_time, busy_end)

            # Final gap until end of day
            if current_time < end_of_day:
                gap_duration = (end_of_day - current_time).total_seconds() / 60
                if gap_duration >= min_duration_minutes:
                    available_slots.append(
                        TimeBlock(
                            start=current_time,
                            end=end_of_day,
                            is_peak_hour=self._is_peak_hour(current_time.hour, preferred_hours),
                        )
                    )

            # Filter out avoid hours and set block types
            filtered_slots = []
            for slot in available_slots:
                if avoid_hours and slot.start.hour in avoid_hours:
                    continue

                # Set recommended type based on hour
                if slot.is_peak_hour:
                    slot.recommended_type = StudyBlockType.DEEP_WORK
                elif slot.start.hour in (avoid_hours or []):
                    slot.recommended_type = StudyBlockType.LIGHT_REVIEW
                else:
                    slot.recommended_type = StudyBlockType.REVIEW

                filtered_slots.append(slot)

            # Sort by preference (peak hours first)
            filtered_slots.sort(key=lambda s: (not s.is_peak_hour, s.start))

            return filtered_slots

        except HttpError as e:
            logger.error(f"Failed to find available slots: {e}")
            return []

    def _is_peak_hour(self, hour: int, preferred_hours: list[int] | None) -> bool:
        """Check if hour is a peak performance hour."""
        if preferred_hours:
            return hour in preferred_hours
        # Default peak hours: 9-11am, 4-6pm
        return hour in [9, 10, 11, 16, 17, 18]

    def book_optimal_session(
        self,
        date: datetime,
        duration_minutes: int,
        modules: list[int],
        preferred_hours: list[int] | None = None,
        avoid_hours: list[int] | None = None,
        block_type: StudyBlockType = StudyBlockType.DEEP_WORK,
    ) -> str | None:
        """
        Book a study session at the optimal time.

        Finds the best available slot based on:
        - Peak performance hours
        - Existing calendar availability
        - Block type requirements

        Args:
            date: The date to book
            duration_minutes: Required duration
            modules: Modules to study
            preferred_hours: Preferred hours for studying
            avoid_hours: Hours to avoid
            block_type: Type of study block

        Returns:
            Event ID if booked successfully
        """
        slots = self.find_available_slots(
            date=date,
            min_duration_minutes=duration_minutes,
            preferred_hours=preferred_hours,
            avoid_hours=avoid_hours,
        )

        # Filter by block type preference
        if block_type == StudyBlockType.DEEP_WORK:
            slots = [s for s in slots if s.is_peak_hour] or slots

        if not slots:
            logger.warning(f"No available slots on {date.date()}")
            return None

        # Book the first (best) slot
        best_slot = slots[0]
        return self.book_study_session(
            start_time=best_slot.start,
            duration_minutes=duration_minutes,
            modules=modules,
            title=f"Cortex {block_type.value.replace('_', ' ').title()}",
        )

    def block_peak_hours(
        self,
        start_date: datetime,
        days: int = 7,
        peak_hours: list[int] = None,
        duration_minutes: int = 60,
    ) -> list[str]:
        """
        Proactively block peak cognitive hours for deep work.

        Based on circadian rhythm and persona data, books "Deep Work"
        slots to protect learning time.

        Args:
            start_date: First date to block
            days: Number of days to block
            peak_hours: Hours to block
            duration_minutes: Duration of each block

        Returns:
            List of created event IDs
        """
        if peak_hours is None:
            peak_hours = [9, 10, 11]
        event_ids = []
        current_date = start_date

        for _ in range(days):
            for hour in peak_hours:
                start_time = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)

                # Check if slot is available
                if self.check_availability(start_time, duration_minutes):
                    event_id = self.book_study_session(
                        start_time=start_time,
                        duration_minutes=duration_minutes,
                        modules=[],  # Will be filled by scheduler
                        title="Cortex Deep Work Block",
                    )
                    if event_id:
                        event_ids.append(event_id)

            current_date += timedelta(days=1)

        logger.info(f"Blocked {len(event_ids)} peak hour slots")
        return event_ids

    # =========================================================================
    # WEBHOOK SUPPORT
    # =========================================================================

    def register_webhook(
        self,
        callback_url: str,
        expiration_hours: int = 24,
    ) -> WebhookChannel | None:
        """
        Register a webhook for calendar change notifications.

        Note: Requires a publicly accessible HTTPS endpoint.

        Args:
            callback_url: URL to receive notifications
            expiration_hours: Hours until channel expires

        Returns:
            WebhookChannel if registered successfully
        """
        if not self._authenticated or not self.service:
            return None

        channel_id = str(uuid.uuid4())
        token = hashlib.sha256(f"{channel_id}:{datetime.now().isoformat()}".encode()).hexdigest()[
            :32
        ]

        expiration = datetime.now() + timedelta(hours=expiration_hours)

        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": callback_url,
            "token": token,
            "expiration": int(expiration.timestamp() * 1000),  # milliseconds
        }

        try:
            response = (
                self.service.events()
                .watch(
                    calendarId="primary",
                    body=body,
                )
                .execute()
            )

            channel = WebhookChannel(
                channel_id=response.get("id"),
                resource_id=response.get("resourceId"),
                expiration=expiration,
                token=token,
            )

            # Save channel state
            self._save_webhook_state(channel)

            logger.info(f"Registered webhook channel: {channel.channel_id}")
            return channel

        except HttpError as e:
            logger.error(f"Failed to register webhook: {e}")
            return None

    def stop_webhook(self, channel: WebhookChannel) -> bool:
        """
        Stop a webhook channel.

        Args:
            channel: The webhook channel to stop

        Returns:
            True if stopped successfully
        """
        if not self._authenticated or not self.service:
            return False

        try:
            self.service.channels().stop(
                body={
                    "id": channel.channel_id,
                    "resourceId": channel.resource_id,
                }
            ).execute()

            logger.info(f"Stopped webhook channel: {channel.channel_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to stop webhook: {e}")
            return False

    def _save_webhook_state(self, channel: WebhookChannel) -> None:
        """Save webhook channel state to file."""
        state = {
            "channel_id": channel.channel_id,
            "resource_id": channel.resource_id,
            "expiration": channel.expiration.isoformat(),
            "token": channel.token,
        }
        with open(WEBHOOK_STATE_PATH, "w") as f:
            json.dump(state, f)

    def _load_webhook_state(self) -> WebhookChannel | None:
        """Load webhook channel state from file."""
        if not WEBHOOK_STATE_PATH.exists():
            return None

        try:
            with open(WEBHOOK_STATE_PATH) as f:
                state = json.load(f)

            return WebhookChannel(
                channel_id=state["channel_id"],
                resource_id=state["resource_id"],
                expiration=datetime.fromisoformat(state["expiration"]),
                token=state["token"],
            )
        except Exception as e:
            logger.warning(f"Failed to load webhook state: {e}")
            return None

    def process_webhook_notification(
        self,
        headers: dict[str, str],
        on_change: Callable[[ScheduleChange], None] | None = None,
    ) -> ScheduleChange | None:
        """
        Process an incoming webhook notification.

        This should be called from your webhook endpoint handler.

        Args:
            headers: HTTP headers from the webhook request
            on_change: Callback function for schedule changes

        Returns:
            ScheduleChange if a relevant change was detected
        """
        # Verify the webhook token
        channel = self._load_webhook_state()
        if not channel:
            logger.warning("No webhook channel registered")
            return None

        received_token = headers.get("X-Goog-Channel-Token")
        if received_token != channel.token:
            logger.warning("Invalid webhook token")
            return None

        # Get the resource state
        resource_state = headers.get("X-Goog-Resource-State")
        resource_id = headers.get("X-Goog-Resource-ID")

        logger.debug(f"Webhook notification: state={resource_state}, id={resource_id}")

        # Determine change type
        if resource_state == "sync":
            # Initial sync - no action needed
            return None

        elif resource_state == "exists":
            # Event was created or updated
            change = ScheduleChange(
                change_type=EventChangeType.UPDATED,
                event=None,  # Would need to fetch the event
            )

            if on_change:
                on_change(change)

            return change

        return None

    # =========================================================================
    # REAL-TIME ADAPTATION
    # =========================================================================

    def adapt_to_schedule_change(
        self,
        change: ScheduleChange,
        current_session_start: datetime | None = None,
        current_session_duration: int = 60,
    ) -> dict[str, Any]:
        """
        Adapt study plans based on a schedule change.

        When a new meeting is added that conflicts with planned study time,
        this method suggests how to adapt.

        Args:
            change: The schedule change that occurred
            current_session_start: Start time of current/planned session
            current_session_duration: Duration of current session

        Returns:
            Dict with adaptation suggestions
        """
        result = {
            "action": "continue",
            "reason": "",
            "new_end_time": None,
            "alternative_slot": None,
            "suggested_task_type": None,
        }

        if not change.event:
            return result

        # If no current session, no adaptation needed
        if not current_session_start:
            return result

        current_session_end = current_session_start + timedelta(minutes=current_session_duration)

        # Check for conflict
        if change.event.start < current_session_end and change.event.end > current_session_start:
            # There's a conflict
            time_until_conflict = (change.event.start - current_session_start).total_seconds() / 60

            if time_until_conflict <= 5:
                # Immediate conflict - end session
                result["action"] = "end_session"
                result["reason"] = (
                    f"Calendar event '{change.event.title}' starts in {time_until_conflict:.0f} minutes"
                )

            elif time_until_conflict <= 20:
                # Short time left - switch to quick review
                result["action"] = "switch_mode"
                result["reason"] = (
                    f"Only {time_until_conflict:.0f} minutes until '{change.event.title}'"
                )
                result["suggested_task_type"] = "plm_drill"  # Quick perceptual learning
                result["new_end_time"] = change.event.start - timedelta(minutes=5)

            else:
                # Still have time - adjust end time
                result["action"] = "shorten_session"
                result["new_end_time"] = change.event.start - timedelta(minutes=5)
                result["reason"] = f"Session shortened to accommodate '{change.event.title}'"

            # Find alternative slot if we had to cut significantly
            if time_until_conflict < current_session_duration / 2:
                slots = self.find_available_slots(
                    date=datetime.now(),
                    min_duration_minutes=30,
                )
                if slots:
                    result["alternative_slot"] = slots[0]

        return result

    def get_next_event(self) -> CalendarEvent | None:
        """Get the next upcoming calendar event."""
        if not self._authenticated or not self.service:
            return None

        try:
            now = datetime.utcnow()
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat() + "Z",
                    maxResults=1,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            if not events:
                return None

            e = events[0]
            start_str = e.get("start", {}).get("dateTime")
            end_str = e.get("end", {}).get("dateTime")

            if not start_str or not end_str:
                return None

            return CalendarEvent(
                event_id=e.get("id", ""),
                title=e.get("summary", "Untitled"),
                start=datetime.fromisoformat(start_str.replace("Z", "+00:00")),
                end=datetime.fromisoformat(end_str.replace("Z", "+00:00")),
                description=e.get("description", ""),
                is_cortex_event="Cortex" in e.get("summary", ""),
            )

        except HttpError as e:
            logger.warning(f"Could not get next event: {e}")
            return None

    def time_until_next_event(self) -> timedelta | None:
        """Get time until the next calendar event."""
        next_event = self.get_next_event()
        if not next_event:
            return None

        return next_event.start - datetime.now(next_event.start.tzinfo)

    # =========================================================================
    # FATIGUE-BASED RESCHEDULING
    # =========================================================================

    def reschedule_session(
        self,
        event_id: str,
        delay_minutes: int = 30,
        reason: str = "fatigue_detected",
    ) -> bool:
        """
        Reschedule a study session by delaying it.

        Used when cognitive fatigue is detected to give the learner
        recovery time before resuming.

        Args:
            event_id: Google Calendar event ID to reschedule
            delay_minutes: Minutes to delay the session (default: 30)
            reason: Reason for rescheduling (for logging)

        Returns:
            True if rescheduled successfully, False otherwise
        """
        if not self._authenticated or not self.service:
            logger.error("Not authenticated. Call authenticate() first.")
            return False

        try:
            # Get existing event
            event = (
                self.service.events()
                .get(
                    calendarId="primary",
                    eventId=event_id,
                )
                .execute()
            )

            # Parse current times
            start_str = event.get("start", {}).get("dateTime")
            end_str = event.get("end", {}).get("dateTime")

            if not start_str or not end_str:
                logger.warning(f"Event {event_id} has no dateTime (all-day event?)")
                return False

            current_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            current_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            duration = current_end - current_start

            # Calculate new times
            new_start = current_start + timedelta(minutes=delay_minutes)
            new_end = new_start + duration

            # Update event times
            event["start"]["dateTime"] = new_start.isoformat()
            event["end"]["dateTime"] = new_end.isoformat()

            # Add reschedule note to description
            current_desc = event.get("description", "")
            reschedule_note = f"\n\n[Rescheduled +{delay_minutes}min: {reason}]"
            if reschedule_note not in current_desc:
                event["description"] = current_desc + reschedule_note

            # Update the event
            self.service.events().update(
                calendarId="primary",
                eventId=event_id,
                body=event,
            ).execute()

            logger.info(
                f"Rescheduled event {event_id}: "
                f"{current_start.strftime('%H:%M')} -> {new_start.strftime('%H:%M')} "
                f"(+{delay_minutes}min, reason={reason})"
            )
            return True

        except HttpError as e:
            logger.error(f"Failed to reschedule event: {e}")
            return False

    def reschedule_on_fatigue(
        self,
        fatigue_level: float,
        fatigue_threshold: float = 0.8,
        delay_minutes: int = 30,
    ) -> bool:
        """
        Automatically reschedule the next Cortex session if fatigue exceeds threshold.

        This is the "Time Lord" integration that responds to cognitive state.
        When the neuromorphic engine detects high fatigue, this method
        automatically adjusts the calendar to give recovery time.

        Args:
            fatigue_level: Current fatigue level (0.0 - 1.0)
            fatigue_threshold: Threshold to trigger rescheduling (default: 0.8)
            delay_minutes: Minutes to delay if fatigue detected (default: 30)

        Returns:
            True if a session was rescheduled, False otherwise
        """
        if fatigue_level < fatigue_threshold:
            logger.debug(
                f"Fatigue {fatigue_level:.2f} below threshold {fatigue_threshold}, "
                "no rescheduling needed"
            )
            return False

        # Find the next Cortex session
        upcoming = self.get_upcoming_sessions(days=1)
        cortex_sessions = [
            s
            for s in upcoming
            if "Cortex" in s.get("title", "") or "cortex" in s.get("description", "").lower()
        ]

        if not cortex_sessions:
            logger.debug("No upcoming Cortex sessions to reschedule")
            return False

        next_session = cortex_sessions[0]
        event_id = next_session.get("id")

        if not event_id:
            return False

        # Reschedule the session
        logger.warning(
            f"Fatigue level {fatigue_level:.2f} exceeds threshold {fatigue_threshold}. "
            f"Rescheduling next session by +{delay_minutes} minutes."
        )

        return self.reschedule_session(
            event_id=event_id,
            delay_minutes=delay_minutes,
            reason=f"fatigue_detected_{fatigue_level:.2f}",
        )
