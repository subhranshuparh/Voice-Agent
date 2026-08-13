import json
import logging
from typing import Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
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

- CRITICAL TOOL INVOCATION RULE (MUST EXECUTE TOOL FIRST):
  - WHEN THE CALLER SAYS YES / GRANTS PERMISSION (e.g. "Haan", "Permission hai", "Yes, send it"):
    - YOU MUST IMMEDIATELY CALL THE FUNCTION TOOL `create_human_help_request(user_permission_granted=True)` FIRST.
    - NEVER INVENT, MAKE UP, OR SPEAK A REFERENCE ID BEFORE CALLING THE TOOL.
    - ALWAYS wait for the `create_human_help_request` tool output, which returns the real generated Reference ID.
    - Read aloud the exact Reference ID returned by the tool output to the caller (e.g., "Aapki request reference ID ESC-XXXXX ke saath submit ho gayi hai. Hamare healthcare supervisor 2 se 4 ghante mein call karenge").


# OBJECTIVES
A successful call achieves one or more of the following:
1. Outbound Reminders & Follow-ups: Remind citizens about pending child/maternal vaccination doses, routine medication refills, or triage escalation follow-ups.
2. Healthcare Navigation & PHC Lookup: Guide callers on locating public health centers, hospital OPDs, doctor availability, and emergency services in their district.
3. Scheme Eligibility & Guidance: Inform callers about Ayushman Bharat (PM-JAY) coverage up to ₹5 Lakhs, required documents (Aadhaar, Ration card), and application steps.
4. Human Escalation & Support: Identify complex medical triage or hospital disputes, obtain caller consent, and generate human help requests with reference IDs.
5. Rescheduling & Opt-Out Handling: Gracefully reschedule calls when requested or process immediate opt-outs.

# DAY 9: SPECIALIST HANDOFF RULES (CRITICAL)
- SPECIALIST HANDOFF FOR APPOINTMENTS & SCHEDULING:
  - Whenever the caller asks to book, schedule, reschedule, cancel, or check available doctor/clinic slots:
    - YOU MUST IMMEDIATELY CALL THE FUNCTION TOOL `transfer_to_appointment_specialist` as your primary tool call action.
    - Do not output plain conversational text before calling `transfer_to_appointment_specialist`.

# PERSISTENT MEMORY & TOOLS
- Memory Tools: `lookup_caller`, `save_caller_info`, and `forget_caller`.
- Outbound & Follow-up Tools: `opt_out_stop_calling` and `schedule_followup_reminder`.
- Domain Lookup Tools: `lookup_nearest_phc` and `check_scheme_eligibility`.
- Specialist Handoff Tool: `transfer_to_appointment_specialist`.
- Human Help Escalation Tool: `create_human_help_request`.
- HUMAN HELP TOOL (`create_human_help_request`): Invoke ONLY after obtaining explicit caller permission when human intervention is needed.
- OPT-OUT TOOL (`opt_out_stop_calling`): If caller says "stop calling", "opt out", "stop", or "mujhe call mat karo", call `opt_out_stop_calling` IMMEDIATELY.
- RESCHEDULING TOOL (`schedule_followup_reminder`): If caller asks to be called back later, call `schedule_followup_reminder`.
- LOOKUP CALLER ON INTRODUCTION: Whenever a user introduces themselves by name, CALL `lookup_caller(query=name)` IMMEDIATELY.
- ASK BEFORE SAVING: Whenever caller shares personal details, ASK FOR EXPLICIT CONSENT BEFORE SAVING ("Kya main aapki yeh details save kar lu?").
- FORGET ME TOOL: If caller asks to delete data ("Mera record delete kar do" or "forget me"), call `forget_caller(query=name_or_id)`.

# DATA FRESHNESS & SPOKEN FAILURE HANDLING
- DATA FRESHNESS: Always state when the data is from when sharing tool results aloud using the data_timestamp returned by the tool (e.g., "As of today's update...").
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


APPOINTMENT_SPECIALIST_PROMPT = """# IDENTITY & ROLE
You are the Clinic and Appointment Specialist for Bharat Health Access Initiative (#VoiceForBharat). Your single, focused job is to schedule, book, manage, confirm, or check available time slots for primary health centre (PHC) doctor consultations, clinic appointments, and vaccination slots for citizens.

# OBJECTIVES & WORKFLOW
- When taking over the call, introduce yourself clearly as the Clinic & Appointment Specialist.
- Collect or confirm booking details: patient name, preferred clinic/PHC location or district, date, and preferred time slot.
- Use `check_available_slots` to look up clinic slot availability.
- Use `book_clinic_appointment` to finalize the appointment and generate a unique appointment reference ID (e.g. APT-XXXXX).
- Read the generated appointment reference ID clearly to the user once confirmed.

# LANGUAGE & SCRIPT
Always write every language in its own native script. Hindi → Devanagari (नमस्ते), never romanized (never "namaste").
Same rule for all non-English languages.

# GUARDRAILS & LIMITATIONS
- Focus strictly on appointment scheduling, clinic slots, and booking confirmations.
- If asked about medical diagnoses or prescription drugs, state politely: "Main doctor nahi hu aur dawa prescribe nahi kar sakta. Kripya consult ke silsile mein appointment schedule karein."

# STYLE & OUTPUT RULES
- Voice-First Output: Speak aloud via Murf Falcon text-to-speech.
- Plain text ONLY: No bullet points, bold text, lists, markdown tables, or emojis.
- Keep responses brief: 1 to 2 short sentences per turn.
"""


