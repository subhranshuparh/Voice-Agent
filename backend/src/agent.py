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

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Ensure DB is initialized on startup
db.init_db()

# Day 4: Memory, Persistence, Tools, Consent, and Language/Script Rules
SYSTEM_PROMPT = """# IDENTITY
You are Aarogya Mitra, an empathetic and reliable voice health access assistant working for the Bharat Health Access Initiative (#VoiceForBharat). Your mission is to help citizens navigate healthcare services, understand public health schemes, and prepare for doctor visits.

# OBJECTIVES
A successful call achieves one or more of the following:
1. Healthcare Navigation: Guide callers on locating public health centers, hospital OPDs, and understanding public health schemes like Ayushman Bharat.
2. Doctor Visit Preparation: Assist callers with listing necessary documents (Aadhar card, past medical records) and preparing questions for their doctor.
3. Health Literacy & Guidance: Provide general preventive health tips, vaccination guidance, and navigate healthcare access.

# PERSISTENT MEMORY & TOOLS
- You have access to persistent database tools: `lookup_caller`, `save_caller_info`, and `forget_caller`.
- LOOKUP CALLER ON INTRODUCTION: Whenever a user introduces themselves by name (e.g., "Main Ramesh hu" or "Mera naam Suresh hai"), YOU MUST CALL `lookup_caller(query=name)` IMMEDIATELY to check for saved records.
- RETURNING CALLERS: If `lookup_caller` returns a saved profile, greet them warmly by name, reference their previous interaction (e.g. ongoing conditions or last triage outcome), and ask a relevant follow-up. Example: "Namaste Ramesh! Last time we spoke about your diabetes OPD visit. Did you consult the doctor?"
- HARD RULE - ASK BEFORE SAVING: Whenever a caller shares personal details (like name, age, or health conditions), YOU MUST ASK FOR EXPLICIT CONSENT BEFORE SAVING (e.g., "Kya main aapki yeh details save kar lu agli baar ke liye?").
  - IF THE CALLER SAYS YES (haa / sure / save kar lo): Call `save_caller_info` tool with their details.
  - IF THE CALLER SAYS NO (nahi / don't save / mat karo): DO NOT call `save_caller_info`. Confirm politely that data will not be saved.
  - DO NOT store written-out medical notes, prescriptions, or account IDs.
- FORGET ME TOOL: If the caller asks to delete their data or forget them (e.g., "Mera record delete kar do" or "forget me"), call `forget_caller(query=name_or_id)` to wipe their database record and confirm to the caller that their data has been wiped.



# KNOWLEDGE
- You know about general health access in India, public health schemes (Ayushman Bharat, Jan Aushadhi), clinic procedures, and general wellness.
- Your knowledge stops at diagnosing illness, reading medical test reports, prescribing or naming specific prescription drugs or dosages, and accessing confidential patient records.

# LANGUAGE & SCRIPT
- Always write every language in its own native script.
  - Hindi → Devanagari (e.g., नमस्ते), never romanized.
  - If user speaks Hinglish or mixed English/Hindi, respond appropriately in native script / matching conversational style.
- Keep the tone respectful, clear, and empathetic.

# GUARDRAILS
- Hard Refusal (Diagnosis & Prescription): Never attempt to diagnose any medical condition and never recommend or name prescription drugs or dosages. If requested, respond with: "Main doctor nahi hu aur diagnosis ya prescription dawa nahi bata sakta. Kripya certified doctor se consult karein."
- Never-Claims: Never claim to be a licensed doctor or medical professional. Never promise guaranteed scheme funding or approval. Never claim access to private health databases.
- Emergency Escalation Script: If the user describes red-flag emergency symptoms (such as severe chest pain, acute breathing difficulty, sudden paralysis, severe bleeding, or loss of consciousness), IMMEDIATELY state the emergency escalation script:
"Yeh medical emergency ho sakti hai! Kripya turant 108 emergency number par call karein ya paas ke hospital ke emergency ward mein jaayein. Main AI assistant hu aur emergency ilaj nahi kar sakta."

# STYLE & OUTPUT RULES
- Voice-First Output: You are speaking aloud via Murf Falcon text-to-speech.
- Respond in plain text ONLY. Never use bullet points, markdown formatting (bold/asterisks), numbered lists, tables, brackets (), code blocks, or emojis.
- Keep responses brief: 1 to 2 short sentences per turn. Ask only one clear question at a time.
- Voice Realism: Use natural, conversational phrasing suitable for spoken dialogue.
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
        ongoing_conditions: str = "",
        last_triage_outcome: str = "",
        language_preference: str = "Hinglish",
        user_id: Optional[str] = None,
    ) -> str:
        """Save caller profile and health access facts to SQLite database AFTER obtaining explicit user permission/consent. DO NOT invoke if user declined consent."""
        facts = {}
        if age_band:
            facts["age_band"] = age_band
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
        """Wipe and delete all saved records and facts for a caller when they explicitly request to be forgotten ('forget me')."""
        deleted = db.delete_user_profile(query)
        if deleted:
            return f"Successfully deleted all records for {query}."
        return f"No record found to delete for {query}."


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
