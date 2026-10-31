import sqlite3
from datetime import datetime
from typing import Optional
from backend.config import settings


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Translation cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            text_key TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (source_lang, target_lang, text_key)
        )
    """)

    # Conversation context and audit table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            session_id TEXT PRIMARY KEY,
            merchant_id TEXT NOT NULL,
            messages_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Tool execution audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL,
            merchant_id TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_cached_translation(source_lang: str, target_lang: str, text_key: str) -> Optional[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT translated_text FROM translations WHERE source_lang = ? AND target_lang = ? AND text_key = ?",
        (source_lang, target_lang, text_key)
    )
    row = cursor.fetchone()
    conn.close()
    return row["translated_text"] if row else None


def set_cached_translation(source_lang: str, target_lang: str, text_key: str, translated_text: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO translations (source_lang, target_lang, text_key, translated_text, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_lang, target_lang, text_key) DO UPDATE SET
            translated_text = excluded.translated_text,
            created_at = excluded.created_at
    """, (source_lang, target_lang, text_key, translated_text, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def log_tool_call(tool_name: str, merchant_id: str, arguments_json: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tool_audit_logs (tool_name, merchant_id, arguments_json, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (tool_name, merchant_id, arguments_json, status, datetime.now().isoformat()))
    conn.commit()
    conn.close()


# Ensure tables exist on import
init_db()
