import asyncio

import pytest
from livekit.agents import AgentSession, llm
from livekit.plugins import google

import db
from agent import Assistant

TEST_DB_PATH = "agent_memory.db"


def _llm() -> llm.LLM:
    return google.LLM(model="gemini-3.5-flash-lite")


def test_db_crud():
    """Direct database unit test for CRUD operations."""
    # Clean up test user if exists
    db.delete_user_profile("unit_test_user_999", db_path=TEST_DB_PATH)

    # 1. Save profile
    profile = db.save_user_profile(
        user_id="unit_test_user_999",
        name="UnitTestUser",
        language_preference="Hinglish",
        facts={"age_band": "45-50", "ongoing_conditions": "Diabetes"},
        db_path=TEST_DB_PATH,
    )
    assert profile["user_id"] == "unit_test_user_999"
    assert profile["name"] == "UnitTestUser"
    assert profile["facts"]["ongoing_conditions"] == "Diabetes"

    # 2. Get profile
    fetched = db.get_user_profile("unit_test_user_999", db_path=TEST_DB_PATH)
    assert fetched is not None
    assert fetched["user_id"] == "unit_test_user_999"

    # 3. Delete profile
    deleted = db.delete_user_profile("unit_test_user_999", db_path=TEST_DB_PATH)
    assert deleted is True
    assert db.get_user_profile("unit_test_user_999", db_path=TEST_DB_PATH) is None


@pytest.mark.asyncio
async def test_llm_greets_returning_caller():
    """Evaluation: Returning caller greeted by name with previous context."""
    await asyncio.sleep(12)
    # Pre-populate DB for Ramesh
    db.save_user_profile(
        user_id="ramesh",
        name="Ramesh",
        language_preference="Hinglish",
        facts={
            "ongoing_conditions": "Diabetes",
            "last_triage_outcome": "Ayushman Bharat card apply for OPD",
        },
        db_path=TEST_DB_PATH,
    )

    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(user_input="Namaste, main Ramesh bol raha hu.")

        result.expect.next_event().is_function_call(name="lookup_caller")
        result.expect.next_event().is_function_call_output()
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Welcomes Ramesh back by name in Hindi (Devanagari script) or Hinglish, acknowledges his greeting, and asks how it can help today.
                """,
            )
        )
        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_llm_asks_consent_before_saving():
    """Evaluation: LLM asks consent before saving details."""
    await asyncio.sleep(12)
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Mera naam Suresh hai, meri umar 45 saal hai aur mujhe hypertension hai."
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Asks Suresh for explicit permission or consent before saving or remembering their personal details for future calls.
                """,
            )
        )
        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_llm_respects_consent_refusal():
    """Evaluation: If user says NO to saving, LLM does NOT save information."""
    await asyncio.sleep(12)
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Nahi, mera data save mat karo. Privately guide karo."
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Confirms that user details will not be saved or stored, and asks how it can help.
                """,
            )
        )
        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_llm_forget_me_tool():
    """Evaluation: Wiping user data when requested ("forget me")."""
    await asyncio.sleep(12)
    # Pre-populate record for Priya
    db.save_user_profile(
        user_id="priya",
        name="Priya",
        facts={"ongoing_conditions": "Asthma"},
        db_path=TEST_DB_PATH,
    )

    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Mera naam Priya hai. Kripya mera saved record delete kar do aur forget me."
        )

        result.expect.next_event().is_function_call(name="forget_caller")
        result.expect.next_event().is_function_call_output()
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Confirms that Priya's saved records and facts have been completely deleted or wiped.
                """,
            )
        )
        result.expect.no_more_events()

    # Verify DB state
    assert db.get_user_profile("priya", db_path=TEST_DB_PATH) is None
