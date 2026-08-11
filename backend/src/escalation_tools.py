import json
import logging
import os
import random
import re
import urllib.request
from typing import Any, Optional

import db

logger = logging.getLogger("escalation_tools")


def sanitize_private_info(text: str) -> str:
    """Scrub private information (passwords, OTPs, PINs, Aadhaar, account numbers) from summaries.

    Day 7 Step 3 Requirement: Do not include passwords, OTPs, PINs, account numbers,
    or other private information in escalation summaries.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Remove 16-digit card / bank account numbers FIRST (before 12-digit match)
    sanitized = re.sub(
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "[REDACTED_ACCOUNT]",
        sanitized,
    )

    # 2. Remove Aadhaar numbers (12 digits, optional spaces/dashes)
    sanitized = re.sub(
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[REDACTED_AADHAAR]", sanitized
    )

    # 3. Remove Passwords, OTPs, PINs phrases
    sanitized = re.sub(
        r"(?i)\b(otp|password|pin|passcode|secret)\s*[:=]?\s*[\w\d@#$!%*?&]{3,20}\b",
        r"\1: [REDACTED]",
        sanitized,
    )

    return sanitized


def send_discord_webhook(
    escalation_data: dict[str, Any], webhook_url: Optional[str] = None
) -> bool:
    """Send a structured Discord webhook alert for human help requests.

    Day 7 Step 5: Send the request somewhere real (Discord Webhook).
    """
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        logger.info(
            "DISCORD_WEBHOOK_URL not configured. Escalation saved to database only."
        )
        return False

    urgency_colors = {
        "emergency": 15158332,  # Red
        "high": 15105570,  # Orange
        "medium": 16776960,  # Yellow
        "low": 3447003,  # Blue
    }

    urgency = str(escalation_data.get("urgency", "medium")).lower()
    color = urgency_colors.get(urgency, 16776960)

    payload = {
        "username": "Aarogya Mitra Alert Bot",
        "avatar_url": "https://murf.ai/favicon.ico",
        "embeds": [
            {
                "title": f"🚨 Human Help Escalation Request: {escalation_data.get('escalation_id')}",
                "description": f"**Urgency Level**: `{urgency.upper()}`\n**Status**: `OPEN`",
                "color": color,
                "fields": [
                    {
                        "name": "👤 Who Needs Help",
                        "value": f"**Name**: {escalation_data.get('caller_name')}\n**Contact**: {escalation_data.get('phone_or_contact') or 'N/A'}",
                        "inline": True,
                    },
                    {
                        "name": "🗣️ Language & Contact Method",
                        "value": f"**Language**: {escalation_data.get('language')}\n**Follow-up**: {escalation_data.get('preferred_followup')}",
                        "inline": True,
                    },
                    {
                        "name": "📋 What Happened (Summary)",
                        "value": escalation_data.get("what_happened", "N/A"),
                        "inline": False,
                    },
                    {
                        "name": "🔍 What Agent Checked",
                        "value": escalation_data.get("checked_by_agent", "N/A"),
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "Bharat Health Access Initiative • #VoiceForBharat • Day 7 Escalation"
                },
            }
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AarogyaMitraVoiceAgent/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status in (200, 204)
    except Exception as err:
        logger.error(f"Failed to post to Discord Webhook: {err}")
        return False


def process_human_help_request(
    caller_name: str,
    reason_type: str,
    what_happened: str,
    checked_by_agent: str,
    user_permission_granted: bool,
    urgency: str = "medium",
    language: str = "Hinglish",
    preferred_followup: str = "Phone Call",
    phone_or_contact: str = "",
    db_path: str = db.DEFAULT_DB_PATH,
    webhook_url: Optional[str] = None,
) -> str:
    """Core function to sanitize, deduplicate, persist, and dispatch human help escalation requests.

    Day 7 Step 4: Ask before sharing. If user_permission_granted is False, refuse request creation.
    Day 7 Step 6: Return reference ID and honest next steps.
    """
    # Step 4 check: Mandatory consent
    if not user_permission_granted:
        return (
            "PERMISSION_REFUSED: Caller did not give permission to share details. "
            "Escalation request was NOT created. Direct caller to emergency lines (108/104) if needed."
        )

    # Step 3 check: Scrub private data
    clean_what_happened = sanitize_private_info(what_happened)
    clean_checked = sanitize_private_info(checked_by_agent)

    # Generate unique 5-digit reference ID
    random_num = random.randint(10000, 99999)
    escalation_id = f"ESC-{random_num}"

    # Step 5 & Advanced: Save to SQLite database with duplicate merging logic
    record = db.save_escalation(
        escalation_id=escalation_id,
        caller_name=caller_name,
        reason_type=reason_type,
        what_happened=clean_what_happened,
        checked_by_agent=clean_checked,
        urgency=urgency.lower(),
        language=language,
        preferred_followup=preferred_followup,
        phone_or_contact=phone_or_contact,
        db_path=db_path,
    )

    ref_id = record.get("escalation_id", escalation_id)
    is_updated = record.get("is_duplicate_updated", False)

    # Dispatch to Discord webhook if configured
    send_discord_webhook(record, webhook_url=webhook_url)

    if is_updated:
        return (
            f"SUCCESS_UPDATED: Updated existing open escalation request {ref_id} for {caller_name}. "
            f"Inform the caller: 'Aapka issue existing ticket {ref_id} mein update kar diya gaya hai. "
            f"Hamare healthcare supervisor 2 se 4 ghante ke andar aapko call karenge.'"
        )

    return (
        f"SUCCESS_CREATED: Human help request successfully created with Reference ID: {ref_id}. "
        f"Inform the caller: 'Aapki request reference ID {ref_id} ke saath submit ho gayi hai. "
        f"Hamari healthcare supervisor team 2 se 4 ghante ke andar aapko follow-up call karegi.'"
    )
