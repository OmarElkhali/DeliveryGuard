from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DG_", env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://deliveryguard@127.0.0.1:5432/deliveryguard"
    data_dir: Path = Path("data")
    api_key: str = ""
    demo: bool = False
    max_upload_bytes: int = 5 * 1024 * 1024
    max_rows: int = 20000
    api_url: str = "http://127.0.0.1:8000"

    def validate_security(self):
        if not self.demo and len(self.api_key) < 32:
            raise RuntimeError(
                "Set DG_API_KEY to at least 32 characters, or explicitly DG_DEMO=true"
            )
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def settings():
    return Settings()
