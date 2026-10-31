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

    # Persistent Sarvam translation cache table (ai_prompt.md Section 8)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translation_cache (
            cache_key TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            source_language TEXT NOT NULL,
            target_language TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            source_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Merchant-scoped OpenAI response cache table (ai_prompt.md Section 9)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_response_cache (
            cache_key TEXT PRIMARY KEY,
            merchant_id TEXT NOT NULL,
            intent TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            financial_data_version TEXT NOT NULL,
            response_payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            hit_count INTEGER NOT NULL DEFAULT 0
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


# -------------------------------------------------------------------------
# Translation Cache Operations (Sarvam Mayura v1)
# -------------------------------------------------------------------------
def get_sarvam_cached_translation(cache_key: str) -> Optional[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT translated_text FROM translation_cache WHERE cache_key = ?",
        (cache_key,)
    )
    row = cursor.fetchone()
    if row:
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE translation_cache SET last_used_at = ?, hit_count = hit_count + 1 WHERE cache_key = ?",
            (now, cache_key)
        )
        conn.commit()
    conn.close()
    return row["translated_text"] if row else None


def set_sarvam_cached_translation(
    cache_key: str,
    provider: str,
    model: str,
    source_language: str,
    target_language: str,
    source_hash: str,
    source_text: str,
    translated_text: str
):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO translation_cache (
            cache_key, provider, model, source_language, target_language,
            source_hash, source_text, translated_text, created_at, last_used_at, hit_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(cache_key) DO UPDATE SET
            translated_text = excluded.translated_text,
            last_used_at = excluded.last_used_at
    """, (
        cache_key, provider, model, source_language, target_language,
        source_hash, source_text, translated_text, now, now
    ))
    conn.commit()
    conn.close()


def clear_sarvam_translation_cache():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM translation_cache")
    conn.commit()
    conn.close()


# -------------------------------------------------------------------------
# Merchant-Scoped AI Response Cache Operations (OpenAI GPT-5.6 Luna)
# -------------------------------------------------------------------------
def get_ai_cached_response(cache_key: str, merchant_id: str) -> Optional[dict]:
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        "SELECT response_payload_json, expires_at FROM ai_response_cache WHERE cache_key = ? AND merchant_id = ?",
        (cache_key, merchant_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    if row["expires_at"] <= now:
        # Expired
        cursor.execute("DELETE FROM ai_response_cache WHERE cache_key = ?", (cache_key,))
        conn.commit()
        conn.close()
        return None

    cursor.execute(
        "UPDATE ai_response_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
        (cache_key,)
    )
    conn.commit()
    conn.close()
    try:
        return json.loads(row["response_payload_json"])
    except Exception:
        return None


def set_ai_cached_response(
    cache_key: str,
    merchant_id: str,
    intent: str,
    query_hash: str,
    financial_data_version: str,
    response_payload: dict,
    ttl_seconds: int = 300,
    max_entries: int = 1000
):
    import json
    from datetime import timedelta
    conn = get_db_connection()
    cursor = conn.cursor()
    now_dt = datetime.now()
    now = now_dt.isoformat()
    expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()

    # Enforce max entries limit (prune oldest when capacity exceeded)
    cursor.execute("SELECT COUNT(*) AS count FROM ai_response_cache")
    count_row = cursor.fetchone()
    if count_row and count_row["count"] >= max_entries:
        cursor.execute("""
            DELETE FROM ai_response_cache WHERE cache_key IN (
                SELECT cache_key FROM ai_response_cache ORDER BY created_at ASC LIMIT 100
            )
        """)

    cursor.execute("""
        INSERT INTO ai_response_cache (
            cache_key, merchant_id, intent, query_hash, financial_data_version,
            response_payload_json, created_at, expires_at, hit_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(cache_key) DO UPDATE SET
            response_payload_json = excluded.response_payload_json,
            expires_at = excluded.expires_at,
            created_at = excluded.created_at
    """, (
        cache_key, merchant_id, intent, query_hash, financial_data_version,
        json.dumps(response_payload), now, expires_at
    ))
    conn.commit()
    conn.close()


def invalidate_merchant_response_cache(merchant_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ai_response_cache WHERE merchant_id = ?", (merchant_id,))
    conn.commit()
    conn.close()


# Ensure tables exist on import
init_db()
