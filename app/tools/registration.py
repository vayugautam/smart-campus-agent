"""
registration.py – Event Registration Tool.

Provides two core functions consumed by the LangGraph registration node
(wired in a future step) and a LangChain-compatible tool wrapper:

    check_registration_open(event_id)
        → Is registration required and is there still capacity?

    create_registration(event_id, user_name)
        → Write a new record to registrations.json and return a REG-NNNN ID.

Persistence mirrors the bookings pattern: a flat JSON list in
``app/data/registrations.json``, written atomically via a temp-file swap
so a crash mid-write can never corrupt the store.

No LLM, no FAISS, no LangGraph imports in this module.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVENTS_PATH = DATA_DIR / "events.json"
REGISTRATIONS_PATH = DATA_DIR / "registrations.json"


# ── Private helpers ───────────────────────────────────────────────────────────

def _load_events() -> list[dict[str, Any]]:
    """Load all events from the JSON data store."""
    with open(EVENTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_registrations() -> list[dict[str, Any]]:
    """Load all registrations, returning an empty list if the file is absent."""
    if not REGISTRATIONS_PATH.exists():
        return []
    with open(REGISTRATIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_registrations(records: list[dict[str, Any]]) -> None:
    """Atomically overwrite registrations.json using a temp-file swap.

    Writing to a temporary file in the same directory and then renaming it
    ensures the on-disk file is never in a half-written state even if the
    process is killed mid-write.
    """
    fd, tmp_path = tempfile.mkstemp(dir=REGISTRATIONS_PATH.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, REGISTRATIONS_PATH)  # atomic on POSIX; best-effort on Windows
    except Exception:
        # Clean up temp file if something went wrong before the rename
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _get_event(event_id: str) -> dict[str, Any] | None:
    """Return the event dict for *event_id*, or None if not found."""
    for ev in _load_events():
        if ev["id"] == event_id:
            return ev
    return None


def _next_registration_id(records: list[dict[str, Any]]) -> str:
    """Generate the next sequential registration ID (REG-0001, REG-0002, …).

    Derives the sequence number from the highest existing numeric suffix so
    the store stays monotonically increasing even after manual edits.
    """
    max_seq = 0
    for rec in records:
        rid = rec.get("registration_id", "")
        if rid.startswith("REG-") and rid[4:].isdigit():
            max_seq = max(max_seq, int(rid[4:]))
    return f"REG-{max_seq + 1:04d}"


# ── Public API ────────────────────────────────────────────────────────────────

def check_registration_open(event_id: str) -> dict[str, Any]:
    """Check whether registration is open for an event.

    Validation checks (in order):
    1. Event exists in events.json.
    2. Event has ``registration_required: true``; if false, registration is
       not needed and the event is freely attendable.
    3. Current registration count < event capacity.

    Args:
        event_id: The ``id`` field of the target event (e.g. ``"evt-002"``).

    Returns:
        A dict with the following keys:

        ``open`` (bool)
            True when registration is possible right now.

        ``reason`` (str)
            Human-readable explanation, populated when ``open`` is False
            or to provide context when True.

        ``event`` (dict | None)
            The full event record if found, else None.

        ``registered_count`` (int)
            How many registrations currently exist for this event.

        ``capacity`` (int | None)
            The event's maximum capacity, or None if unset.

        ``spots_remaining`` (int | None)
            ``capacity - registered_count``, or None if capacity is unset.
    """
    event = _get_event(event_id)
    if event is None:
        return {
            "open": False,
            "reason": f"Event '{event_id}' not found.",
            "event": None,
            "registered_count": 0,
            "capacity": None,
            "spots_remaining": None,
        }

    if not event.get("registration_required", False):
        return {
            "open": False,
            "reason": (
                f"'{event['name']}' does not require registration — "
                "anyone may attend freely."
            ),
            "event": event,
            "registered_count": 0,
            "capacity": event.get("capacity"),
            "spots_remaining": None,
        }

    records = _load_registrations()
    registered_count = sum(
        1 for r in records if r.get("event_id") == event_id
    )
    capacity: int | None = event.get("capacity")
    spots_remaining: int | None = (
        capacity - registered_count if capacity is not None else None
    )

    if capacity is not None and registered_count >= capacity:
        return {
            "open": False,
            "reason": (
                f"'{event['name']}' is fully booked "
                f"({registered_count}/{capacity} spots taken)."
            ),
            "event": event,
            "registered_count": registered_count,
            "capacity": capacity,
            "spots_remaining": 0,
        }

    return {
        "open": True,
        "reason": (
            f"Registration is open for '{event['name']}'. "
            + (
                f"{spots_remaining} of {capacity} spots remaining."
                if capacity is not None
                else "No capacity limit set."
            )
        ),
        "event": event,
        "registered_count": registered_count,
        "capacity": capacity,
        "spots_remaining": spots_remaining,
    }


def create_registration(event_id: str, user_name: str) -> dict[str, Any]:
    """Persist a new event registration and return the confirmation record.

    Should only be called after ``check_registration_open`` confirms the
    slot is available **and** the user has given explicit consent (mirrors
    the booking pattern where ``create_booking`` is called post-confirmation).

    Args:
        event_id:  Target event ID (e.g. ``"evt-002"``).
        user_name: Identifier of the registering user.

    Returns:
        A dict with the following keys:

        ``success`` (bool)
            Whether the registration was created.

        ``registration_id`` (str | None)
            Generated ID (e.g. ``"REG-0001"``), or None on failure.

        ``event_id`` (str)
            Echoed back for convenience.

        ``user_name`` (str)
            Echoed back for convenience.

        ``registered_at`` (str | None)
            ISO-8601 UTC timestamp of the registration, or None on failure.

        ``message`` (str)
            Human-readable confirmation or error description.
    """
    if not user_name or not user_name.strip():
        return {
            "success": False,
            "registration_id": None,
            "event_id": event_id,
            "user_name": user_name,
            "registered_at": None,
            "message": "user_name must not be empty.",
        }

    # Re-check open status inside the write path to guard against TOCTOU
    status = check_registration_open(event_id)
    if not status["open"]:
        return {
            "success": False,
            "registration_id": None,
            "event_id": event_id,
            "user_name": user_name,
            "registered_at": None,
            "message": f"Cannot register: {status['reason']}",
        }

    try:
        records = _load_registrations()

        # Check for duplicate registration for same user + event
        already = any(
            r.get("event_id") == event_id and r.get("user_name") == user_name
            for r in records
        )
        if already:
            existing = next(
                r for r in records
                if r.get("event_id") == event_id and r.get("user_name") == user_name
            )
            return {
                "success": False,
                "registration_id": existing["registration_id"],
                "event_id": event_id,
                "user_name": user_name,
                "registered_at": existing["registered_at"],
                "message": (
                    f"{user_name} is already registered for "
                    f"'{status['event']['name']}' "
                    f"(existing ID: {existing['registration_id']})."
                ),
            }

        reg_id = _next_registration_id(records)
        registered_at = datetime.now(timezone.utc).isoformat()

        new_record: dict[str, Any] = {
            "registration_id": reg_id,
            "event_id": event_id,
            "user_name": user_name,
            "registered_at": registered_at,
        }
        records.append(new_record)
        _save_registrations(records)

        return {
            "success": True,
            "registration_id": reg_id,
            "event_id": event_id,
            "user_name": user_name,
            "registered_at": registered_at,
            "message": (
                f"Successfully registered {user_name} for "
                f"'{status['event']['name']}'. "
                f"Confirmation ID: {reg_id}."
            ),
        }

    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "registration_id": None,
            "event_id": event_id,
            "user_name": user_name,
            "registered_at": None,
            "message": f"Unexpected error during registration: {exc}",
        }


# ── LangChain-compatible tool wrapper ────────────────────────────────────────

def registration_tool(event_id: str, user_name: str) -> str:
    """LangChain-compatible tool function for event registration.

    Wraps ``create_registration`` and returns a human-readable confirmation
    string for the LLM response-generation node.  Mirrors the signature of
    ``booking_tool`` in ``app/tools/booking.py``.

    Args:
        event_id:  Target event ID.
        user_name: Registering user's identifier.

    Returns:
        A formatted confirmation or error string.
    """
    res = create_registration(event_id, user_name)
    if res["success"]:
        return f"SUCCESS: {res['message']}"
    return f"FAILED: {res['message']}"
