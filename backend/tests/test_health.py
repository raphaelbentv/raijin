from fastapi.testclient import TestClient

from app.main import app
from app.services.health import rollup_status

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "raijin-backend"}


def test_health_rollup_status() -> None:
    assert rollup_status([{"critical": True, "status": "ok"}]) == "ok"
    assert rollup_status([{"critical": False, "status": "down"}]) == "degraded"
    assert rollup_status([{"critical": True, "status": "degraded"}]) == "down"
