"""
Translation Service for LoanIQ.
Integrates Sarvam Mayura v1 (ai_prompt.md Section 2.2 & 8) with persistent SQLite caching,
placeholder shielding, and graceful fallback to English when keys are absent.
"""

from typing import Dict, List, Optional
import httpx
from backend.config import settings
from backend.schemas.translation import TranslateResponse, SupportedLanguagesResponse
from backend.services.cache_service import (
    get_cached_sarvam_translation,
    set_cached_sarvam_translation,
    mask_placeholders,
    unmask_placeholders
)

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native": "English"},
    {"code": "mr", "name": "Marathi", "native": "मराठी"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
]


def normalize_sarvam_lang_code(code: str) -> str:
    """Normalizes language codes to Sarvam format (e.g., 'mr' -> 'mr-IN', 'hi' -> 'hi-IN')."""
    clean = code.strip().lower()
    if clean.startswith("mr"):
        return "mr-IN"
    if clean.startswith("hi"):
        return "hi-IN"
    if clean.startswith("en"):
        return "en-IN"
    return code


def get_supported_languages() -> SupportedLanguagesResponse:
    has_key = bool(settings.SARVAM_API_KEY.strip() or settings.GOOGLE_TRANSLATE_API_KEY.strip())
    return SupportedLanguagesResponse(
        languages=SUPPORTED_LANGUAGES,
        active_key=has_key
    )


def translate_single_text(text: str, source_lang: str = "en", target_lang: str = "mr") -> str:
    """
    Translates a single string using Sarvam Mayura v1 with persistent SQLite caching.
    Safely masks numbers, currency, and IDs.
    """
    if not text or not text.strip():
        return text
    if source_lang == target_lang or (source_lang.startswith("en") and target_lang.startswith("en")):
        return text

    # 1. Check persistent SQLite cache
    cached = get_cached_sarvam_translation(source_lang, target_lang, text)
    if cached is not None:
        return cached

    # 2. Check Sarvam API key
    api_key = settings.SARVAM_API_KEY.strip()
    if not api_key:
        # Check Google Translate fallback if configured
        if settings.GOOGLE_TRANSLATE_API_KEY.strip():
            return _google_translate_single(text, source_lang, target_lang)
        return text

    # 3. Mask placeholders & amounts
    masked_text, mapping = mask_placeholders(text)

    # 4. Call Sarvam Mayura v1
    url = "https://api.sarvam.ai/translate"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "input": masked_text,
        "source_language_code": normalize_sarvam_lang_code(source_lang),
        "target_language_code": normalize_sarvam_lang_code(target_lang),
        "speaker_gender": "Female",
        "mode": "formal",
        "model": settings.SARVAM_TRANSLATE_MODEL or "mayura:v1",
        "enable_preprocessing": True
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                translated = data.get("translated_text", masked_text)
                final_text = unmask_placeholders(translated, mapping)
                # Store in persistent cache
                set_cached_sarvam_translation(source_lang, target_lang, text, final_text)
                return final_text
    except Exception as e:
        print(f"Sarvam translation error: {e}")

    return text


def translate_ui_strings(source_lang: str, target_lang: str, strings: Dict[str, str]) -> TranslateResponse:
    """
    Translates a dictionary of UI string keys. Checks persistent cache for every key,
    calls Mayura v1 only for cache misses, and stores new translations.
    """
    if target_lang == source_lang or target_lang == "en":
        return TranslateResponse(
            source_lang=source_lang,
            target_lang=target_lang,
            translations=strings,
            cached_count=len(strings),
            api_called=False,
            status_message="Source and target languages are identical; returning original strings."
        )

    translations: Dict[str, str] = {}
    uncached_keys: List[str] = []
    cached_count = 0

    # 1. Check persistent SQLite cache first
    for k, original_text in strings.items():
        cached = get_cached_sarvam_translation(source_lang, target_lang, original_text)
        if cached is not None:
            translations[k] = cached
            cached_count += 1
        else:
            uncached_keys.append(k)

    if not uncached_keys:
        return TranslateResponse(
            source_lang=source_lang,
            target_lang=target_lang,
            translations=translations,
            cached_count=cached_count,
            api_called=False,
            status_message="All strings served from persistent SQLite cache."
        )

    # 2. If API key missing, return original English strings for uncached
    api_key = settings.SARVAM_API_KEY.strip()
    if not api_key and not settings.GOOGLE_TRANSLATE_API_KEY.strip():
        for k in uncached_keys:
            translations[k] = strings[k]
        return TranslateResponse(
            source_lang=source_lang,
            target_lang=target_lang,
            translations=translations,
            cached_count=cached_count,
            api_called=False,
            status_message="Translation API key not configured; English UI fallback active."
        )

    # 3. Translate uncached items concurrently using Mayura v1
    api_called = False
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_trans(key: str, orig_text: str):
        return key, translate_single_text(orig_text, source_lang, target_lang)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(lambda k: _fetch_trans(k, strings[k]), uncached_keys)
        for k, trans in results:
            if trans != strings[k]:
                api_called = True
            translations[k] = trans

    return TranslateResponse(
        source_lang=source_lang,
        target_lang=target_lang,
        translations=translations,
        cached_count=cached_count,
        api_called=api_called,
        status_message=f"Translated {len(uncached_keys)} strings via Sarvam Mayura v1 ({cached_count} from cache)."
    )


def _google_translate_single(text: str, source_lang: str, target_lang: str) -> str:
    """Legacy Google Translate fallback if GOOGLE_TRANSLATE_API_KEY is configured."""
    key = settings.GOOGLE_TRANSLATE_API_KEY.strip()
    if not key:
        return text
    try:
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {"key": key}
        payload = {"q": [text], "source": source_lang, "target": target_lang, "format": "text"}
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, params=params, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                trans = data["data"]["translations"][0]["translatedText"]
                set_cached_sarvam_translation(source_lang, target_lang, text, trans)
                return trans
    except Exception:
        pass
    return text
