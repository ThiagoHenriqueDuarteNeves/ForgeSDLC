"""Teste da primeira fatia vertical: GET /health."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "forge-api"
    assert "version" in body


def test_get_model_name_roteia_por_no():
    from src.llm import get_model_name

    assert get_model_name("grill") == "deepseek-v4-pro"
    assert get_model_name("consolidador") == "deepseek-v4-flash"


def test_get_model_name_no_desconhecido():
    import pytest

    from src.llm import get_model_name

    with pytest.raises(ValueError):
        get_model_name("inexistente")
