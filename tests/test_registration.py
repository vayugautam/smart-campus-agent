"""
test_registration.py – Isolated unit tests for app.tools.registration.

All tests run against a temporary registrations.json created per-test via
pytest's ``tmp_path`` fixture so they never touch the real data store and
can run in any order independently.

Usage (from e:\\Campus\\campus-agent):
    pip install pytest          # if not already installed
    pytest tests/test_registration.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    """Redirect REGISTRATIONS_PATH inside the module to a temp file."""
    import app.tools.registration as reg_mod

    reg_file = tmp_path / "registrations.json"
    reg_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(reg_mod, "REGISTRATIONS_PATH", reg_file)
    return reg_file


# ---------------------------------------------------------------------------
# check_registration_open
# ---------------------------------------------------------------------------

class TestCheckRegistrationOpen:
    """Tests for check_registration_open()."""

    def test_unknown_event_returns_closed(self, monkeypatch, tmp_path):
        """A non-existent event_id must return open=False with a clear reason."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import check_registration_open

        result = check_registration_open("evt-DOES-NOT-EXIST")

        assert result["open"] is False
        assert "not found" in result["reason"].lower()
        assert result["event"] is None

    def test_event_without_registration_required_returns_closed(self, monkeypatch, tmp_path):
        """An event with registration_required=false should return open=False
        with an explanation that attendance is free."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import check_registration_open

        # evt-001 (Orientation Week Kickoff) has registration_required=false
        result = check_registration_open("evt-001")

        assert result["open"] is False
        assert result["event"] is not None
        assert "does not require" in result["reason"].lower() or "freely" in result["reason"].lower()

    def test_event_with_registration_required_open(self, monkeypatch, tmp_path):
        """An event with registration_required=true and free capacity returns open=True."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import check_registration_open

        # evt-002 (PyTorch Workshop) has registration_required=true, capacity=60
        result = check_registration_open("evt-002")

        assert result["open"] is True
        assert result["capacity"] == 60
        assert result["registered_count"] == 0
        assert result["spots_remaining"] == 60

    def test_fully_booked_event_returns_closed(self, monkeypatch, tmp_path):
        """When registered_count >= capacity the event should return open=False."""
        reg_file = _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import check_registration_open

        # evt-008 (Alumni Mixer) capacity=20 — pre-fill 20 registrations
        full_records = [
            {
                "registration_id": f"REG-{i:04d}",
                "event_id": "evt-008",
                "user_name": f"user_{i}",
                "registered_at": "2026-07-01T10:00:00+00:00",
            }
            for i in range(1, 21)  # exactly 20 records
        ]
        reg_file.write_text(json.dumps(full_records, indent=2), encoding="utf-8")

        result = check_registration_open("evt-008")

        assert result["open"] is False
        assert result["spots_remaining"] == 0
        assert "fully booked" in result["reason"].lower() or "full" in result["reason"].lower()
        assert result["registered_count"] == 20

    def test_spots_remaining_decrements_with_existing_registrations(self, monkeypatch, tmp_path):
        """spots_remaining should reflect actual count of existing records."""
        reg_file = _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import check_registration_open

        # evt-008 capacity=20, add 5 existing registrations
        existing = [
            {
                "registration_id": f"REG-{i:04d}",
                "event_id": "evt-008",
                "user_name": f"user_{i}",
                "registered_at": "2026-07-01T10:00:00+00:00",
            }
            for i in range(1, 6)
        ]
        reg_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        result = check_registration_open("evt-008")

        assert result["open"] is True
        assert result["registered_count"] == 5
        assert result["spots_remaining"] == 15


# ---------------------------------------------------------------------------
# create_registration
# ---------------------------------------------------------------------------

