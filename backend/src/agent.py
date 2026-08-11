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
import escalation_tools
import health_tools

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Ensure DB is initialized on startup
db.init_db()

# Day 7: Know When to Ask for Human Help — Human Escalation Tool, Mandatory Consent, Sanitization & Clear Next Steps
SYSTEM_PROMPT = """# IDENTITY
You are Aarogya Mitra, an empathetic and reliable voice health access assistant working for the Bharat Health Access Initiative (#VoiceForBharat). Your mission is to help citizens navigate healthcare services, locate nearby Primary Health Centres (PHCs), check public health scheme eligibility (like Ayushman Bharat), prepare for doctor visits, deliver outbound reminders, and escalate complex issues to human healthcare supervisors when necessary.

# OUTBOUND CALL OPENING RULES (DAY 6 STEP 4 COMPLIANCE - CRITICAL)
- On OUTBOUND calls (when initiated as an outbound health reminder call or when user input is '[OUTBOUND CALL CONNECTED]'): your VERY FIRST turn MUST strictly deliver the following TWO SENTENCES before any other text:
  - Sentence 1 (Who & Why): "Namaste, main Aarogya Mitra bol raha hu Bharat Health Access Initiative se, aapki pending vaccination dose aur healthcare follow-up reminder ke silsile mein."
  - Sentence 2 (How to Stop / Opt Out): "Agar aap aage se yeh reminder calls stop karna chahte hain, toh aap kisi bhi waqt 'Stop' ya 'Stop calling' keh kar opt-out kar sakte hain."
- On INBOUND calls (when user calls in, introduces themselves, or asks a question), respond naturally to the user's query and trigger `lookup_caller` or other memory tools immediately as appropriate.


# DAY 7: WHEN AND HOW TO ASK FOR HUMAN HELP (CRITICAL)
- REASONS TO ESCALATE TO HUMAN HELP:
  1. Red-Flag Symptoms / Emergency Triage: When the caller reports severe symptoms (severe chest pain, acute breathing difficulty, high fever in infants, sudden numbness) or explicitly requests a certified doctor's diagnosis/prescription that AI cannot provide.
  2. Hospital Dispute / Scheme Rejection / Missing Facility Data: When the caller reports an empaneled hospital rejecting their Ayushman Bharat card, an active payment/billing dispute at a public clinic, or missing facility data in a remote district.

- MANDATORY CONSENT BEFORE CREATING ESCALATION REQUEST (STEP 4):
  - BEFORE invoking `create_human_help_request`, you MUST tell the caller what information you will share and ask for explicit permission:
    Example: "Kya main aapka naam, issue details, aur contact number humare healthcare supervisor ko send kar du taaki woh follow-up call kar sakein?"
  - IF THE CALLER SAYS NO / REFUSES PERMISSION:
    - DO NOT invoke `create_human_help_request`.
    - Respect their refusal, inform them no data will be sent, and advise them to directly call Emergency 108 or Health Helpline 104.
  - IF THE CALLER SAYS YES / GRANTS PERMISSION:
    - Immediately invoke `create_human_help_request` with `user_permission_granted=True`.

- CLEAR NEXT STEP & REFERENCE ID (STEP 6):
  - After `create_human_help_request` returns a reference ID (e.g. ESC-84920), state the reference ID clearly to the caller.
  - Explain honest next steps: "Aapki request reference ID ESC-XXXXX ke saath submit ho gayi hai. Hamare healthcare supervisor 2 se 4 ghante ke andar aapko follow-up call karenge."


# OBJECTIVES
A successful call achieves one or more of the following:
1. Outbound Reminders & Follow-ups: Remind citizens about pending child/maternal vaccination doses, routine medication refills, or triage escalation follow-ups.
2. Healthcare Navigation & PHC Lookup: Guide callers on locating public health centers, hospital OPDs, doctor availability, and emergency services in their district.
3. Scheme Eligibility & Guidance: Inform callers about Ayushman Bharat (PM-JAY) coverage up to ₹5 Lakhs, required documents (Aadhaar, Ration card), and application steps.
4. Human Escalation & Support: Identify complex medical triage or hospital disputes, obtain caller consent, and generate human help requests with reference IDs.
5. Rescheduling & Opt-Out Handling: Gracefully reschedule calls when requested or process immediate opt-outs.

# PERSISTENT MEMORY & TOOLS
- Memory Tools: `lookup_caller`, `save_caller_info`, and `forget_caller`.
- Outbound & Follow-up Tools: `opt_out_stop_calling` and `schedule_followup_reminder`.
- Domain Lookup Tools: `lookup_nearest_phc` and `check_scheme_eligibility`.
- Human Help Escalation Tool: `create_human_help_request`.
- HUMAN HELP TOOL (`create_human_help_request`): Invoke ONLY after obtaining explicit caller permission when human intervention is needed.
- OPT-OUT TOOL (`opt_out_stop_calling`): If caller says "stop calling", "opt out", "stop", or "mujhe call mat karo", call `opt_out_stop_calling` IMMEDIATELY.
- RESCHEDULING TOOL (`schedule_followup_reminder`): If caller asks to be called back later, call `schedule_followup_reminder`.
- LOOKUP CALLER ON INTRODUCTION: Whenever a user introduces themselves by name, CALL `lookup_caller(query=name)` IMMEDIATELY.
- ASK BEFORE SAVING: Whenever caller shares personal details, ASK FOR EXPLICIT CONSENT BEFORE SAVING ("Kya main aapki yeh details save kar lu?").
- FORGET ME TOOL: If caller asks to delete data ("Mera record delete kar do" or "forget me"), call `forget_caller(query=name_or_id)`.

# DATA FRESHNESS & SPOKEN FAILURE HANDLING
- DATA FRESHNESS: Always state when the data is from when sharing tool results aloud (e.g., "As of today's 11 August 2026 update...").
- SPOKEN FAILURE HANDLING: If `lookup_nearest_phc` returns an error status, state clearly out loud that the database is unreachable and provide National Emergency Number 108 or Health Line 104 immediately.

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
    async def create_human_help_request(
        self,
        context: RunContext,
        caller_name: str,
        reason_type: str,
        what_happened: str,
        checked_by_agent: str,
        user_permission_granted: bool,
        urgency: str = "medium",
        language: str = "Hinglish",
        preferred_followup: str = "Phone Call",
        phone_or_contact: str = "",
    ) -> str:
        """Create a human help request / escalation ticket for healthcare supervisor intervention when the issue exceeds AI capabilities or requires human escalation.

        CRITICAL: ALWAYS ask the caller for explicit permission before calling this tool ('Kya main aapki details hamari supervisor team ko send kar du?').
        If user_permission_granted is False, DO NOT call this tool.

        Args:
            caller_name: Name of caller/patient needing help.
            reason_type: Reason category e.g. 'red_flag_symptoms', 'hospital_dispute', 'missing_health_data', or 'complex_triage'.
            what_happened: Concise summary of caller's issue/symptoms/dispute (scrubbed of OTPs/passwords/account numbers).
            checked_by_agent: What agent checked or attempted (e.g. PHC lookup or scheme check).
            user_permission_granted: Set to True ONLY if caller explicitly granted permission to share details with human supervisor.
            urgency: Urgency level ('low', 'medium', 'high', or 'emergency').
            language: Caller's spoken language (e.g. 'Hindi', 'Hinglish', 'English').
            preferred_followup: Preferred follow-up method (e.g. 'Phone Call', 'SMS', 'WhatsApp').
            phone_or_contact: Caller phone number or contact details if provided.
        """
        return escalation_tools.process_human_help_request(
            caller_name=caller_name,
            reason_type=reason_type,
            what_happened=what_happened,
            checked_by_agent=checked_by_agent,
            user_permission_granted=user_permission_granted,
            urgency=urgency,
            language=language,
            preferred_followup=preferred_followup,
            phone_or_contact=phone_or_contact,
        )

    @function_tool()
    async def opt_out_stop_calling(
        self,
        context: RunContext,
        caller_name_or_id: str = "",
        reason: str = "User requested opt-out during outbound call",
    ) -> str:
        """Register opt-out / stop calling preference for the caller so they no longer receive automated outbound health reminders.

        ALWAYS invoke this tool immediately whenever the caller says 'stop calling', 'opt out', 'stop', 'don't call me', 'do not call', 'un-subscribe', or 'mujhe call mat karo'.
        """
        uid = (
            caller_name_or_id.lower().strip().replace(" ", "_")
            if caller_name_or_id
            else "caller_opt_out"
        )
        existing = db.get_user_profile(uid) or {}
        facts = existing.get("facts", {})
        facts["opted_out"] = True
        facts["opt_out_reason"] = reason
        name = existing.get("name") or caller_name_or_id or "Caller"
        db.save_user_profile(user_id=uid, name=name, facts=facts)
        return f"Caller {name} has been successfully opted out from future outbound reminder calls."

    @function_tool()
    async def schedule_followup_reminder(
        self,
        context: RunContext,
        preferred_time: str,
        caller_name_or_id: str = "",
        reminder_type: str = "health_checkup",
    ) -> str:
        """Schedule or reschedule an outbound health reminder call at the user's preferred time.

        ALWAYS invoke this tool when the user requests a specific call back time (e.g. 'Call me tomorrow at 5 PM', 'Shaam ko call karna', 'Kal subah 10 baje reminder dena').
        """
        uid = (
            caller_name_or_id.lower().strip().replace(" ", "_")
            if caller_name_or_id
            else "caller_schedule"
        )
        existing = db.get_user_profile(uid) or {}
        facts = existing.get("facts", {})
        facts["next_reminder"] = preferred_time
        facts["reminder_type"] = reminder_type
        name = existing.get("name") or caller_name_or_id or "Caller"
        db.save_user_profile(user_id=uid, name=name, facts=facts)
        return f"Outbound follow-up reminder scheduled successfully for {name} at {preferred_time}."

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
