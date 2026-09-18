import json
import re
from dataclasses import dataclass
from typing import Any

from app.rag import ChromaRAGRetriever


@dataclass
class GeneratedQuery:
    sql: str
    explanation: str
    tables: list[str]
    confidence: float
    notes: list[str]
    retrieved_examples: int = 0
    provider: str = "fallback"


class QueryGenerator:
    """Gemini structured generation grounded by Chroma-retrieved examples."""

    def __init__(self, api_key: str | None, model: str, examples_csv: str, top_k: int = 5, chunk_size: int = 800, chunk_overlap: int = 120):
        self.model = model
        self.top_k = top_k
        self.retriever = ChromaRAGRetriever(examples_csv, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.client: Any = None
        if api_key:
            from google import genai

            self.client = genai.Client(api_key=api_key)

    def generate(self, question: str, schema: list[dict[str, Any]]) -> GeneratedQuery:
        examples = self.retriever.retrieve(question, self.top_k)
        if self.client:
            return self._generate_with_gemini(question, schema, examples)
        return self._fallback(question, examples)

    def _generate_with_gemini(self, question: str, schema: list[dict[str, Any]], examples: list[dict[str, Any]]):
        from google.genai import types

        few_shots = "\n".join(
            f"Question: {item['text_query']}\nSQL: {item['sql_command']}" for item in examples
        )
        prompt = f"""You are an enterprise Text-to-SQL compiler. Generate only read-only SQL.
Database schema: {json.dumps(schema, default=str)}
Retrieved approved examples:
{few_shots}
User question: {question}

Return JSON with exactly these keys: sql, explanation, tables, confidence, notes.
confidence must be a number between 0 and 1. Use only tables and columns in the schema.
"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        payload = json.loads(response.text)
        return GeneratedQuery(
            sql=payload["sql"], explanation=payload["explanation"], tables=payload.get("tables", []),
            confidence=float(payload.get("confidence", 0.5)), notes=payload.get("notes", []),
            retrieved_examples=len(examples), provider="gemini",
        )

    def _fallback(self, question: str, examples: list[dict[str, Any]]) -> GeneratedQuery:
        if examples:
            sql = examples[0]["sql_command"]
            tables = sorted(set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", sql, re.IGNORECASE)))
            return GeneratedQuery(sql, "Used the highest-ranked approved CSV example because Gemini is not configured.", tables, 0.55, ["No Gemini key was configured; RAG fallback generation was used."], len(examples))
        return GeneratedQuery("SELECT 1", "No approved examples were found.", [], 0.05, ["Add a text_query,sql_command CSV and configure Gemini."], 0)
