import json
import sqlite3
from typing import Any

DEFAULT_DB_PATH = "agent_memory.db"


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database and users table if not existing."""
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
