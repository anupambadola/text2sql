from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "duckdb:///data/warehouse.duckdb"
    data_dir: str = "data"
    examples_csv: str = "data/spider_text_sql.csv"
    max_rows: int = 1000
    max_scan_rows: int = 100000
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    rag_top_k: int = 5
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
