"""
mock_db.py – Data access layer for the campus agent.

Provides helpers to load, query, and mutate the mock JSON data stores
(events.json, facilities.json, bookings.json).  A future iteration may
swap this for SQLite or a real database; callers should only depend on
the public functions defined here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── paths ────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent

EVENTS_PATH = DATA_DIR / "events.json"
FACILITIES_PATH = DATA_DIR / "facilities.json"
BOOKINGS_PATH = DATA_DIR / "bookings.json"


# ── loaders ──────────────────────────────────────────────────────────────

def load_events() -> list[dict[str, Any]]:
    """Load all events from the JSON data store.

    Returns:
        A list of event dicts, each containing at minimum:
        id, title, description, date, time, location, category.
    """
    pass


def load_facilities() -> list[dict[str, Any]]:
    """Load all facilities from the JSON data store.

    Returns:
        A list of facility dicts, each containing at minimum:
        id, name, type, building, capacity, amenities, available.
    """
    pass


def load_bookings() -> list[dict[str, Any]]:
    """Load all bookings from the JSON data store.

    Returns:
        A list of booking dicts, each containing at minimum:
        id, facility_id, user, date, start_time, end_time, status.
    """
    pass


# ── queries ──────────────────────────────────────────────────────────────

def get_event_by_id(event_id: str) -> dict[str, Any] | None:
    """Return a single event dict by its ID, or None if not found."""
    pass


def get_facility_by_id(facility_id: str) -> dict[str, Any] | None:
    """Return a single facility dict by its ID, or None if not found."""
    pass


def get_bookings_for_facility(facility_id: str, date: str) -> list[dict[str, Any]]:
    """Return all bookings for a given facility on a specific date.

    Args:
        facility_id: The facility to query.
        date: ISO-format date string (YYYY-MM-DD).

    Returns:
        List of matching booking dicts.
    """
    pass


# ── mutations ────────────────────────────────────────────────────────────

def create_booking(booking: dict[str, Any]) -> dict[str, Any]:
    """Persist a new booking to the JSON data store.

    Args:
        booking: A dict with facility_id, user, date, start_time, end_time.

    Returns:
        The created booking dict with a generated id and status='confirmed'.
    """
    pass