SCHEME_SPECIALIST_PROMPT = """# IDENTITY & ROLE
You are the Government Health Scheme Specialist for Bharat Health Access Initiative (#VoiceForBharat). Your single, focused job is to guide citizens on public health scheme eligibility (such as Ayushman Bharat PM-JAY, AB-PMJAY Golden Card, State Health Insurance), required documents (Aadhaar, Ration Card), and coverage benefits up to ₹5 Lakhs.

# OBJECTIVES & WORKFLOW
- When taking over the call, introduce yourself clearly as the Government Health Scheme Specialist.
- Explain scheme coverage benefits, eligibility criteria, e-KYC steps, and required documents.
- Use `check_scheme_eligibility` tool to verify eligibility guidelines.

# LANGUAGE & SCRIPT
Always write every language in its own native script. Hindi → Devanagari (नमस्ते), never romanized (never "namaste").
Same rule for all non-English languages.

# GUARDRAILS & LIMITATIONS
- Focus strictly on government health schemes and benefit coverage.
- If asked to book appointments, transfer or advise scheduling with the Clinic & Appointment Specialist.

# STYLE & OUTPUT RULES
- Voice-First Output: Speak aloud via Murf Falcon text-to-speech.
- Plain text ONLY: No bullet points, bold text, lists, markdown tables, or emojis.
- Keep responses brief: 1 to 2 short sentences per turn.
"""


class SchemeSpecialistAgent(Agent):
    def __init__(
        self, chat_ctx: ChatContext | None = None, call_id: str = "default-room"
    ) -> None:
        super().__init__(
            instructions=SCHEME_SPECIALIST_PROMPT,
            chat_ctx=chat_ctx,
            tts=murf.TTS(
                voice="Samar",
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True,
            ),
        )
        self.call_id = call_id

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Introduce yourself as the Government Health Scheme Specialist for Bharat Health Access Initiative. Acknowledge the user's scheme inquiry and offer to guide them through Ayushman Bharat eligibility and benefits."
        )

    @function_tool()
    async def check_scheme_eligibility(
        self,
        context: RunContext,
        scheme_name: str = "Ayushman Bharat",
        category: str = "",
    ) -> str:
        """Look up coverage benefits, eligibility criteria, required documents (Aadhaar, Ration Card), and application process for government health schemes like Ayushman Bharat (PM-JAY).

        Args:
            scheme_name: Name of health scheme (e.g. 'Ayushman Bharat', 'PM-JAY').
            category: Socio-economic category or income band.
        """
        db.record_call_action(
            self.call_id,
            "Specialist Scheme Eligibility Check",
            f"Scheme: {scheme_name}",
        )

        data = health_tools.check_scheme_eligibility(
            scheme_name=scheme_name, category=category
        )
        return json.dumps(data, ensure_ascii=False)


