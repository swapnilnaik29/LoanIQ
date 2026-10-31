from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5.6-luna"
    OPENAI_REASONING_EFFORT: str = "low"
    SARVAM_API_KEY: str = ""
    SARVAM_STT_MODEL: str = "saaras:v4"
    SARVAM_TRANSLATE_MODEL: str = "mayura:v1"
    SARVAM_TTS_MODEL: str = "bulbul:v4-flash"
    AI_RESPONSE_CACHE_TTL_SECONDS: int = 300
    AI_RESPONSE_CACHE_MAX_ENTRIES: int = 1000
    TRANSLATION_CACHE_ENABLED: bool = True
    GOOGLE_TRANSLATE_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./loaniq.db"
    DATA_DIR: str = "./data"
    ARTIFACTS_DIR: str = "./artifacts"
    FORECAST_SAFETY_BUFFER: float = 5000.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR).resolve()

    @property
    def artifacts_path(self) -> Path:
        return Path(self.ARTIFACTS_DIR).resolve()

    @property
    def db_path(self) -> Path:
        url = self.DATABASE_URL
        if url.startswith("sqlite:///"):
            return Path(url.replace("sqlite:///", "")).resolve()
        return Path("./loaniq.db").resolve()


settings = Settings()

