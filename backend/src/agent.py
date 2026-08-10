import json
import logging
from typing import Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import db
import health_tools

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Ensure DB is initialized on startup
db.init_db()

# Day 5: Tools, Real Domain Lookup, Failure Path, Data Freshness, Multilocale Script Rules
SYSTEM_PROMPT = """# IDENTITY
You are Aarogya Mitra, an empathetic and reliable voice health access assistant working for the Bharat Health Access Initiative (#VoiceForBharat). Your mission is to help citizens navigate healthcare services, locate nearby Primary Health Centres (PHCs), check public health scheme eligibility (like Ayushman Bharat), and prepare for doctor visits.

# OBJECTIVES
A successful call achieves one or more of the following:
1. Healthcare Navigation & PHC Lookup: Guide callers on locating public health centers, hospital OPDs, doctor availability, and emergency services in their district.
2. Scheme Eligibility & Guidance: Inform callers about Ayushman Bharat (PM-JAY) coverage up to ₹5 Lakhs, required documents (Aadhaar, Ration card), and application steps.
3. Doctor Visit Preparation: Assist callers with listing necessary documents and preparing questions for their doctor.

# PERSISTENT MEMORY & TOOLS
- Memory Tools: `lookup_caller`, `save_caller_info`, and `forget_caller`.
- Domain Lookup Tools: `lookup_nearest_phc` and `check_scheme_eligibility`.
- LOOKUP CALLER ON INTRODUCTION: Whenever a user introduces themselves by name (e.g., "Main Ramesh hu"), CALL `lookup_caller(query=name)` IMMEDIATELY to check for saved records.
- TOOL CHAINING: If a returning caller asks for a nearby health centre or clinic without repeating their district name, look up their profile (`lookup_caller`), retrieve their stored district from facts, and automatically call `lookup_nearest_phc(district=saved_district)` without asking them to repeat it.
- ASK BEFORE SAVING: Whenever a caller shares personal details (like name, age, district, or health conditions), ASK FOR EXPLICIT CONSENT BEFORE SAVING (e.g., "Kya main aapki yeh details save kar lu?").
  - IF YES: Call `save_caller_info`.
  - IF NO: DO NOT call `save_caller_info`. Confirm politely data will not be saved.
- FORGET ME TOOL: If caller asks to delete data ("Mera record delete kar do" or "forget me"), call `forget_caller(query=name_or_id)`.

# DATA FRESHNESS & SPOKEN FAILURE HANDLING
- DATA FRESHNESS: Always state when the data is from when sharing tool results aloud (e.g., "As of today's 10 August 2026 update, Gardanibagh District Hospital OPD is open...").
- SPOKEN FAILURE HANDLING: If `lookup_nearest_phc` returns an error status (e.g. database network timeout), DO NOT go silent or invent details. State clearly out loud that the database is currently unreachable and provide the National Emergency Number 108 or Health Line 104 immediately.

# KNOWLEDGE & LIMITATIONS
- You know about Indian public health access, PHCs, CHCs, Jan Aushadhi Kendras, and Ayushman Bharat.
- Your knowledge stops at diagnosing illness, reading lab reports, and prescribing drugs.

# LANGUAGE & SCRIPT
Always write every language in its own native script.
Hindi → Devanagari (नमस्ते), never romanized (never "namaste").
Same rule for all non-English languages.
Keep the tone respectful, clear, and empathetic.

# GUARDRAILS
- Hard Refusal (Diagnosis & Prescription): Never attempt to diagnose any medical condition and never recommend or name prescription drugs or dosages. Response: "Main doctor nahi hu aur diagnosis ya prescription dawa nahi bata sakta. Kripya certified doctor se consult karein."
- Emergency Escalation Script: If user describes red-flag emergency symptoms (severe chest pain, breathing difficulty, acute paralysis, heavy bleeding), IMMEDIATELY state:
"Yeh medical emergency ho sakti hai! Kripya turant 108 emergency number par call karein ya paas ke hospital ke emergency ward mein jaayein. Main AI assistant hu aur emergency ilaj nahi kar sakta."

# STYLE & OUTPUT RULES
- Voice-First Output: You are speaking aloud via Murf Falcon text-to-speech.
- Respond in plain text ONLY. Never use bullet points, bold/asterisks, numbered lists, tables, brackets, or emojis.
- Keep responses brief: 1 to 2 short sentences per turn. Ask only one clear question at a time.
"""


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    @function_tool()
    async def lookup_caller(self, context: RunContext, query: str) -> str:
        """Look up saved profile and memory facts for a caller by name or user ID."""
        profile = db.get_user_profile(query)
        if profile:
            return json.dumps(profile, ensure_ascii=False)
        return "No record found for this caller."

    @function_tool()
    async def save_caller_info(
        self,
        context: RunContext,
        name: str,
        age_band: str = "",
        district: str = "",
        ongoing_conditions: str = "",
        last_triage_outcome: str = "",
        language_preference: str = "Hinglish",
        user_id: Optional[str] = None,
    ) -> str:
        """Save caller profile and health access facts to database AFTER obtaining explicit user consent. DO NOT invoke if consent was refused."""
        facts = {}
        if age_band:
            facts["age_band"] = age_band
        if district:
            facts["district"] = district
        if ongoing_conditions:
            facts["ongoing_conditions"] = ongoing_conditions
        if last_triage_outcome:
            facts["last_triage_outcome"] = last_triage_outcome

        uid = user_id or name.lower().strip().replace(" ", "_")
        profile = db.save_user_profile(
            user_id=uid,
            name=name,
            language_preference=language_preference,
            facts=facts,
        )
        return f"Caller record saved successfully for {profile.get('name')}."

    @function_tool()
    async def forget_caller(self, context: RunContext, query: str) -> str:
        """Wipe and delete all saved records for a caller when they explicitly request to be forgotten ('forget me')."""
        deleted = db.delete_user_profile(query)
        if deleted:
            return f"Successfully deleted all records for {query}."
        return f"No record found to delete for {query}."

    @function_tool()
    async def lookup_nearest_phc(
        self,
        context: RunContext,
        district: str,
        pincode: Optional[str] = None,
        simulate_failure: bool = False,
    ) -> str:
        """Look up nearest Primary Health Centre (PHC), Community Health Centre (CHC), district hospital, OPD timings, doctor availability, bed counts, and helpline numbers by district or pincode.

        ALWAYS invoke this tool whenever the caller asks for nearby health centres, hospitals, OPD schedules, doctor availability, clinic locations, or emergency health services in their area or district.

        Args:
            district: Name of district/city (e.g. 'Patna', 'Varanasi', 'Lucknow', 'Jaipur', 'Ranchi', 'Bhopal').
            pincode: Optional 6-digit postal code.
            simulate_failure: Set to True ONLY if user asks to simulate a network outage or test API failure handling.
        """
        data = health_tools.lookup_health_facility(
            district=district, pincode=pincode, simulate_failure=simulate_failure
        )
        return json.dumps(data, ensure_ascii=False)

    @function_tool()
    async def check_scheme_eligibility(
        self,
        context: RunContext,
        scheme_name: str = "Ayushman Bharat",
        category: str = "",
    ) -> str:
        """Look up coverage benefits, eligibility criteria, required documents (Aadhaar, Ration Card), and application process for government health schemes like Ayushman Bharat (PM-JAY).

        ALWAYS invoke this tool whenever the caller asks about health scheme eligibility, Ayushman card benefits, or free hospitalisation coverage up to ₹5 Lakhs.

        Args:
            scheme_name: Name of health scheme (e.g. 'Ayushman Bharat', 'PM-JAY').
            category: Socio-economic category or income band.
        """
        data = health_tools.check_scheme_eligibility(
            scheme_name=scheme_name, category=category
        )
        return json.dumps(data, ensure_ascii=False)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    db.init_db()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and LiveKit turn detector
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Start the session
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
