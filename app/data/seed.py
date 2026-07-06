"""
seed.py — Populate availability.db with time-slot data for every facility.

Usage:
    python -m app.data.seed          # from project root
    python app/data/seed.py          # direct execution

Generates 2-hour slots (08:00–20:00) for each facility across the next
14 days.  Randomly marks ~30 % of slots as already booked so the agent
has realistic availability patterns to work with.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent
FACILITIES_PATH = DATA_DIR / "facilities.json"
DB_PATH = DATA_DIR / "availability.db"

# ── configuration ────────────────────────────────────────────────────────
NUM_DAYS = 14                       # how many days ahead to seed
SLOT_DURATION_HOURS = 2             # each slot is 2 hours
DAY_START_HOUR = 8                  # first slot starts at 08:00
DAY_END_HOUR = 20                   # last slot ends at 20:00
BOOKED_PROBABILITY = 0.30           # chance a slot is pre-booked


def _create_schema(cur: sqlite3.Cursor) -> None:
    """Create the `slots` table (drops it first if it already exists)."""
    cur.execute("DROP TABLE IF EXISTS slots")
    cur.execute(
        """
        CREATE TABLE slots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id   TEXT    NOT NULL,
            date          TEXT    NOT NULL,   -- ISO format YYYY-MM-DD
            start_time    TEXT    NOT NULL,   -- HH:MM  (24-hr)
            end_time      TEXT    NOT NULL,   -- HH:MM  (24-hr)
            is_booked     INTEGER NOT NULL DEFAULT 0,  -- 0 = free, 1 = booked
            booked_by     TEXT,                        -- user id (NULL if free)
            UNIQUE(facility_id, date, start_time)
        )
        """
    )


def _load_facility_ids() -> list[str]:
    """Read facility IDs from facilities.json."""
    with open(FACILITIES_PATH, encoding="utf-8") as f:
        facilities = json.load(f)
    return [fac["id"] for fac in facilities]


def _generate_slots(facility_ids: list[str]) -> list[tuple]:
    """Return a list of row tuples ready for INSERT.

    Each tuple: (facility_id, date_str, start_time, end_time, is_booked, booked_by)
    """
    rows: list[tuple] = []
    today = date(2026, 7, 20)  # fixed anchor so data is reproducible

    demo_users = [
        "stu_ananya", "stu_rohit", "prof_sharma", "prof_iyer",
        "club_ieee", "club_literary", "admin_dean", "stu_fatima",
    ]

    for day_offset in range(NUM_DAYS):
        current_date = today + timedelta(days=day_offset)
        date_str = current_date.isoformat()

        for fac_id in facility_ids:
            hour = DAY_START_HOUR
            while hour < DAY_END_HOUR:
                start = f"{hour:02d}:00"
                end = f"{hour + SLOT_DURATION_HOURS:02d}:00"
                is_booked = 1 if random.random() < BOOKED_PROBABILITY else 0
                booked_by = random.choice(demo_users) if is_booked else None
                rows.append((fac_id, date_str, start, end, is_booked, booked_by))
                hour += SLOT_DURATION_HOURS

    return rows


def seed() -> None:
    """Main entry point — create the DB and fill it with slot data."""
    random.seed(42)  # deterministic for reproducibility

    facility_ids = _load_facility_ids()
    rows = _generate_slots(facility_ids)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    _create_schema(cur)
    cur.executemany(
        """
        INSERT INTO slots (facility_id, date, start_time, end_time, is_booked, booked_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
    booked = cur.execute("SELECT COUNT(*) FROM slots WHERE is_booked = 1").fetchone()[0]
    conn.close()

    print(f"[OK] Seeded {DB_PATH.name}")
    print(f"  {total} slots across {len(facility_ids)} facilities x {NUM_DAYS} days")
    print(f"  {booked} pre-booked ({booked / total * 100:.0f}%),  {total - booked} available")


if __name__ == "__main__":
    seed()
