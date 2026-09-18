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
    return service.run(request.question)


@app.get("/v1/schema")
def schema():
    return {"tables": service.schema()}


@app.get("/v1/history")
def history():
    return {"items": service.history}


@app.post("/v1/feedback")
def feedback(request: FeedbackRequest):
    return {"status": "recorded" if service.record_feedback(request.query_id, request.correct, request.note) else "not_found"}
