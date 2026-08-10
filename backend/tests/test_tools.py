"""Unit tests for health domain lookup tools (Day 5 - The Tools)."""

from health_tools import check_scheme_eligibility, lookup_health_facility


def test_lookup_health_facility_known_district():
    """Test lookup for a known district (Patna) returns valid facility data and timestamp."""
    res = lookup_health_facility("Patna")
    assert res["status"] == "success"
    assert res["district"] == "Patna"
    assert "primary_health_centre" in res
    assert "Kankarbagh" in res["primary_health_centre"]["name"]
    assert "10 August 2026" in res["data_timestamp"]


def test_lookup_health_facility_fallback_district():
    """Test lookup for an arbitrary unlisted district returns structured CHC info and timestamp."""
    res = lookup_health_facility("Dharbhanga")
    assert res["status"] == "success"
    assert res["district"] == "Dharbhanga"
    assert "Dharbhanga" in res["primary_health_centre"]["name"]
    assert "10 August 2026" in res["data_timestamp"]


def test_lookup_health_facility_failure_simulation():
    """Test Day 5 Step 4 failure path: simulate_failure returns structured error fallback out loud."""
    res = lookup_health_facility("Patna", simulate_failure=True)
    assert res["status"] == "error"
    assert res["error_code"] == "NETWORK_TIMEOUT"
    assert "108" in res["spoken_fallback"]
    assert "104" in res["spoken_fallback"]
    assert "10 August 2026" in res["data_timestamp"]


def test_check_scheme_eligibility_ayushman():
    """Test scheme eligibility lookup for Ayushman Bharat PM-JAY."""
    res = check_scheme_eligibility("Ayushman Bharat")
    assert res["status"] == "success"
    assert "5,00,000" in res["coverage_amount"]
    assert "Aadhaar Card" in res["required_documents"]
    assert "10 August 2026" in res["data_timestamp"]


import pytest
import db
from agent import Assistant


@pytest.mark.asyncio
async def test_opt_out_stop_calling_unit():
    """Unit test for opt_out_stop_calling tool registering opt-out in DB."""
    db.init_db()
    assistant = Assistant()
    res = await assistant.opt_out_stop_calling(
        context=None, caller_name_or_id="Ramesh Kumar", reason="User asked to stop"
    )
    assert "Ramesh Kumar" in res
    assert "opted out" in res.lower()

    profile = db.get_user_profile("ramesh_kumar")
    assert profile is not None
    assert profile["facts"]["opted_out"] is True


@pytest.mark.asyncio
async def test_schedule_followup_reminder_unit():
    """Unit test for schedule_followup_reminder tool saving scheduled time in DB."""
    db.init_db()
    assistant = Assistant()
    res = await assistant.schedule_followup_reminder(
        context=None, preferred_time="Tomorrow 10 AM", caller_name_or_id="Sunita Devi"
    )
    assert "Sunita Devi" in res
    assert "Tomorrow 10 AM" in res

    profile = db.get_user_profile("sunita_devi")
    assert profile is not None
    assert profile["facts"]["next_reminder"] == "Tomorrow 10 AM"
