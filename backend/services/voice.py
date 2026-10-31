"""
Sarvam AI Voice Integration Adapter for LoanIQ.
Integrates Speech-to-Text (STT) and Text-to-Speech (TTS) using official Sarvam endpoints.
Gracefully degrades with informative message when SARVAM_API_KEY is not configured.
"""

from typing import Optional
import httpx
from backend.config import settings
from backend.schemas.voice import STTResponse, TTSResponse


def speech_to_text(audio_bytes: bytes, language_code: str = "hi-IN") -> STTResponse:
    api_key = settings.SARVAM_API_KEY.strip()
    if not api_key:
        return STTResponse(
            text="",
            language_code=language_code,
            status="UNAVAILABLE",
            message="Sarvam API key not configured. Please use text input or configure SARVAM_API_KEY."
        )

    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": api_key}
    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {"language_code": language_code, "model": "saaras:v1"}

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


def text_to_speech(text: str, language_code: str = "hi-IN") -> TTSResponse:
    api_key = settings.SARVAM_API_KEY.strip()
    if not api_key:
        return TTSResponse(
            audio_base64=None,
            status="UNAVAILABLE",
            message="Sarvam API key not configured. Audio playback unavailable."
        )

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": [text[:500]],
        "target_language_code": language_code,
        "speaker": "meera",
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v1"
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

