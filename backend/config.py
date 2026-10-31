from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    SARVAM_API_KEY: str = ""
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

