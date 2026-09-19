from fastapi import FastAPI

from app.config import get_settings
from app.models import FeedbackRequest, QueryRequest
from app.service import QueryService

app = FastAPI(title="Guarded Text-to-SQL API", version="1.0.0")
service = QueryService(get_settings())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/query")
def query(request: QueryRequest):
    print(f"API query received: {request.question}")
    return service.run(request.question)


@app.get("/v1/schema")
def schema():
    return {"tables": service.schema()}


@app.get("/v1/history")
def history():
    return {"items": service.history}


@app.post("/v1/feedback")
def feedback(request: FeedbackRequest):
    print(f"API feedback received: query_id={request.query_id}, corrected_sql_present={bool(request.corrected_sql and request.corrected_sql.strip())}")
    return service.record_feedback(request.query_id, request.correct, request.note, request.corrected_sql, request.question, request.original_sql)
