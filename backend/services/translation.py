"""
Google Cloud Translation Adapter with SQLite Caching for LoanIQ.
- Caches translations by (source_lang, target_lang, text_key).
- Translates UI string keys only.
- Gracefully degrades to English if GOOGLE_TRANSLATE_API_KEY is not configured.
"""

from typing import Dict, List
import httpx
from backend.config import settings
from backend.database import get_cached_translation, set_cached_translation
from backend.schemas.translation import TranslateResponse, SupportedLanguagesResponse

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native": "English"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    {"code": "mr", "name": "Marathi", "native": "मराठी"},
]


def get_supported_languages() -> SupportedLanguagesResponse:
    return SupportedLanguagesResponse(
        languages=SUPPORTED_LANGUAGES,
        active_key=bool(settings.GOOGLE_TRANSLATE_API_KEY.strip())
    )


def translate_ui_strings(source_lang: str, target_lang: str, strings: Dict[str, str]) -> TranslateResponse:
    if target_lang == source_lang or target_lang == "en":
        return TranslateResponse(
            source_lang=source_lang,
            target_lang=target_lang,
            translations=strings,
            cached_count=len(strings),
            api_called=False,
            status_message="Source and target languages are identical; returning original strings."
        )

    api_key = settings.GOOGLE_TRANSLATE_API_KEY.strip()
    translations: Dict[str, str] = {}
    uncached_keys: List[str] = []
    uncached_texts: List[str] = []
    cached_count = 0

    # 1. Check local SQLite cache first
    for k, original_text in strings.items():
        cached = get_cached_translation(source_lang, target_lang, k)
        if cached is not None:
            translations[k] = cached
            cached_count += 1
        else:
            uncached_keys.append(k)
            uncached_texts.append(original_text)

    if not uncached_keys:
        return TranslateResponse(
            source_lang=source_lang,
            target_lang=target_lang,
            translations=translations,
            cached_count=cached_count,
            api_called=False,
            status_message="All strings served from persistent cache."
        )

    # 2. If API key missing, return original strings for uncached
    if not api_key:
        for k in uncached_keys:
            translations[k] = strings[k]
        return TranslateResponse(
            source_lang=source_lang,
            target_lang=target_lang,
            translations=translations,
            cached_count=cached_count,
            api_called=False,
            status_message="Google Translate API key not configured; English UI fallback active."
        )

    # 3. Call Google Translation API for uncached strings
    api_called = False
    try:
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {"key": api_key}
        payload = {
            "q": uncached_texts,
            "source": source_lang,
            "target": target_lang,
            "format": "text"
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, params=params, json=payload)
            if resp.status_code == 200:
                api_called = True
                data = resp.json()
                translated_items = data.get("data", {}).get("translations", [])
                for idx, item in enumerate(translated_items):
                    t_text = item.get("translatedText", uncached_texts[idx])
                    k = uncached_keys[idx]
                    translations[k] = t_text
                    # Store in cache
                    set_cached_translation(source_lang, target_lang, k, t_text)
                status_msg = f"Successfully translated {len(uncached_keys)} strings via Google Translate API."
            else:
                for k in uncached_keys:
                    translations[k] = strings[k]
                status_msg = f"Google Translate API error (HTTP {resp.status_code}); fallback to English."
    except Exception as e:
        for k in uncached_keys:
            translations[k] = strings[k]
        status_msg = f"Translation network exception: {str(e)}; fallback to English."

    return TranslateResponse(
        source_lang=source_lang,
        target_lang=target_lang,
        translations=translations,
        cached_count=cached_count,
        api_called=api_called,
        status_message=status_msg
    )

