"""Teste da primeira fatia vertical: GET /health."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_ok():
    # Requer o Postgres de pé (docker compose up -d db). O /health faz SELECT 1.
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "forge-api"
    assert body["database"] == "up"
    assert "version" in body


def test_cors_libera_origem_da_web_dev():
    # A web em dev pode cair em :3000 ou :3001 (fallback quando 3000 ocupada).
    # Ambas devem ser liberadas pela API — regressão do bug de origem fixa.
    for origin in ("http://localhost:3000", "http://localhost:3001"):
        resp = client.get("/health", headers={"Origin": origin})
        assert resp.headers.get("access-control-allow-origin") == origin


def test_get_model_name_roteia_por_no():
    from src.llm import get_model_name

    assert get_model_name("grill") == "deepseek-v4-pro"
    assert get_model_name("consolidador") == "deepseek-v4-flash"


def test_get_model_name_no_desconhecido():
    import pytest

    from src.llm import get_model_name

    with pytest.raises(ValueError):
        get_model_name("inexistente")
