import os
import sys
import tempfile

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import db


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db.init_db(db_path)
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


def test_call_analytics_flow(temp_db):
    # 1. Log call start
    call_1 = "test-call-001"
    start_res = db.log_call_start(call_1, participant_identity="User 1", channel="browser", db_path=temp_db)
    assert start_res["call_id"] == call_1

    # Record action (successful call)
    db.record_call_action(call_1, "PHC Lookup", "District: Patna", db_path=temp_db)
    final_1 = db.finalize_call(call_1, db_path=temp_db)
    assert final_1["status"] == "successful"
    assert final_1["failure_category"] == "none"

    # 2. Log failed call (user hung up early)
    call_2 = "test-call-002"
    db.log_call_start(call_2, participant_identity="User 2", channel="sip", db_path=temp_db)
    db.mark_call_failure_category(call_2, "user_hungup_early", db_path=temp_db)
    final_2 = db.finalize_call(call_2, db_path=temp_db)
    assert final_2["status"] == "failed"
    assert final_2["failure_category"] == "user_hungup_early"

    # 3. Test record_test_call helper
    analytics_after = db.record_test_call(
        status="successful",
        primary_action="Scheme Eligibility Check",
        channel="browser",
        db_path=temp_db,
    )
    assert analytics_after["total_calls"] == 3
    assert analytics_after["successful_calls"] == 2
    assert analytics_after["failed_calls"] == 1
    assert analytics_after["success_rate"] == 66.7
    assert len(analytics_after["recent_calls"]) == 3
