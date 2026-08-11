import asyncio
import os

import db
import escalation_tools
import pytest
from agent import Assistant
from livekit.agents import AgentSession, llm
from livekit.plugins import google

TEST_DB_PATH = "test_escalation_memory.db"


def _llm() -> llm.LLM:
    return google.LLM(model="gemini-3.5-flash-lite")


def setup_module(module):
    """Setup clean test database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db.init_db(TEST_DB_PATH)


def teardown_module(module):
    """Teardown test database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def test_sanitization():
    """Verify private info scrubbing (Day 7 Step 3)."""
    raw_summary = (
        "Caller Ramesh reported hospital issue. Aadhaar: 1234 5678 9012. "
        "Account: 4321-8765-9876-5432. OTP: 987654 password: mySecret123."
    )
    clean = escalation_tools.sanitize_private_info(raw_summary)

    assert "1234 5678 9012" not in clean
    assert "[REDACTED_AADHAAR]" in clean
    assert "4321-8765-9876-5432" not in clean
    assert "[REDACTED_ACCOUNT]" in clean
    assert "987654" not in clean
    assert "mySecret123" not in clean


def test_escalation_db_crud_and_deduplication():
    """Verify database escalation creation, deduplication (Advanced), status updates, and queries."""
    # 1. Create initial escalation
    record1 = db.save_escalation(
        escalation_id="ESC-10001",
        caller_name="Anil Kumar",
        reason_type="hospital_dispute",
        what_happened="Hospital rejected Ayushman Card for OPD admission",
        checked_by_agent="Checked PM-JAY eligibility, confirmed valid scheme",
        urgency="high",
        language="Hindi",
        preferred_followup="Phone Call",
        phone_or_contact="9876543210",
        db_path=TEST_DB_PATH,
    )

    assert record1["escalation_id"] == "ESC-10001"
    assert record1["is_duplicate_updated"] is False
    assert record1["status"] == "open"

    # 2. Duplicate escalation attempt for same caller & reason -> should update existing open ticket
    record2 = db.save_escalation(
        escalation_id="ESC-10002",
        caller_name="Anil Kumar",
        reason_type="hospital_dispute",
        what_happened="Hospital manager still refusing treatment",
        checked_by_agent="Re-checked eligibility",
        urgency="emergency",
        db_path=TEST_DB_PATH,
    )

    assert record2["escalation_id"] == "ESC-10001"  # Retains original ticket ID
    assert record2["is_duplicate_updated"] is True
    assert record2["urgency"] == "emergency"

    # 3. Retrieve ticket by ID
    fetched = db.get_escalation("ESC-10001", db_path=TEST_DB_PATH)
    assert fetched is not None
    assert fetched["caller_name"] == "Anil Kumar"

    # 4. Update status
    updated = db.update_escalation_status(
        "ESC-10001", "in_progress", db_path=TEST_DB_PATH
    )
    assert updated is True
    assert (
        db.get_escalation("ESC-10001", db_path=TEST_DB_PATH)["status"] == "in_progress"
    )

    # 5. List all escalations
    all_tickets = db.get_all_escalations(db_path=TEST_DB_PATH)
    assert len(all_tickets) >= 1


def test_permission_refusal_does_not_create_ticket():
    """Verify Day 7 Step 4: If user permission is False, no request is created."""
    result = escalation_tools.process_human_help_request(
        caller_name="Sunita Devi",
        reason_type="red_flag_symptoms",
        what_happened="Severe abdominal pain",
        checked_by_agent="Advised emergency line",
        user_permission_granted=False,  # Refused
        db_path=TEST_DB_PATH,
    )

    assert "PERMISSION_REFUSED" in result
    assert "NOT created" in result

    # Check DB to confirm nothing was saved for Sunita Devi
    escalations = db.get_all_escalations(db_path=TEST_DB_PATH)
    sunita_records = [
        e for e in escalations if e["caller_name"].lower() == "sunita devi"
    ]
    assert len(sunita_records) == 0


def test_permission_granted_creates_ticket():
    """Verify Day 7 Step 4 & 6: When permission is True, escalation is created with Ref ID."""
    result = escalation_tools.process_human_help_request(
        caller_name="Rajesh Sharma",
        reason_type="hospital_dispute",
        what_happened="Billing dispute at district hospital",
        checked_by_agent="Checked scheme rules",
        user_permission_granted=True,  # Granted
        urgency="medium",
        db_path=TEST_DB_PATH,
    )

    assert "SUCCESS_CREATED" in result
    assert "ESC-" in result

    # Check DB to confirm record exists
    escalations = db.get_all_escalations(db_path=TEST_DB_PATH)
    rajesh_records = [
        e for e in escalations if e["caller_name"].lower() == "rajesh sharma"
    ]
    assert len(rajesh_records) == 1
    assert rajesh_records[0]["urgency"] == "medium"


@pytest.mark.asyncio
async def test_llm_asks_permission_before_escalating():
    """Evaluation: LLM detects complex dispute and asks for caller permission before creating human help request."""
    await asyncio.sleep(12)
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Mera naam Mohan hai. Patna ke hospital me doctor mera Ayushman Card accept nahi kar rahe aur treatment mana kar rahe hain!"
        )

        # Agent may call lookup_caller first or directly output assistant message asking for permission
        event = result.expect.next_event()
        if event.is_function_call(name="lookup_caller"):
            result.expect.next_event().is_function_call_output()
            event = result.expect.next_event()

        await event.is_message(role="assistant").judge(
            llm_instance,
            intent="""
            Acknowledges the hospital issue/dispute, states that this requires supervisor or human team escalation,
            and explicitly asks Mohan for permission to share their name and details with the human help team.
            """,
        )


@pytest.mark.asyncio
async def test_llm_normal_conversation_does_not_escalate():
    """Evaluation: Normal query (PHC lookup) is answered normally without triggering human help request."""
    await asyncio.sleep(12)
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Mera naam Vikas hai. Patna district mein nearest PHC location aur OPD timing kya hai?"
        )

        result.expect.next_event().is_function_call(name="lookup_caller")
        result.expect.next_event().is_function_call_output()
        result.expect.next_event().is_function_call(name="lookup_nearest_phc")
        result.expect.next_event().is_function_call_output()

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Provides the PHC details for Patna clearly without asking for human escalation or calling create_human_help_request.
                """,
            )
        )
