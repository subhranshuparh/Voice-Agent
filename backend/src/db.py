import json
import os
import sqlite3
from typing import Any

DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "agent_memory.db")
)


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database and users/escalations tables if not existing."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                language_preference TEXT DEFAULT 'Hinglish',
                facts TEXT NOT NULL,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS escalations (
                escalation_id TEXT PRIMARY KEY,
                caller_name TEXT NOT NULL,
                phone_or_contact TEXT DEFAULT '',
                reason_type TEXT NOT NULL,
                what_happened TEXT NOT NULL,
                checked_by_agent TEXT NOT NULL,
                urgency TEXT DEFAULT 'medium',
                language TEXT DEFAULT 'Hinglish',
                preferred_followup TEXT DEFAULT 'Phone Call',
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_profile(
    query: str, db_path: str = DEFAULT_DB_PATH
) -> dict[str, Any] | None:
    """Look up a user profile by user_id or name (case-insensitive)."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        clean_query = query.strip()
        # Search by exact user_id, exact name match (case insensitive), or partial name
        cur.execute(
            """
            SELECT user_id, name, language_preference, facts, last_interaction
            FROM users
            WHERE LOWER(user_id) = LOWER(?) OR LOWER(name) = LOWER(?)
            LIMIT 1
            """,
            (clean_query, clean_query),
        )
        row = cur.fetchone()
        if not row:
            # Fallback partial name search
            cur.execute(
                """
                SELECT user_id, name, language_preference, facts, last_interaction
                FROM users
                WHERE LOWER(name) LIKE LOWER(?)
                LIMIT 1
                """,
                (f"%{clean_query}%",),
            )
            row = cur.fetchone()

        if row:
            try:
                parsed_facts = json.loads(row["facts"])
            except Exception:
                parsed_facts = {}
            return {
                "user_id": row["user_id"],
                "name": row["name"],
                "language_preference": row["language_preference"],
                "facts": parsed_facts,
                "last_interaction": row["last_interaction"],
            }
    finally:
        conn.close()
    return None


def save_user_profile(
    user_id: str,
    name: str,
    language_preference: str = "Hinglish",
    facts: dict[str, Any] | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Save or update a user profile in the database."""

    init_db(db_path)
    if facts is None:
        facts = {}

    clean_user_id = (
        user_id.strip() if user_id else name.strip().lower().replace(" ", "_")
    )
    clean_name = name.strip()
    facts_json = json.dumps(facts, ensure_ascii=False)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                language_preference = excluded.language_preference,
                facts = excluded.facts,
                last_interaction = CURRENT_TIMESTAMP
            """,
            (clean_user_id, clean_name, language_preference, facts_json),
        )
        conn.commit()
    finally:
        conn.close()

    return get_user_profile(clean_user_id, db_path) or {}


def delete_user_profile(query: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Delete a user profile by user_id or name ("forget me" tool)."""
    init_db(db_path)
    clean_query = query.strip()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM users
            WHERE LOWER(user_id) = LOWER(?) OR LOWER(name) = LOWER(?)
            """,
            (clean_query, clean_query),
        )
        deleted_count = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    return deleted_count > 0


# --- DAY 7: ESCALATION & HUMAN HELP DATABASE FUNCTIONS ---


def save_escalation(
    escalation_id: str,
    caller_name: str,
    reason_type: str,
    what_happened: str,
    checked_by_agent: str,
    urgency: str = "medium",
    language: str = "Hinglish",
    preferred_followup: str = "Phone Call",
    phone_or_contact: str = "",
    db_path: str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Save a human escalation request or update an existing open request if a duplicate exists."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        clean_name = caller_name.strip()
        clean_reason = reason_type.strip().lower()

        # Check for existing open/in_progress escalation for caller with same reason category (Duplicate Prevention)
        cur.execute(
            """
            SELECT escalation_id, what_happened, checked_by_agent
            FROM escalations
            WHERE LOWER(caller_name) = LOWER(?)
              AND LOWER(reason_type) = LOWER(?)
              AND status IN ('open', 'in_progress')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (clean_name, clean_reason),
        )
        existing = cur.fetchone()

        if existing:
            # Update existing open escalation instead of creating duplicate
            target_id = existing["escalation_id"]
            updated_happened = (
                f"{existing['what_happened']} | Follow-up update: {what_happened}"
            )
            updated_checked = f"{existing['checked_by_agent']} | Additional checks: {checked_by_agent}"
            cur.execute(
                """
                UPDATE escalations
                SET what_happened = ?,
                    checked_by_agent = ?,
                    urgency = ?,
                    language = ?,
                    preferred_followup = ?,
                    phone_or_contact = CASE WHEN ? <> '' THEN ? ELSE phone_or_contact END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE escalation_id = ?
                """,
                (
                    updated_happened,
                    updated_checked,
                    urgency,
                    language,
                    preferred_followup,
                    phone_or_contact,
                    phone_or_contact,
                    target_id,
                ),
            )
            conn.commit()
            return {
                "escalation_id": target_id,
                "is_duplicate_updated": True,
                "caller_name": clean_name,
                "reason_type": reason_type,
                "what_happened": updated_happened,
                "checked_by_agent": updated_checked,
                "urgency": urgency,
                "language": language,
                "preferred_followup": preferred_followup,
                "status": "open",
            }

        # Create new escalation entry
        cur.execute(
            """
            INSERT INTO escalations (
                escalation_id, caller_name, phone_or_contact, reason_type,
                what_happened, checked_by_agent, urgency, language,
                preferred_followup, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                escalation_id,
                clean_name,
                phone_or_contact,
                reason_type,
                what_happened,
                checked_by_agent,
                urgency,
                language,
                preferred_followup,
            ),
        )
        conn.commit()
        return {
            "escalation_id": escalation_id,
            "is_duplicate_updated": False,
            "caller_name": clean_name,
            "reason_type": reason_type,
            "what_happened": what_happened,
            "checked_by_agent": checked_by_agent,
            "urgency": urgency,
            "language": language,
            "preferred_followup": preferred_followup,
            "status": "open",
        }
    finally:
        conn.close()


def get_escalation(
    escalation_id: str, db_path: str = DEFAULT_DB_PATH
) -> dict[str, Any] | None:
    """Retrieve an escalation ticket by ID."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT escalation_id, caller_name, phone_or_contact, reason_type,
                   what_happened, checked_by_agent, urgency, language,
                   preferred_followup, status, created_at, updated_at
            FROM escalations
            WHERE LOWER(escalation_id) = LOWER(?)
            """,
            (escalation_id.strip(),),
        )
        row = cur.fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    return None


def get_all_escalations(
    status_filter: str | None = None, db_path: str = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Retrieve all escalation tickets, optionally filtered by status ('open', 'in_progress', 'resolved')."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if status_filter and status_filter.lower() != "all":
            cur.execute(
                """
                SELECT escalation_id, caller_name, phone_or_contact, reason_type,
                       what_happened, checked_by_agent, urgency, language,
                       preferred_followup, status, created_at, updated_at
                FROM escalations
                WHERE LOWER(status) = LOWER(?)
                ORDER BY created_at DESC
                """,
                (status_filter.strip(),),
            )
        else:
            cur.execute(
                """
                SELECT escalation_id, caller_name, phone_or_contact, reason_type,
                       what_happened, checked_by_agent, urgency, language,
                       preferred_followup, status, created_at, updated_at
                FROM escalations
                ORDER BY created_at DESC
                """
            )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_escalation_status(
    escalation_id: str, new_status: str, db_path: str = DEFAULT_DB_PATH
) -> bool:
    """Update status of an escalation ticket ('open', 'in_progress', 'resolved')."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE escalations
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE LOWER(escalation_id) = LOWER(?)
            """,
            (new_status.strip(), escalation_id.strip()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
