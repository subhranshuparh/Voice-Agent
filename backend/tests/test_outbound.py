import asyncio

import pytest
from livekit.agents import AgentSession, llm
from livekit.plugins import google

import db
from agent import Assistant


def _llm() -> llm.LLM:
    return google.LLM(model="gemini-3.5-flash-lite")


@pytest.mark.asyncio
async def test_outbound_opening_compliance() -> None:
    """Day 6 Step 4 Evaluation: Outbound opening line compliance.

    Verifies that the agent opens with who's calling, why, and how to make it stop (opt-out).
    """
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="[OUTBOUND CALL CONNECTED] Hello, who is this?"
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Delivers the mandatory outbound opening statement in Hinglish:
                1. States identity and purpose: Aarogya Mitra, Bharat Health Access Initiative, health/vaccination/follow-up reminder.
                2. States how to opt-out or make it stop: 'Stop' or 'Stop calling' keh kar opt out kar sakte hain.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_opt_out_stop_calling_tool() -> None:
    """Day 6 Step 4 Evaluation: Processing immediate opt-out / stop calling request."""
    await asyncio.sleep(6)  # Rate limit protection
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Mujhe aur calls mat karo, stop calling me right now!"
        )

        # Verify tool call opt_out_stop_calling was triggered
        result.expect.next_event().is_function_call(name="opt_out_stop_calling")
        result.expect.next_event().is_function_call_output()

        # Verify agent's polite closing confirmation
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Confirms politely in Hindi (Devanagari script) or Hinglish that the caller has been opted out from future outbound calls and will not be contacted again.
                """,
            )
        )

        result.expect.no_more_events()

    # Check database fact persistence
    profile = db.get_user_profile("caller_opt_out") or db.get_user_profile("caller")
    assert profile is not None


@pytest.mark.asyncio
async def test_schedule_followup_reminder_tool() -> None:
    """Day 6 Evaluation: Scheduling or rescheduling a reminder call."""
    await asyncio.sleep(6)  # Rate limit protection
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Mujhe kal subah 10 baje call karna reminder ke liye."
        )

        # Verify tool call schedule_followup_reminder was triggered
        result.expect.next_event().is_function_call(name="schedule_followup_reminder")
        result.expect.next_event().is_function_call_output()

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Confirms politely in Hindi (Devanagari script) or Hinglish that the follow-up reminder has been scheduled for tomorrow morning at 10 AM.
                """,
            )
        )

        result.expect.no_more_events()
