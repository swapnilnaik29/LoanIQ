"""
Persistent Caching Service for LoanIQ.
Implements:
1. Sarvam Translation Cache (ai_prompt.md Section 8) with placeholder shielding.
2. Merchant-scoped OpenAI Response Cache (ai_prompt.md Section 9) with data versioning.
"""

import hashlib
import json
import re
from typing import Optional, Dict, Any, Tuple
from backend.config import settings
from backend.database import (
    get_sarvam_cached_translation,
    set_sarvam_cached_translation,
    clear_sarvam_translation_cache,
    get_ai_cached_response,
    set_ai_cached_response,
    invalidate_merchant_response_cache
)

# -------------------------------------------------------------------------
# Placeholder Masking for Translation
# -------------------------------------------------------------------------
PLACEHOLDER_REGEX = re.compile(r'(\{[a-zA-Z0-9_]+\}|₹\s*[\d,]+(?:\.\d+)?|LP\d{3}|M\d{3}|LA\d{4})')


def mask_placeholders(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Replaces interpolation tokens, product IDs, loan IDs, and amounts with
    untranslatable tokens __TOK_0__, __TOK_1__, etc.
    """
    mapping = {}
    counter = [0]

    def replacer(match):
        token = f"__TOK_{counter[0]}__"
        mapping[token] = match.group(0)
        counter[0] += 1
        return token

    masked_text = PLACEHOLDER_REGEX.sub(replacer, text)
    return masked_text, mapping


def unmask_placeholders(text: str, mapping: Dict[str, str]) -> str:
    """Restores masked interpolation tokens, product IDs, and amounts."""
    result = text
    for token, original in mapping.items():
        result = result.replace(token, original)
        # Also handle potential spacing added by translation models like "__ TOK_0 __"
        spaced_token = token.replace("__", " __ ").strip()
        result = result.replace(spaced_token, original)
    return result


# -------------------------------------------------------------------------
# Sarvam Translation Caching
# -------------------------------------------------------------------------
def make_translation_cache_key(provider: str, model: str, src_lang: str, tgt_lang: str, source_text: str) -> Tuple[str, str]:
    normalized = source_text.strip()
    source_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    raw_key = f"{provider}:{model}:{src_lang}->{tgt_lang}:{source_hash}"
    cache_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return cache_key, source_hash


def get_cached_sarvam_translation(src_lang: str, tgt_lang: str, text: str) -> Optional[str]:
    if not settings.TRANSLATION_CACHE_ENABLED:
        return None
    provider = "sarvam"
    model = settings.SARVAM_TRANSLATE_MODEL or "mayura:v1"
    cache_key, _ = make_translation_cache_key(provider, model, src_lang, tgt_lang, text)
    return get_sarvam_cached_translation(cache_key)


def set_cached_sarvam_translation(src_lang: str, tgt_lang: str, original_text: str, translated_text: str):
    if not settings.TRANSLATION_CACHE_ENABLED:
        return
    provider = "sarvam"
    model = settings.SARVAM_TRANSLATE_MODEL or "mayura:v1"
    cache_key, source_hash = make_translation_cache_key(provider, model, src_lang, tgt_lang, original_text)
    set_sarvam_cached_translation(
        cache_key=cache_key,
        provider=provider,
        model=model,
        source_language=src_lang,
        target_language=tgt_lang,
        source_hash=source_hash,
        source_text=original_text,
        translated_text=translated_text
    )


# -------------------------------------------------------------------------
# Merchant-Scoped Response Caching
# -------------------------------------------------------------------------
def make_response_cache_key(merchant_id: str, intent: str, message: str, data_version: str, locale: str) -> Tuple[str, str]:
    normalized_msg = " ".join(message.strip().lower().split())
    query_hash = hashlib.sha256(normalized_msg.encode("utf-8")).hexdigest()
    raw_key = f"{merchant_id}:{intent}:{query_hash}:{data_version}:{locale}"
    cache_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return cache_key, query_hash


def get_cached_ai_response(merchant_id: str, intent: str, message: str, data_version: str = "v1", locale: str = "en") -> Optional[dict]:
    cache_key, _ = make_response_cache_key(merchant_id, intent, message, data_version, locale)
    return get_ai_cached_response(cache_key, merchant_id)


def set_cached_ai_response(
    merchant_id: str,
    intent: str,
    message: str,
    response_payload: dict,
    data_version: str = "v1",
    locale: str = "en"
):
    # Never cache mutation commands or errors
    if response_payload.get("workflow_type") in ["ERROR", "MUTATION"]:
        return

    cache_key, query_hash = make_response_cache_key(merchant_id, intent, message, data_version, locale)
    ttl = settings.AI_RESPONSE_CACHE_TTL_SECONDS
    max_entries = settings.AI_RESPONSE_CACHE_MAX_ENTRIES

    set_ai_cached_response(
        cache_key=cache_key,
        merchant_id=merchant_id,
        intent=intent,
        query_hash=query_hash,
        financial_data_version=data_version,
        response_payload=response_payload,
        ttl_seconds=ttl,
        max_entries=max_entries
    )


def clear_merchant_cache(merchant_id: str):
    invalidate_merchant_response_cache(merchant_id)

