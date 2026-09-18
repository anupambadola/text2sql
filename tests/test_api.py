from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_endpoint_returns_confidence_and_rows():
    response = client.post("/v1/query", json={"question": "What is our total revenue?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 0
    assert 0 <= payload["confidence"] <= 1
    assert payload["retrieved_examples"] > 0


def test_schema_endpoint():
    response = client.get("/v1/schema")
    assert response.status_code == 200
    assert response.json()["tables"] == []
