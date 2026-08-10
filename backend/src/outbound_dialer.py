"""
Outbound Health Access Call Dialer — Day 6 Telephony Integration & Campaign Runner.

Usage:
  Single Outbound Phone Call:
    uv run python src/outbound_dialer.py --to +919876543210

  Campaign Batch Calls from CSV:
    uv run python src/outbound_dialer.py --csv health_reminders.csv

  Local Dry-Run / Browser Test Mode:
    uv run python src/outbound_dialer.py --test --name "Ramesh Kumar" --reminder "Polio Booster"
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

load_dotenv(os.path.join(_ROOT, ".env.local"), override=False)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("outbound_dialer")

_E164_RE = re.compile(r"^\+\d{7,15}$")


def clean_phone(raw: str) -> str:
    """Validate and clean E.164 phone number format (+CountryCodeNumber)."""
    phone = raw.strip()
    if not _E164_RE.match(phone):
        raise ValueError(
            f"Invalid phone number {phone!r}. Must be E.164 format e.g. +919876543210."
        )
    return phone


@dataclass
class OutboundCallOutcome:
    phone_number: str
    recipient_name: str
    reminder_type: str
    due_date: str
    district: str
    room_name: str
    call_start_time: str
    call_end_time: Optional[str] = None
    duration_seconds: float = 0.0
    outcome_status: str = (
        "pending"  # completed, opt_out, no_answer, busy, voicemail, immediate_hangup
    )
    opt_out_registered: bool = False
    retry_recommended: bool = False
    notes: str = ""

    def save(self) -> str:
        logs_dir = os.path.join(_ROOT, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(logs_dir, f"outbound_{ts}_{self.room_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        return filepath


async def dispatch_outbound_call(
    phone_number: str,
    recipient_name: str = "Citizen",
    reminder_type: str = "Health Vaccination Reminder",
    due_date: str = "August 15, 2026",
    district: str = "Patna",
) -> OutboundCallOutcome:
    """Dispatch an outbound SIP call using LiveKit API and track outcome."""
    try:
        from livekit import api as lk_api
    except ImportError:
        logger.error("livekit-api not installed. Run `uv sync` first.")
        sys.exit(1)

    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    sip_trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

    if not livekit_url or not api_key or not api_secret:
        logger.error(
            "LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required."
        )
        sys.exit(1)

    room_name = f"outbound-health-{uuid.uuid4().hex[:8]}"
    start_time = datetime.now().isoformat()
    outcome = OutboundCallOutcome(
        phone_number=phone_number,
        recipient_name=recipient_name,
        reminder_type=reminder_type,
        due_date=due_date,
        district=district,
        room_name=room_name,
        call_start_time=start_time,
    )

    metadata = {
        "outbound": True,
        "phone_number": phone_number,
        "customer_name": recipient_name,
        "reminder_type": reminder_type,
        "due_date": due_date,
        "district": district,
    }

    lk = lk_api.LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
    t0 = time.monotonic()

    try:
        logger.info("Creating room: %s", room_name)
        await lk.room.create_room(lk_api.CreateRoomRequest(name=room_name))

        # Create dispatch for our agent
        dispatch = await lk.agent_dispatch.create_dispatch(
            lk_api.CreateAgentDispatchRequest(
                agent_name="my-agent",
                room=room_name,
                metadata=json.dumps(metadata),
            )
        )
        logger.info("Agent dispatch created: %s", dispatch.id)

        # Dial outbound SIP if trunk ID is available
        if sip_trunk_id:
            logger.info(
                "Dialing outbound SIP trunk %s to %s...", sip_trunk_id, phone_number
            )
            try:
                await lk.sip.create_sip_participant(
                    lk_api.CreateSIPParticipantRequest(
                        sip_trunk_id=sip_trunk_id,
                        sip_call_to=phone_number,
                        room_name=room_name,
                        participant_identity=f"phone-{phone_number}",
                        wait_until_answered=True,
                    )
                )
                logger.info("Call answered by recipient %s!", phone_number)
                outcome.outcome_status = "completed"
            except Exception as sip_err:
                logger.warning("SIP dial failed or not answered: %s", sip_err)
                outcome.outcome_status = "no_answer"
                outcome.retry_recommended = True
                outcome.notes = f"SIP call failed: {sip_err}"
        else:
            logger.info(
                "LIVEKIT_SIP_OUTBOUND_TRUNK_ID not set. Room created and dispatch registered."
            )
            logger.info(
                "You can join room '%s' via LiveKit Agents frontend/playground to test.",
                room_name,
            )
            outcome.outcome_status = "completed"
            outcome.notes = "Dispatched room for WebRTC/Playground connection."

    except Exception as exc:
        logger.error("Outbound dispatch error: %s", exc)
        outcome.outcome_status = "failed"
        outcome.notes = str(exc)
    finally:
        await lk.aclose()

    outcome.call_end_time = datetime.now().isoformat()
    outcome.duration_seconds = round(time.monotonic() - t0, 2)
    saved_path = outcome.save()
    logger.info("Outcome saved to %s (Status: %s)", saved_path, outcome.outcome_status)
    return outcome


async def run_csv_campaign(csv_path: str) -> list[OutboundCallOutcome]:
    """Run campaign batch calling for each recipient in CSV."""
    if not os.path.exists(csv_path):
        logger.error("CSV file not found: %s", csv_path)
        sys.exit(1)

    outcomes = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(
        "Starting campaign dispatch for %d recipients from %s", len(rows), csv_path
    )
    for i, row in enumerate(rows, 1):
        name = row.get("name", "Citizen").strip()
        phone_raw = row.get("phone", "").strip()
        reminder = row.get("reminder_type", "Health Reminder").strip()
        due_date = row.get("due_date", "Today").strip()
        district = row.get("district", "General").strip()

        try:
            phone = clean_phone(phone_raw)
        except ValueError as err:
            logger.warning("[%d/%d] Skipping %s: %s", i, len(rows), name, err)
            continue

        logger.info(
            "[%d/%d] Calling %s (%s) for %s...", i, len(rows), name, phone, reminder
        )
        res = await dispatch_outbound_call(
            phone_number=phone,
            recipient_name=name,
            reminder_type=reminder,
            due_date=due_date,
            district=district,
        )
        outcomes.append(res)
        await asyncio.sleep(2)  # Pause between calls

    logger.info("Campaign completed. Executed %d calls.", len(outcomes))
    return outcomes


def main():
    parser = argparse.ArgumentParser(
        description="Outbound Health Access Call Dialer (Day 6)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--to", help="Single outbound phone number in E.164 format (+919876543210)"
    )
    group.add_argument("--csv", help="Path to campaign CSV file")
    group.add_argument("--test", action="store_true", help="Run local test dispatch")

    parser.add_argument(
        "--name", default="Ramesh Kumar", help="Recipient name for single/test call"
    )
    parser.add_argument(
        "--reminder",
        default="Polio Booster Dose Vaccination",
        help="Reminder subject for single/test call",
    )
    parser.add_argument(
        "--due", default="August 15, 2026", help="Due date for reminder"
    )
    parser.add_argument("--district", default="Patna", help="District for recipient")

    args = parser.parse_args()

    if args.test:
        print("\n--- OUTBOUND CALL TEST DISPATCH ---")
        print(f"Recipient : {args.name}")
        print(f"Reminder  : {args.reminder}")
        print(f"Due Date  : {args.due}")
        print(f"District  : {args.district}\n")
        asyncio.run(
            dispatch_outbound_call(
                phone_number="+919876543210",
                recipient_name=args.name,
                reminder_type=args.reminder,
                due_date=args.due,
                district=args.district,
            )
        )
    elif args.to:
        phone = clean_phone(args.to)
        asyncio.run(
            dispatch_outbound_call(
                phone_number=phone,
                recipient_name=args.name,
                reminder_type=args.reminder,
                due_date=args.due,
                district=args.district,
            )
        )
    elif args.csv:
        asyncio.run(run_csv_campaign(args.csv))


if __name__ == "__main__":
    main()
