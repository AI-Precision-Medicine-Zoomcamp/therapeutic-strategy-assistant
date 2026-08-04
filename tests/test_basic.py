from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.rag_pipeline import RAGResponse, RetrievedChunk
from app.services.evaluation_service import AnswerEvaluation


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "KRAS" in payload["supported_targets"]


def fake_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        id="KRAS_sotorasib_001",
        text="Sotorasib is represented as KRAS evidence in the local test fixture.",
        metadata={
            "target_symbol": "KRAS",
            "drug_name": "sotorasib",
            "source": "test",
            "evidence_strength": "strong",
            "evidence_score": 5,
        },
        distance=0.1,
    )


def fake_rag_response() -> RAGResponse:
    return RAGResponse(
        conversation_id="test-conversation-id",
        question="What evidence supports sotorasib as a KRAS therapy?",
        answer="Retrieved evidence summary: KRAS - sotorasib has supporting evidence.",
        model="test-model",
        used_llm=False,
        target_filter="KRAS",
        retrieved_chunks=[fake_chunk()],
        prompt={"system": "test system", "user": "test user"},
        response_time=0.01,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        estimated_cost_usd=0.0,
        evaluation=AnswerEvaluation(
            relevance="NOT_EVALUATED",
            explanation="Generated answer was skipped in the test fixture.",
            mode="off",
        ),
    )


def test_retrieve_endpoint_returns_target_filtered_chunks(monkeypatch):
    monkeypatch.setattr(routes, "retrieve_chunks", lambda **_: [fake_chunk()])

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
    monkeypatch.setattr(routes, "answer_question", lambda **_: fake_rag_response())
    monkeypatch.setattr(routes, "log_interaction", lambda *args, **kwargs: None)

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
    assert payload["conversation_id"] == "test-conversation-id"
    assert payload["evaluation"]["relevance"] == "NOT_EVALUATED"


def test_feedback_endpoint_saves_rating(monkeypatch):
    saved_feedback = {}

    def fake_log_feedback(**kwargs):
        saved_feedback.update(kwargs)

    monkeypatch.setattr(routes, "log_feedback", fake_log_feedback)

    response = client.post(
        "/feedback",
        json={
            "conversation_id": "test-conversation-id",
            "rating": 1,
            "comment": "Useful answer",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "saved"
    assert payload["rating"] == 1
    assert saved_feedback["conversation_id"] == "test-conversation-id"
    assert saved_feedback["rating"] == 1
