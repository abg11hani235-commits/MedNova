from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5433/clinsight"
    embedding_dim: int = 768
    storage_path: str = "storage"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 25
    data_dir: str = "data"

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def storage_dir(self) -> Path:
        p = Path(self.storage_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        return p if p.is_absolute() else ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
