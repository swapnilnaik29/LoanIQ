"""
Conversational AI Agent & Voice Router for LoanIQ.
Exposes Chat, Speech-to-Text, and Text-to-Speech endpoints with graceful fallback.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from backend.schemas.agent import AgentChatRequest, AgentChatResponse
from backend.schemas.voice import STTResponse, TTSRequest, TTSResponse
from backend.services.agent_service import AgentService
from backend.services.voice import speech_to_text, text_to_speech

assistant_router = APIRouter(prefix="/assistant", tags=["Conversational Assistant & Voice"])


@assistant_router.post("/chat", response_model=AgentChatResponse)
def chat(req: AgentChatRequest):
    return AgentService.process_chat(req)


@assistant_router.post("/stt", response_model=STTResponse)
async def handle_stt(
    file: UploadFile = File(...),
    language_code: str = Form("hi-IN")
):
    try:
        content = await file.read()
        return speech_to_text(content, language_code=language_code)
    except Exception as e:
        return STTResponse(text="", language_code=language_code, status="ERROR", message=str(e))


@assistant_router.post("/tts", response_model=TTSResponse)
def handle_tts(req: TTSRequest):
    return text_to_speech(req.text, language_code=req.language_code or "hi-IN")

