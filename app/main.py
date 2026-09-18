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
    for item in service.history:
        if item["query_id"] == request.query_id:
            item["feedback"] = {"correct": request.correct, "note": request.note}
            return {"status": "recorded"}
    return {"status": "not_found"}