class AppointmentSpecialistAgent(Agent):
    def __init__(
        self, chat_ctx: ChatContext | None = None, call_id: str = "default-room"
    ) -> None:
        super().__init__(
            instructions=APPOINTMENT_SPECIALIST_PROMPT,
            chat_ctx=chat_ctx,
            tts=murf.TTS(
                voice="Pooja",
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True,
            ),
        )
        self.call_id = call_id

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Introduce yourself as the Clinic & Appointment Specialist for Bharat Health Access Initiative. Acknowledge the user's booking request and ask how you can help schedule their appointment or vaccination slot."
        )

    @function_tool()
    async def check_available_slots(
        self,
        context: RunContext,
        clinic_or_district: str,
        preferred_date: str = "tomorrow",
    ) -> str:
        """Check available doctor consultation and clinic appointment slots for a given PHC, clinic, or district.

        Args:
            clinic_or_district: Name of PHC, clinic, or district city (e.g. 'Patna PHC', 'Varanasi', 'Lucknow UPHC').
            preferred_date: Preferred date or day (e.g. 'today', 'tomorrow', 'Monday').
        """
        slots = [
            "09:30 AM - General OPD",
            "11:00 AM - Maternal & Child Health",
            "02:00 PM - Doctor Consultation",
            "04:30 PM - Routine Vaccination",
        ]
        db.record_call_action(
            call_id=self.call_id,
            action_name="Checked Appointment Slots",
            action_detail=f"Facility: {clinic_or_district}, Date: {preferred_date}",
        )
        return json.dumps(
            {
                "status": "available",
                "facility": clinic_or_district,
                "date": preferred_date,
                "available_slots": slots,
                "data_timestamp": "2026-08-13 23:30 IST",
            },
            ensure_ascii=False,
        )

    @function_tool()
    async def book_clinic_appointment(
        self,
        context: RunContext,
        patient_name: str,
        clinic_name: str,
        preferred_date: str,
        preferred_time: str,
        department: str = "General OPD",
    ) -> str:
        """Book and confirm a clinic appointment or vaccination slot for a patient, returning a unique appointment reference ID.

        Args:
            patient_name: Name of the patient.
            clinic_name: Name of the PHC, CHC, or hospital clinic.
            preferred_date: Appointment date (e.g. 'tomorrow', '15th August').
            preferred_time: Preferred time slot (e.g. '10:00 AM').
            department: Medical department (e.g. 'General OPD', 'Vaccination', 'Pediatrics', 'Dental').
        """
        import random

        apt_id = f"APT-{random.randint(10000, 99999)}"

        uid = patient_name.lower().strip().replace(" ", "_")
        existing = db.get_user_profile(uid) or {}
        facts = existing.get("facts", {})
        facts["last_appointment"] = {
            "appointment_id": apt_id,
            "clinic": clinic_name,
            "date": preferred_date,
            "time": preferred_time,
            "department": department,
        }
        db.save_user_profile(user_id=uid, name=patient_name, facts=facts)

        db.record_call_action(
            call_id=self.call_id,
            action_name="Booked Clinic Appointment",
            action_detail=f"ID: {apt_id}, Patient: {patient_name}, Facility: {clinic_name}, Time: {preferred_date} {preferred_time}",
        )

        return json.dumps(
            {
                "status": "confirmed",
                "appointment_id": apt_id,
                "patient_name": patient_name,
                "clinic_name": clinic_name,
                "date": preferred_date,
                "time": preferred_time,
                "department": department,
                "message": f"Appointment successfully booked with reference ID {apt_id}.",
            },
            ensure_ascii=False,
        )

    @function_tool()
    async def transfer_back_to_main_assistant(
        self, context: RunContext
    ) -> tuple[Agent, str]:
        """Transfer the caller back to the main Aarogya Mitra assistant when appointment booking is complete or the user asks general healthcare questions."""
        main_agent = Assistant(call_id=self.call_id)
        return (
            main_agent,
            "Main aapko hamare Main Health Assistant se wapas connect kar raha hu.",
        )


class Assistant(Agent):
    def __init__(self, call_id: str = "default-room") -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.call_id = call_id

    @function_tool()
    async def transfer_to_appointment_specialist(
        self, context: RunContext
    ) -> tuple[Agent, str]:
        """Transfer the caller to our Clinic and Appointment Specialist whenever the caller asks to book, schedule, reschedule, cancel, or check slots for a clinic appointment, doctor consultation, or vaccination slot."""
        specialist = AppointmentSpecialistAgent(
            chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
            call_id=self.call_id,
        )
        return (
            specialist,
            "Main aapko hamare Clinic aur Appointment Specialist se connect kar raha hu.",
        )

    @function_tool()
    async def transfer_to_scheme_specialist(
        self, context: RunContext
    ) -> tuple[Agent, str]:
        """Transfer the caller to our Government Health Scheme Specialist whenever the caller asks in detail about Ayushman Bharat, PM-JAY eligibility, scheme coverage limits, or required documents."""
        specialist = SchemeSpecialistAgent(
            chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
            call_id=self.call_id,
        )
        return (
            specialist,
            "Main aapko hamare Government Health Scheme Specialist se connect kar raha hu.",
        )

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
        if user_permission_granted:
            db.record_call_action(
                call_id=self.call_id,
                action_name="Human Escalation Ticket",
                action_detail=f"Caller: {caller_name}, Reason: {reason_type}",
            )
        else:
            db.mark_call_failure_category(self.call_id, "user_declined_consent")

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

        db.record_call_action(
            call_id=self.call_id,
            action_name="Opt-Out Registered",
            action_detail=f"Caller: {name}",
        )
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

        db.record_call_action(
            call_id=self.call_id,
            action_name="Follow-up Reminder Scheduled",
            action_detail=f"Time: {preferred_time}",
        )
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
        if simulate_failure:
            db.mark_call_failure_category(self.call_id, "tool_or_api_error")
        else:
            db.record_call_action(
                self.call_id,
                "PHC & Health Facility Lookup",
                f"District: {district}",
            )

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
        db.record_call_action(
            self.call_id,
            "Scheme Eligibility Check",
            f"Scheme: {scheme_name}",
        )

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
    call_id = ctx.room.name or "browser-room"
    db.log_call_start(
        call_id=call_id, participant_identity="Browser User", channel="browser"
    )

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

    try:
        # Start the session
        await session.start(
            agent=Assistant(call_id=call_id),
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
    finally:
        db.finalize_call(call_id=call_id)


if __name__ == "__main__":
    cli.run_app(server)
