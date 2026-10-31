"""
Multilingual UI Translation Router for LoanIQ.
"""

from fastapi import APIRouter
from backend.schemas.translation import TranslateRequest, TranslateResponse, SupportedLanguagesResponse
from backend.services.translation import translate_ui_strings, get_supported_languages

translation_router = APIRouter(prefix="/translation", tags=["Translation"])


@translation_router.get("/languages", response_model=SupportedLanguagesResponse)
def list_languages():
    return get_supported_languages()


@translation_router.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    return translate_ui_strings(req.source_lang, req.target_lang, req.strings)

