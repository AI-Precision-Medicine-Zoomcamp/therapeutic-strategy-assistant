from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_invalid_target_returns_400():
    response = client.post(
        "/retrieve",
        json={
            "question": "What therapies target an unknown marker?",
            "target_symbol": "UNKNOWN",
            "top_k": 2,
        },
    )

    assert response.status_code == 400
    assert "Unsupported target" in response.json()["detail"]
