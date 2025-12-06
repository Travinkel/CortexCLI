"""
AnkiConnect client for notion-learning-sync.

Provides HTTP wrapper around AnkiConnect API for:
- Importing existing Anki decks with tags and FSRS stats
- Extracting prerequisite hierarchies from tag:prereq:* tags
- Pushing cleaned/split atoms back to Anki
- Bidirectional sync of FSRS scheduling data

Based on AnkiConnect API v6.

Hardening:
- Connection check with graceful degradation
- Configurable timeout with retry logic
- Detection of Anki modal dialogs (blocks API)
- Detailed error logging for sync failures
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger

from config import get_settings


# Default retry configuration for AnkiConnect
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5  # 0.5, 1.0, 2.0 seconds between retries
RETRY_STATUS_CODES = [500, 502, 503, 504]  # Retry on server errors


class AnkiClient:
    """
    Best-effort wrapper around the AnkiConnect API.

    AnkiConnect must be installed in Anki and running on port 8765.
    See: https://foosoft.net/projects/anki-connect/
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        deck_name: Optional[str] = None,
        note_type: Optional[str] = None,
        timeout: int = 60,
        retries: int = DEFAULT_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ) -> None:
        """
        Initialize AnkiConnect client with retry logic.

        Args:
            base_url: AnkiConnect URL (default from config)
            deck_name: Anki deck name (default from config)
            note_type: Anki note type (default from config)
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
            backoff_factor: Exponential backoff factor between retries
        """
        settings = get_settings()
        self.base_url = base_url or settings.anki_connect_url
        self.deck_name = deck_name or settings.anki_deck_name
        self.note_type = note_type or settings.anki_note_type
        self.timeout = timeout
        self._last_connection_check = 0.0
        self._connection_available = False

        # Configure session with retry logic
        self.session = requests.Session()

        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=["POST"],  # AnkiConnect only uses POST
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(
            "Initialized AnkiConnect client: url={}, deck={}, note_type={}, "
            "timeout={}s, retries={}",
            self.base_url,
            self.deck_name,
            self.note_type,
            self.timeout,
            retries,
        )

    # ========================================
    # Core API Methods
    # ========================================

    def _invoke(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Invoke an AnkiConnect API action.

        Args:
            action: AnkiConnect action name (e.g., "version", "findNotes")
            params: Action parameters

        Returns:
            Result from AnkiConnect API

        Raises:
            RuntimeError: If AnkiConnect returns an error
            requests.RequestException: If HTTP request fails
        """
        payload = {
            "action": action,
            "version": 6,
            "params": params or {},
        }

        # Truncate large params for logging to avoid verbose output
        log_params = params
        if params:
            log_params = {}
            for k, v in params.items():
                if isinstance(v, list) and len(v) > 10:
                    log_params[k] = f"[{len(v)} items]"
                else:
                    log_params[k] = v
        logger.debug("AnkiConnect request: action={}, params={}", action, log_params)

        response = self.session.post(
            self.base_url,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            raise RuntimeError(f"AnkiConnect error: {data['error']}")

        return data.get("result")

    def check_connection(self, cache_seconds: float = 30.0) -> bool:
        """
        Check if AnkiConnect is running and accessible.

        Uses cached result to avoid hammering Anki on repeated checks.
        Detects common failure modes:
        - Anki not running
        - AnkiConnect addon not installed
        - Modal dialog blocking API (e.g., "Check Database")

        Args:
            cache_seconds: Seconds to cache the connection status

        Returns:
            True if connection successful, False otherwise
        """
        # Use cached result if recent
        now = time.monotonic()
        if (now - self._last_connection_check) < cache_seconds:
            return self._connection_available

        try:
            # Quick timeout for connection check
            version = self._invoke("version")
            self._connection_available = True
            self._last_connection_check = now
            logger.info("AnkiConnect version detected: {}", version)
            return True

        except requests.exceptions.ConnectionError:
            self._connection_available = False
            self._last_connection_check = now
            logger.warning(
                "Anki not running or AnkiConnect not installed. "
                "Start Anki and ensure AnkiConnect addon is enabled."
            )
            return False

        except requests.exceptions.Timeout:
            self._connection_available = False
            self._last_connection_check = now
            logger.warning(
                "AnkiConnect request timed out. "
                "Anki may have a modal dialog open (e.g., 'Check Database', 'Sync'). "
                "Close any dialogs and try again."
            )
            return False

        except RuntimeError as e:
            self._connection_available = False
            self._last_connection_check = now
            logger.warning("AnkiConnect error: {}", e)
            return False

        except Exception as exc:  # pylint: disable=broad-except
            self._connection_available = False
            self._last_connection_check = now
            logger.warning("Anki connection failed: {}", exc)
            return False

    def is_available(self) -> bool:
        """
        Quick check if Anki connection was recently verified.

        Use this for fast conditional logic without making a network call.
        """
        return self._connection_available

    def require_connection(self) -> None:
        """
        Raise an exception if Anki is not available.

        Use at the start of operations that require Anki.
        """
        if not self.check_connection():
            raise RuntimeError(
                "Anki is not available. Ensure Anki is running with "
                "AnkiConnect addon enabled and no modal dialogs are open."
            )

    # ========================================
    # Card Import Methods
    # ========================================

    def fetch_all_cards(
        self,
        deck_name: Optional[str] = None,
        include_stats: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all cards from Anki deck with optional FSRS stats.

        This is the primary method for importing existing Anki decks.
        Returns raw card data with tags parsed for prerequisite extraction.

        Args:
            deck_name: Deck to fetch from (default from config)
            include_stats: Whether to include FSRS stats (stability, difficulty, etc.)

        Returns:
            List of card dictionaries with keys:
                - anki_note_id: Anki's internal note ID
                - anki_card_id: Anki's internal card ID
                - card_id: Custom Card ID field (e.g., "NET-M1-015")
                - front: Question text
                - back: Answer text
                - tags: List of tag strings
                - prerequisites: Parsed prerequisite tags
                - deck_name: Deck name
                - note_type: Note type name
                - fsrs_stats: FSRS scheduling data (if include_stats=True)
        """
        deck = deck_name or self.deck_name

        try:
            # Find all notes in deck
            query = f'deck:"{deck}"'
            logger.info("Querying Anki for notes with query: {}", query)

            note_ids = self._invoke("findNotes", {"query": query})

            if not note_ids:
                logger.warning(
                    "Anki returned 0 notes for deck '{}'. Check deck name.",
                    deck,
                )
                return []

            logger.info("Found {} notes in deck '{}'", len(note_ids), deck)

            # Fetch note details
            notes = self._invoke("notesInfo", {"notes": note_ids})

            # Fetch FSRS stats if requested
            stats_by_note_id: Dict[str, Dict[str, Any]] = {}
            if include_stats:
                stats = self.fetch_card_stats(deck_name=deck)
                for stat in stats:
                    note_id = stat.get("note_id")
                    if note_id:
                        stats_by_note_id[note_id] = stat

            # Map notes to card dictionaries
            cards: List[Dict[str, Any]] = []
            for note in notes or []:
                if not note:
                    continue

                card = self._map_note_to_card(note)

                # Attach FSRS stats if available
                note_id = str(note.get("noteId") or "")
                if note_id in stats_by_note_id:
                    card["fsrs_stats"] = stats_by_note_id[note_id]

                cards.append(card)

            logger.info("Mapped {} notes to card dictionaries", len(cards))
            return cards

        except requests.RequestException as exc:
            logger.error("Failed to fetch cards from Anki: {}", exc)
            return []

    def fetch_card_stats(
        self,
        deck_name: Optional[str] = None,
        reviewed_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch FSRS scheduling stats for all cards in deck.

        Extracts:
        - Stability (days): FSRS memory strength
        - Difficulty (0-1): FSRS difficulty rating
        - Retrievability (0-1): Current recall probability
        - Due date: Next review date
        - Interval: Current interval in days
        - Review count: Total reviews
        - Accuracy: Success rate

        Args:
            deck_name: Deck to fetch from (default from config)
            reviewed_only: Only return cards with review history

        Returns:
            List of stat dictionaries with FSRS fields
        """
        deck = deck_name or self.deck_name

        try:
            # Find all cards in deck
            query = f'deck:"{deck}"'
            logger.info("Querying Anki for cards with query: {}", query)

            card_ids = self._invoke("findCards", {"query": query})

            if not card_ids:
                logger.warning("Anki returned 0 cards for deck '{}'", deck)
                return []

            logger.info("Found {} cards in deck '{}'", len(card_ids), deck)

            # Fetch card info with FSRS data
            cards = self._invoke("cardsInfo", {"cards": card_ids})
            logger.info("Fetched cardsInfo for {} cards", len(cards or []))

            # Fetch review logs for accuracy calculation
            review_logs = self._fetch_review_logs(card_ids)

            # Build stats list
            stats: List[Dict[str, Any]] = []
            for card in cards or []:
                card_key = str(card.get("cardId") or card.get("id") or "")
                fields = card.get("fields", {})

                # Extract review log data
                review_entries = review_logs.get(card_key, [])
                has_reviews = bool(review_entries) or (card.get("reps") or 0) > 0

                if reviewed_only and not has_reviews:
                    continue

                # Calculate accuracy from review log
                correct_count = sum(
                    1 for entry in review_entries if (entry.get("ease") or 0) > 1
                )
                accuracy_percent = (
                    round((correct_count / len(review_entries)) * 100, 2)
                    if review_entries
                    else None
                )

                # Map queue code to human-readable label
                queue_code = card.get("queue")
                queue_label = self._map_queue(queue_code)

                # Format due date (depends on queue type)
                due_iso, due_mode = self._format_due(card.get("due"), queue_code)

                # Last review timestamp
                last_review_iso = (
                    self._last_review_from_logs(review_entries)
                    or self._format_timestamp(card.get("mod"))
                )

                stats.append({
                    "anki_card_id": card_key,
                    "note_id": str(card.get("noteId") or ""),
                    "card_id": self._field_value(fields.get("Card ID")) or str(card.get("noteId") or ""),
                    "deck_name": card.get("deckName") or deck,
                    "card_type": self._map_card_type(card.get("type")),
                    "queue": queue_label,
                    "due_date": due_iso,
                    "due_interpretation": due_mode,
                    "interval_days": card.get("interval") or card.get("ivl"),
                    "ease_factor": self._format_ease(card.get("factor")),
                    "review_count": card.get("reps"),
                    "lapses": card.get("lapses"),
                    "tags": " ".join(card.get("tags", [])),
                    "last_review": last_review_iso,
                    "correct_count": correct_count,
                    "accuracy_percent": accuracy_percent,
                })

            return stats

        except requests.RequestException as exc:
            logger.error("Failed to fetch card stats from Anki: {}", exc)
            return []

    # ========================================
    # Card Push Methods
    # ========================================

    def upsert_card(
        self,
        card_data: Dict[str, Any],
        dry_run: bool = False,
    ) -> Optional[str]:
        """
        Create or update a card in Anki.

        Args:
            card_data: Card dictionary with keys:
                - card_id: Custom Card ID (e.g., "NET-M1-015")
                - front: Question text
                - back: Answer text
                - tags: List of tag strings (optional)
                - anki_note_id: Anki note ID for updates (optional)
            dry_run: If True, log action but don't execute

        Returns:
            Anki note ID (as string) or None if failed
        """
        if dry_run:
            logger.info(
                "DRY RUN: Would upsert card: card_id={}, front={}...",
                card_data.get("card_id"),
                (card_data.get("front") or "")[:50],
            )
            return None

        # Build Anki fields
        fields = {
            "Card ID": card_data.get("card_id", ""),
            "Front": card_data.get("front", ""),
            "Back": card_data.get("back", ""),
        }

        # Build tags
        tags = card_data.get("tags", [])
        if isinstance(tags, str):
            tags = tags.split()

        try:
            # Check if updating existing note
            note_id = card_data.get("anki_note_id")

            if note_id and str(note_id).isdigit():
                # Update existing note
                self._invoke(
                    "updateNoteFields",
                    {"note": {"id": int(note_id), "fields": fields}},
                )
                logger.info("Updated Anki note: note_id={}", note_id)
                return str(note_id)
            else:
                # Create new note
                note_payload = {
                    "deckName": self.deck_name,
                    "modelName": self.note_type,
                    "fields": fields,
                    "tags": tags,
                }

                result = self._invoke("addNote", {"note": note_payload})
                logger.info(
                    "Created Anki note: note_id={}, card_id={}",
                    result,
                    card_data.get("card_id"),
                )
                return str(result)

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Failed to upsert card in Anki: card_id={}, error={}",
                card_data.get("card_id"),
                exc,
            )
            return None

    def suspend_card(self, note_id: int, dry_run: bool = False) -> bool:
        """
        Suspend a card in Anki (used for original cards after splitting).

        Args:
            note_id: Anki note ID to suspend
            dry_run: If True, log action but don't execute

        Returns:
            True if successful, False otherwise
        """
        if dry_run:
            logger.info("DRY RUN: Would suspend card: note_id={}", note_id)
            return True

        try:
            # Find cards for this note
            card_ids = self._invoke("findCards", {"query": f"nid:{note_id}"})

            if not card_ids:
                logger.warning("No cards found for note {}", note_id)
                return False

            # Suspend all cards
            self._invoke("suspend", {"cards": card_ids})
            logger.info("Suspended {} cards for note {}", len(card_ids), note_id)
            return True

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to suspend note {}: {}", note_id, exc)
            return False

    # ========================================
    # Helper Methods
    # ========================================

    def _map_note_to_card(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map Anki note to card dictionary.

        Extracts fields, parses tags, identifies prerequisites.
        """
        note_id = str(note.get("noteId") or "")
        fields = note.get("fields", {})
        tags = note.get("tags", [])

        # Extract field values
        card_id = self._field_value(fields.get("Card ID")) or note_id
        front = self._field_value(fields.get("Front")) or ""
        back = self._field_value(fields.get("Back")) or ""

        # Parse prerequisite tags
        prerequisites = self._parse_prerequisite_tags(tags)

        return {
            "anki_note_id": note_id,
            "anki_card_id": note_id,  # Will be updated with actual card ID if needed
            "card_id": card_id,
            "front": front,
            "back": back,
            "tags": tags,
            "prerequisites": prerequisites,
            "deck_name": self.deck_name,
            "note_type": note.get("modelName") or self.note_type,
        }

    def _parse_prerequisite_tags(self, tags: List[str]) -> Dict[str, Any]:
        """
        Parse tag:prereq:domain:topic:subtopic hierarchy from tags.

        Args:
            tags: List of tag strings

        Returns:
            Dictionary with keys:
                - has_prerequisites: Boolean
                - prerequisite_tags: List of full prerequisite tags
                - parsed_hierarchy: List of dicts with domain/topic/subtopic
        """
        prereq_tags = [tag for tag in tags if tag.startswith("tag:prereq:")]

        if not prereq_tags:
            return {
                "has_prerequisites": False,
                "prerequisite_tags": [],
                "parsed_hierarchy": [],
            }

        parsed = []
        for tag in prereq_tags:
            # Split tag:prereq:domain:topic:subtopic
            parts = tag.split(":")
            if len(parts) >= 3:
                parsed.append({
                    "full_tag": tag,
                    "domain": parts[2] if len(parts) > 2 else None,
                    "topic": parts[3] if len(parts) > 3 else None,
                    "subtopic": parts[4] if len(parts) > 4 else None,
                })

        return {
            "has_prerequisites": True,
            "prerequisite_tags": prereq_tags,
            "parsed_hierarchy": parsed,
        }

    def _fetch_review_logs(
        self,
        card_ids: List[int],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch review logs for cards (for accuracy calculation).

        Returns dict mapping card_id -> list of review entries.
        """
        try:
            records = self._invoke("getReviewsOfCards", {"cards": card_ids}) or []
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to fetch review logs: {}", exc)
            return {}

        if not isinstance(records, list):
            logger.warning("Unexpected review log payload type {}", type(records))
            return {}

        # Group by card ID
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue

            key = str(
                record.get("cid")
                or record.get("cardId")
                or record.get("id")
                or ""
            )

            if not key:
                continue

            buckets.setdefault(key, []).append(record)

        # Sort by timestamp
        for items in buckets.values():
            items.sort(key=lambda r: r.get("id", 0))

        return buckets

    def _last_review_from_logs(
        self,
        records: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Extract last review timestamp from review log."""
        if not records:
            return None

        latest = records[-1]
        stamp = latest.get("id") or latest.get("timestamp")

        if stamp is None:
            return None

        # Revlog IDs are milliseconds since epoch
        if stamp > 10_000_000_000:
            stamp = int(stamp) // 1000

        return self._format_timestamp(int(stamp))

    @staticmethod
    def _field_value(field: Optional[Dict[str, Any]]) -> str:
        """Extract string value from Anki field dictionary."""
        if not field:
            return ""

        if isinstance(field, dict):
            if "value" in field:
                return str(field["value"]).strip()
            if "text" in field:
                return str(field["text"]).strip()

        return str(field).strip()

    @staticmethod
    def _map_card_type(card_type: Optional[int]) -> str:
        """Map Anki card type code to human-readable label."""
        mapping = {
            0: "new",
            1: "learning",
            2: "review",
            3: "relearning",
        }
        return mapping.get(card_type, "unknown")

    @staticmethod
    def _map_queue(queue: Optional[int]) -> str:
        """Map Anki queue code to human-readable label."""
        mapping = {
            -3: "manually_suspended",
            -2: "scheduler_suspended",
            -1: "suspended",
            0: "new",
            1: "learning",
            2: "review",
            3: "day_learning",
            4: "preview",
        }
        return mapping.get(queue, "unknown")

    @staticmethod
    def _format_ease(raw: Optional[int]) -> Optional[float]:
        """Format Anki ease factor (stored as integer * 1000)."""
        if raw is None:
            return None
        return round(raw / 1000, 3)

    @staticmethod
    def _format_timestamp(raw: Optional[int]) -> Optional[str]:
        """Format Unix timestamp to ISO 8601 string."""
        if raw is None:
            return None

        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            return None

    def _format_due(
        self,
        due: Optional[int],
        queue: Optional[int],
    ) -> tuple[Optional[str], str]:
        """
        Format Anki due date (interpretation depends on queue type).

        Returns:
            Tuple of (iso_date, interpretation_mode)
        """
        if due is None:
            return None, "unknown"

        try:
            # Review/day learning: day count since epoch
            if queue in {2, 3}:
                iso_date = datetime.fromtimestamp(
                    int(due) * 86400,
                    tz=timezone.utc,
                ).date().isoformat()
                return iso_date, "epoch_days"

            # Learning queue: unix seconds
            if queue == 1:
                iso_date = datetime.fromtimestamp(
                    int(due),
                    tz=timezone.utc,
                ).isoformat()
                return iso_date, "unix_seconds"

            # Suspended/new/preview: position or irrelevant
            if queue in {-3, -2, -1, 0, 4}:
                return None, "position_or_preview"

        except (OverflowError, OSError, ValueError, TypeError):
            return None, "unparsed"

        return None, "unknown"