class TestCreateRegistration:
    """Tests for create_registration()."""

    def test_successful_registration_returns_success(self, monkeypatch, tmp_path):
        """A valid event + user should produce success=True with a REG-NNNN ID."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        result = create_registration("evt-002", "stu_ananya")

        assert result["success"] is True
        assert result["registration_id"] is not None
        assert result["registration_id"].startswith("REG-")
        assert result["event_id"] == "evt-002"
        assert result["user_name"] == "stu_ananya"
        assert result["registered_at"] is not None

    def test_successful_registration_persists_to_file(self, monkeypatch, tmp_path):
        """After create_registration, the record must appear in the JSON file."""
        reg_file = _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        create_registration("evt-002", "stu_rohit")

        persisted = json.loads(reg_file.read_text(encoding="utf-8"))
        assert len(persisted) == 1
        assert persisted[0]["event_id"] == "evt-002"
        assert persisted[0]["user_name"] == "stu_rohit"

    def test_registration_ids_are_sequential(self, monkeypatch, tmp_path):
        """Three consecutive registrations should get REG-0001, REG-0002, REG-0003."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        r1 = create_registration("evt-002", "user_a")
        r2 = create_registration("evt-005", "user_b")
        r3 = create_registration("evt-006", "user_c")

        assert r1["registration_id"] == "REG-0001"
        assert r2["registration_id"] == "REG-0002"
        assert r3["registration_id"] == "REG-0003"

    def test_duplicate_registration_returns_failure(self, monkeypatch, tmp_path):
        """Registering the same user for the same event twice must return
        success=False and report the existing registration ID."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        first = create_registration("evt-002", "stu_fatima")
        second = create_registration("evt-002", "stu_fatima")

        assert first["success"] is True
        assert second["success"] is False
        assert first["registration_id"] == second["registration_id"]
        assert "already registered" in second["message"].lower()

    def test_registration_fails_for_event_without_registration_required(
        self, monkeypatch, tmp_path
    ):
        """Attempting to register for an event that has registration_required=false
        must fail with a meaningful message (not silently succeed)."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        result = create_registration("evt-001", "stu_ananya")  # no registration needed

        assert result["success"] is False
        assert "cannot register" in result["message"].lower() or "does not require" in result["message"].lower()

    def test_registration_fails_for_nonexistent_event(self, monkeypatch, tmp_path):
        """A completely unknown event_id must return success=False."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        result = create_registration("evt-GHOST", "any_user")

        assert result["success"] is False
        assert result["registration_id"] is None

    def test_registration_fails_for_empty_user_name(self, monkeypatch, tmp_path):
        """An empty or whitespace-only user_name must be rejected before any I/O."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        result_empty = create_registration("evt-002", "")
        result_blank = create_registration("evt-002", "   ")

        assert result_empty["success"] is False
        assert result_blank["success"] is False

    def test_registration_fails_when_event_is_at_capacity(self, monkeypatch, tmp_path):
        """Trying to register for a fully-booked event must fail gracefully."""
        reg_file = _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        # evt-008 capacity=20 — fill all 20 spots
        full_records = [
            {
                "registration_id": f"REG-{i:04d}",
                "event_id": "evt-008",
                "user_name": f"user_{i}",
                "registered_at": "2026-07-01T10:00:00+00:00",
            }
            for i in range(1, 21)
        ]
        reg_file.write_text(json.dumps(full_records, indent=2), encoding="utf-8")

        result = create_registration("evt-008", "late_arrival")

        assert result["success"] is False
        assert "fully booked" in result["message"].lower() or "full" in result["message"].lower() or "cannot register" in result["message"].lower()

    def test_multiple_users_same_event(self, monkeypatch, tmp_path):
        """Different users can register for the same event independently."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import create_registration

        r1 = create_registration("evt-006", "user_alpha")
        r2 = create_registration("evt-006", "user_beta")
        r3 = create_registration("evt-006", "user_gamma")

        assert r1["success"] is True
        assert r2["success"] is True
        assert r3["success"] is True
        # All IDs must be distinct
        ids = {r1["registration_id"], r2["registration_id"], r3["registration_id"]}
        assert len(ids) == 3


# ---------------------------------------------------------------------------
# registration_tool (LangChain wrapper)
# ---------------------------------------------------------------------------

class TestRegistrationTool:
    """Tests for registration_tool() — the LangChain string wrapper."""

    def test_tool_returns_success_string_on_valid_registration(
        self, monkeypatch, tmp_path
    ):
        """A successful registration must return a string starting with 'SUCCESS:'."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import registration_tool

        output = registration_tool("evt-002", "stu_test")

        assert isinstance(output, str)
        assert output.startswith("SUCCESS:")
        assert "REG-" in output

    def test_tool_returns_failed_string_on_bad_event(self, monkeypatch, tmp_path):
        """An invalid event must produce a string starting with 'FAILED:'."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import registration_tool

        output = registration_tool("evt-INVALID", "stu_test")

        assert isinstance(output, str)
        assert output.startswith("FAILED:")

    def test_tool_output_contains_confirmation_id(self, monkeypatch, tmp_path):
        """The success string must embed the REG-NNNN confirmation ID."""
        _patch_paths(monkeypatch, tmp_path)
        from app.tools.registration import registration_tool

        output = registration_tool("evt-007", "stu_researcher")

        assert "REG-0001" in output
