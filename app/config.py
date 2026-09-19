from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://text2sql:text2sql@localhost:5432/text2sql"
    data_dir: str = "data"
    examples_csv: str = "data/spider_text_sql.csv"
    max_rows: int = 1000
    max_scan_rows: int = 100000
    openrouter_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENROUTER_API_KEY", "GEMINI_API_KEY"))
    openrouter_model: str = Field(default="nvidia/nemotron-3-ultra-550b-a55b:free", validation_alias=AliasChoices("OPENROUTER_MODEL", "GEMINI_MODEL"))
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    rag_top_k: int = 5
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_database_path: str = "data/lancedb"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
