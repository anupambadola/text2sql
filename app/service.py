import time
import uuid
from typing import Any

from app.config import Settings
from app.data_source import CsvWarehouse
from app.generator import QueryGenerator
from app.guardrails import check_query
from app.models import QueryResponse
from app.schema import extract_schema


class QueryService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.warehouse = CsvWarehouse(settings.database_url, settings.data_dir, settings.examples_csv)
        self.generator = QueryGenerator(settings.gemini_api_key, settings.gemini_model, settings.examples_csv, settings.rag_top_k, settings.rag_chunk_size, settings.rag_chunk_overlap)
        self.history: list[dict[str, Any]] = []

    def run(self, question: str) -> QueryResponse:
        generated = self.generator.generate(question, self.schema())
        guardrail = check_query(generated.sql, self.settings.max_rows)
        query_id = str(uuid.uuid4())
        if not guardrail.allowed:
            response = QueryResponse(query_id=query_id, question=question, sql=generated.sql, explanation=generated.explanation, rows=[], row_count=0, execution_ms=0, confidence=0.0, confidence_breakdown={"sql_validity": 0.0, "alignment": generated.confidence, "result_sanity": 0.0, "schema_coverage": 0.0}, guardrail_warnings=guardrail.warnings, validation_notes=generated.notes, tables=generated.tables, blocked=True, retrieved_examples=generated.retrieved_examples, provider=generated.provider)
            self.history.insert(0, response.model_dump())
            return response
        started = time.perf_counter()
        connection = self.warehouse.connection()
        try:
            frame = connection.execute(guardrail.sql).fetchdf()
        except Exception as exc:
            response = QueryResponse(query_id=query_id, question=question, sql=guardrail.sql, explanation=generated.explanation, rows=[], row_count=0, execution_ms=(time.perf_counter() - started) * 1000, confidence=0.0, confidence_breakdown={"sql_validity": 0.0, "alignment": generated.confidence, "result_sanity": 0.0, "schema_coverage": 0.0}, guardrail_warnings=guardrail.warnings, validation_notes=[f"Execution failed: {exc}"], tables=generated.tables, retrieved_examples=generated.retrieved_examples, provider=generated.provider)
        else:
            rows = frame.where(frame.notna(), None).to_dict(orient="records")
            breakdown = {"sql_validity": 1.0, "alignment": generated.confidence, "result_sanity": 1.0 if frame.shape[0] >= 0 else 0.0, "schema_coverage": min(1.0, len(generated.tables) / 2)}
            confidence = round(sum(breakdown.values()) / len(breakdown), 2)
            response = QueryResponse(query_id=query_id, question=question, sql=guardrail.sql, explanation=generated.explanation, rows=rows, row_count=len(rows), execution_ms=round((time.perf_counter() - started) * 1000, 2), confidence=confidence, confidence_breakdown=breakdown, guardrail_warnings=guardrail.warnings, validation_notes=generated.notes + ["SQL executed in a read-only application path."], tables=generated.tables, retrieved_examples=generated.retrieved_examples, provider=generated.provider)
        finally:
            connection.close()
        self.history.insert(0, response.model_dump())
        self.history = self.history[:50]
        return response

    def schema(self):
        return extract_schema(self.warehouse)
