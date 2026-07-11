from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "KRAS" in payload["supported_targets"]


def test_retrieve_endpoint_returns_target_filtered_chunks():
    response = client.post(
        "/retrieve",
        json={
            "question": "What evidence supports sotorasib as a KRAS therapy?",
            "target_symbol": "KRAS",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_filter"] == "KRAS"
    assert len(payload["retrieved_chunks"]) >= 1
    assert payload["retrieved_chunks"][0]["metadata"]["target_symbol"] == "KRAS"


def test_ask_endpoint_returns_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post(
        "/ask",
        json={
            "question": "What evidence supports sotorasib as a KRAS therapy?",
            "target_symbol": "KRAS",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_filter"] == "KRAS"
    assert payload["used_llm"] is False
    assert "Retrieved evidence summary" in payload["answer"]
