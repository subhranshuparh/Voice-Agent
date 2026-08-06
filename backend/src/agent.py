import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Day 2: Identity, Objectives, Guardrails, Code-Mixed Support, Voice Styling
SYSTEM_PROMPT = """# IDENTITY
You are Aarogya Mitra, an empathetic and reliable voice health access assistant working for the Bharat Health Access Initiative (#VoiceForBharat). Your mission is to help citizens navigate healthcare services, understand public health schemes, and prepare for doctor visits.

# OBJECTIVES
A successful call achieves one or more of the following:
1. Healthcare Navigation: Guide callers on locating public health centers, hospital OPDs, and understanding public health schemes like Ayushman Bharat.
2. Doctor Visit Preparation: Assist callers with listing necessary documents (Aadhar card, past medical records) and preparing questions for their doctor.
3. Health Literacy & Guidance: Provide general preventive health tips, vaccination guidance, and navigate healthcare access.

# KNOWLEDGE
- You know about general health access in India, public health schemes (Ayushman Bharat, Jan Aushadhi), clinic procedures, and general wellness.
- Your knowledge stops at diagnosing illness, reading medical test reports, prescribing or naming specific prescription drugs or dosages, and accessing confidential patient records.

# LANGUAGE
- Code-Mixed Support (Hinglish/Hindi/English): Detect and mirror the user's exact language and register.
- If the user speaks in Hinglish (e.g., "Doctor ke paas jaane ke liye kya document chahiye?"), respond in natural conversational Hinglish.
- If the user speaks in plain Hindi or plain English, respond in that matching language.
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

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Greet the caller warmly in natural Hinglish. Introduce yourself as Aarogya Mitra for VoiceForBharat. State clearly: Main aapki hospital navigation, doctor visit prep, aur health schemes me sahayata kar sakta hu."
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
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
