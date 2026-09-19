from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class FeedbackRequest(BaseModel):
    query_id: str
    correct: bool
    note: str | None = None
    corrected_sql: str | None = None
    question: str | None = None
    original_sql: str | None = None


class QueryResponse(BaseModel):
    query_id: str
    question: str
    sql: str
    explanation: str
    rows: list[dict[str, Any]]
    row_count: int
    execution_ms: float
    confidence: float
    confidence_breakdown: dict[str, float]
    guardrail_warnings: list[str] = []
    validation_notes: list[str] = []
    tables: list[str] = []
    blocked: bool = False
    retrieved_examples: int = 0
    provider: str = "LLM"
