import sqlite3
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "availability.db"

def create_booking(facility_id: str, date: str, start_time: str, end_time: str, user_name: str) -> dict:
    """Create and persist a new booking.

    This function should only be called AFTER the confirmation node has
    received explicit user approval.

    Args:
        facility_id: ID of the facility to book.
        date: Booking date (YYYY-MM-DD).
        start_time: Start time (HH:MM).
        end_time: End time (HH:MM).
        user_name: Identifier of the requesting user.

    Returns:
        The newly created booking dict (including generated ID and status).
    """
    if not DB_PATH.exists():
        return {"success": False, "error": "Database not found."}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # First check if the slot is free
        cur.execute(
            "SELECT id, is_booked FROM slots WHERE facility_id = ? AND date = ? AND start_time = ? AND end_time = ?",
            (facility_id, date, start_time, end_time)
        )
        row = cur.fetchone()

        if row is None:
            return {"success": False, "error": "Time slot not found in the schedule."}
        
        slot_id, is_booked = row
        if is_booked == 1:
            return {"success": False, "error": "Time slot is already booked."}

        # Update the slot to mark it as booked
        cur.execute(
            "UPDATE slots SET is_booked = 1, booked_by = ? WHERE id = ?",
            (user_name, slot_id)
        )
        conn.commit()

        booking_id = f"BKG-{slot_id:04d}"
        
        return {
            "success": True,
            "booking_id": booking_id,
            "facility_id": facility_id,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "user_name": user_name,
            "message": f"Successfully booked {facility_id} for {user_name} on {date}."
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def booking_tool(facility_id: str, date: str, start_time: str, end_time: str, user_name: str) -> str:
    """LangChain-compatible tool function for booking execution.

    Wraps `create_booking` and returns a human-readable confirmation
    string for the LLM response-generation node.

    Args:
        facility_id: Facility to book.
        date: Booking date (YYYY-MM-DD).
        start_time: Start time (HH:MM).
        end_time: End time (HH:MM).
        user_name: Requesting user.

    Returns:
        A formatted confirmation or error string.
    """
    res = create_booking(facility_id, date, start_time, end_time, user_name)
    if res["success"]:
        return f"SUCCESS: {res['message']} Confirmation ID: {res['booking_id']}."
    else:
        return f"FAILED: Could not create booking. Reason: {res['error']}"
