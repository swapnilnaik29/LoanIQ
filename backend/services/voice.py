"""
Sarvam AI Voice Integration Adapter for LoanIQ.
Integrates Speech-to-Text (STT) and Text-to-Speech (TTS) using official Sarvam endpoints:
- Speech-to-Text: saaras:v4 (transcribes Marathi, Hindi, English while preserving verbatim transcript)
- Text-to-Speech: bulbul:v4-flash (synthesizes natural speech)
Gracefully degrades with informative message when SARVAM_API_KEY is not configured.
"""

from typing import Optional
import httpx
from backend.config import settings
from backend.schemas.voice import STTResponse, TTSResponse


def speech_to_text(audio_bytes: bytes, language_code: str = "mr-IN") -> STTResponse:
    """
    Transcribes spoken merchant audio into text using Sarvam Saaras v4.
    Preserves verbatim spoken transcript in original language.
    """
    api_key = settings.SARVAM_API_KEY.strip()
    if not api_key:
        return STTResponse(
            text="",
            language_code=language_code,
            status="UNAVAILABLE",
            message="Sarvam API key not configured. Audio transcription requires SARVAM_API_KEY."
        )

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": api_key}
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {
        "language_code": language_code,
        "model": settings.SARVAM_STT_MODEL or "saaras:v4"
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, files=files, data=data)
            if resp.status_code == 200:
                result = resp.json()
                transcript = result.get("transcript", "")
                return STTResponse(text=transcript, language_code=language_code, status="SUCCESS")
            else:
                return STTResponse(
                    text="",
                    language_code=language_code,
                    status="ERROR",
                    message=f"Sarvam STT returned HTTP {resp.status_code}: {resp.text}"
                )
    except Exception as e:
        return STTResponse(
            text="",
            language_code=language_code,
            status="ERROR",
            message=f"Sarvam STT connection error: {str(e)}"
        )


# Optimal conversational speakers for Sarvam bulbul:v4-flash
LANGUAGE_SPEAKER_MAP = {
    "mr-IN": "ishita_mr_conversational",
    "hi-IN": "kavya_hi_conversational",
    "en-IN": "neha_en_customer",
    "bn-IN": "roopa_bn_conversational",
    "as-IN": "mouchumi_as_conversational",
}


def get_speaker_for_language(lang_code: str, requested_speaker: Optional[str] = None) -> str:
    """Selects valid speaker for bulbul:v4-flash based on language code."""
    if requested_speaker and requested_speaker not in ["meera", "default"]:
        return requested_speaker
    norm = (lang_code or "").strip()
    if norm in LANGUAGE_SPEAKER_MAP:
        return LANGUAGE_SPEAKER_MAP[norm]
    if norm.startswith("mr"):
        return "ishita_mr_conversational"
    if norm.startswith("hi"):
        return "kavya_hi_conversational"
    if norm.startswith("en"):
        return "neha_en_customer"
    return "ishita_mr_conversational"


def text_to_speech(text: str, language_code: str = "mr-IN", speaker: Optional[str] = None) -> TTSResponse:
    """
    Synthesizes speech from text using Sarvam Bulbul v4 Flash.
    """
    api_key = settings.SARVAM_API_KEY.strip()
    if not api_key:
        return TTSResponse(
            audio_base64=None,
            status="UNAVAILABLE",
            message="Sarvam API key not configured. Audio playback requires SARVAM_API_KEY."
        )

    # Normalize language code to standard format if needed (e.g. "mr" -> "mr-IN", "hi" -> "hi-IN")
    if language_code == "mr":
        language_code = "mr-IN"
    elif language_code == "hi":
        language_code = "hi-IN"
    elif language_code == "en":
        language_code = "en-IN"

    model = settings.SARVAM_TTS_MODEL or "bulbul:v4-flash"
    chosen_speaker = get_speaker_for_language(language_code, speaker) if "v4" in model else (speaker or "meera")

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": [text[:500]],
        "target_language_code": language_code,
        "speaker": chosen_speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": model
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                result = resp.json()
                audios = result.get("audios", [])
                audio_b64 = audios[0] if audios else None
                return TTSResponse(audio_base64=audio_b64, status="SUCCESS")
            else:
                return TTSResponse(
                    audio_base64=None,
                    status="ERROR",
                    message=f"Sarvam TTS returned HTTP {resp.status_code}: {resp.text}"
                )
    except Exception as e:
        return TTSResponse(
            audio_base64=None,
            status="ERROR",
            message=f"Sarvam TTS connection error: {str(e)}"
        )
