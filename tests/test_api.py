from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    body = response.json()
    # "degraded" when the large, gitignored terrain files are not built (fresh clone, CI)
    assert body["status"] == ("ok" if not body["missing_data"] else "degraded")
