"""
availability_checker.py – Availability / Constraint Checker Tool.

Checks whether a requested facility is available for a given date and
time window by querying the mock institutional database (bookings.json).
Also enforces business rules (e.g., operating hours, max duration).
"""

from __future__ import annotations


import sqlite3
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "availability.db"

def check_availability(facility_id: str, date: str, start_time: str, end_time: str) -> dict:
    """Check if a facility is available for the requested time slot.

    Args:
        facility_id: ID of the facility to check.
        date: Requested date in ISO format (YYYY-MM-DD).
        start_time: Requested start time (HH:MM, 24-hr).
        end_time: Requested end time (HH:MM, 24-hr).

    Returns:
        A dict with keys:
        - available (bool): Whether the slot is free.
        - conflicts (list[dict]): Any overlapping bookings.
        - reason (str | None): Human-readable explanation if unavailable.
        - alternatives (list[dict]): Nearest free slots if unavailable.
    """
    if not DB_PATH.exists():
        return {"available": False, "conflicts": [], "reason": "Database not found.", "alternatives": []}

    try:
        req_start = datetime.strptime(start_time, "%H:%M")
    except ValueError:
        return {"available": False, "conflicts": [], "reason": "Invalid start_time format. Use HH:MM.", "alternatives": []}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check exact slot
    cur.execute(
        "SELECT is_booked FROM slots WHERE facility_id = ? AND date = ? AND start_time = ? AND end_time = ?",
        (facility_id, date, start_time, end_time)
    )
    row = cur.fetchone()

    if row is None:
        # Check if the facility exists on this date
        cur.execute("SELECT COUNT(*) FROM slots WHERE facility_id = ? AND date = ?", (facility_id, date))
        if cur.fetchone()[0] == 0:
            conn.close()
            return {"available": False, "conflicts": [], "reason": "Facility or date not found in the schedule.", "alternatives": []}
        
        # Slot doesn't exist but facility is open
        conn.close()
        return {"available": False, "conflicts": [], "reason": "Invalid time slot requested. Slots are in 2-hour blocks starting at 08:00.", "alternatives": []}
    
    if row["is_booked"] == 0:
        conn.close()
        return {"available": True, "conflicts": [], "reason": None, "alternatives": []}

    # If booked, find alternatives
    cur.execute(
        "SELECT start_time, end_time FROM slots WHERE facility_id = ? AND date = ? AND is_booked = 0",
        (facility_id, date)
    )
    free_slots = cur.fetchall()
    conn.close()

    # Sort alternatives by distance to requested start_time
    def time_distance(slot_row):
        try:
            slot_start = datetime.strptime(slot_row["start_time"], "%H:%M")
            return abs((slot_start - req_start).total_seconds())
        except ValueError:
            return float('inf')

    free_slots_sorted = sorted(free_slots, key=time_distance)
    nearest_two = [
        {"start_time": s["start_time"], "end_time": s["end_time"]}
        for s in free_slots_sorted[:2]
    ]

    return {
        "available": False,
        "conflicts": [{"start_time": start_time, "end_time": end_time, "reason": "Pre-booked"}],
        "reason": "The requested time slot is already booked.",
        "alternatives": nearest_two
    }


def availability_tool(facility_id: str, date: str, start_time: str, end_time: str) -> str:
    """LangChain-compatible tool function for availability checking.

    Wraps `check_availability` and returns a human-readable summary
    string for the LLM response-generation node.

    Args:
        facility_id: Facility to query.
        date: Requested date (YYYY-MM-DD).
        start_time: Start time (HH:MM).
        end_time: End time (HH:MM).

    Returns:
        A formatted string indicating availability or conflicts.
    """
    res = check_availability(facility_id, date, start_time, end_time)
    
    if res["available"]:
        return f"SUCCESS: The slot for {facility_id} on {date} from {start_time} to {end_time} is available."
    
    msg = f"UNAVAILABLE: {res['reason']}"
    if res.get("alternatives"):
        alts = [f"{a['start_time']} to {a['end_time']}" for a in res["alternatives"]]
        msg += f" Suggested alternative slots on {date}: " + " and ".join(alts) + "."
    
    return msg
