from typing import Dict, List
from pydantic import BaseModel


class TranslateRequest(BaseModel):
    source_lang: str = "en"
    target_lang: str
    strings: Dict[str, str]


class TranslateResponse(BaseModel):
    source_lang: str
    target_lang: str
    translations: Dict[str, str]
    cached_count: int
    api_called: bool
    status_message: str


class SupportedLanguagesResponse(BaseModel):
    languages: List[Dict[str, str]]
    active_key: bool

