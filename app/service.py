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
        self.generator = QueryGenerator(settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_base_url, settings.examples_csv, settings.rag_top_k, settings.rag_chunk_size, settings.rag_chunk_overlap, settings.rag_database_path)
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
        try:
            connection = self.warehouse.connection()
            with connection.cursor() as cursor:
                cursor.execute(guardrail.sql)
                rows = [dict(zip([column.name for column in cursor.description], row)) for row in cursor.fetchall()]
        except Exception as exc:
                response = QueryResponse(query_id=query_id, question=question, sql=guardrail.sql, explanation=generated.explanation, rows=[], row_count=0, execution_ms=(time.perf_counter() - started) * 1000, confidence=0.0, confidence_breakdown={"sql_validity": 0.0, "alignment": generated.confidence, "result_sanity": 0.0, "schema_coverage": 0.0}, guardrail_warnings=guardrail.warnings, validation_notes=generated.notes + [f"Execution failed: {exc}"], tables=generated.tables, retrieved_examples=generated.retrieved_examples, provider=generated.provider)
        else:
            breakdown = {"sql_validity": 1.0, "alignment": generated.confidence, "result_sanity": 1.0, "schema_coverage": min(1.0, len(generated.tables) / 2)}
            confidence = round(sum(breakdown.values()) / len(breakdown), 2)
            response = QueryResponse(query_id=query_id, question=question, sql=guardrail.sql, explanation=generated.explanation, rows=rows, row_count=len(rows), execution_ms=round((time.perf_counter() - started) * 1000, 2), confidence=confidence, confidence_breakdown=breakdown, guardrail_warnings=guardrail.warnings, validation_notes=generated.notes + ["SQL executed in a read-only application path."], tables=generated.tables, retrieved_examples=generated.retrieved_examples, provider=generated.provider)
        finally:
            if "connection" in locals():
                connection.close()
        self.history.insert(0, response.model_dump())
        self.history = self.history[:50]
        return response

    def schema(self):
        return extract_schema(self.warehouse)

    def record_feedback(self, query_id: str, correct: bool, note: str | None = None, corrected_sql: str | None = None, question: str | None = None, original_sql: str | None = None) -> dict[str, Any]:
        print(f"Feedback save started: query_id={query_id}, corrected_sql_present={bool(corrected_sql and corrected_sql.strip())}")
        for item in self.history:
            if item["query_id"] == query_id:
                question = item["question"]
                original_sql = item["sql"]
                item["feedback"] = {"correct": correct, "note": note}
                break
        if not question or not original_sql:
            print("Feedback save failed: missing question/original SQL context")
            return {"status": "not_found", "original_feedback_saved": False, "correction_saved": False, "message": "Query context was not provided and is no longer in API history."}
        print(f"Saving original feedback for question: {question}")
        self.generator.record_feedback(f"{query_id}-original", question, original_sql, correct, note)
        if corrected_sql and corrected_sql.strip():
            correction_check = check_query(corrected_sql.strip(), self.settings.max_rows)
            if not correction_check.allowed:
                print(f"Corrected SQL rejected: {correction_check.warnings}")
                return {"status": "rejected", "original_feedback_saved": True, "correction_saved": False, "message": correction_check.warnings[0]}
            print(f"Saving corrected SQL to vector database: {correction_check.sql}")
            self.generator.record_feedback(f"{query_id}-correction", question, correction_check.sql, True, "User-provided correction")
            print("Corrected SQL saved successfully")
            return {"status": "recorded", "original_feedback_saved": True, "correction_saved": True, "message": "Corrected SQL was saved to the vector database."}
        return {"status": "recorded", "original_feedback_saved": True, "correction_saved": False, "message": "Feedback was saved."}
