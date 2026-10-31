from typing import Optional
from pydantic import BaseModel


class STTResponse(BaseModel):
    text: str
    language_code: Optional[str] = "en"
    status: str
    message: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    language_code: Optional[str] = "hi-IN"


class TTSResponse(BaseModel):
    audio_base64: Optional[str] = None
    status: str
    message: Optional[str] = None

