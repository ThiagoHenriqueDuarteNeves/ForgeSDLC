"""CORS: os métodos que a web usa precisam passar no preflight.

A web é servida de outra origem (Vercel) e a API atrás de um túnel, então
toda chamada é cross-origin. O browser faz preflight (OPTIONS) antes de um
PATCH e só prossegue se o método constar em Access-Control-Allow-Methods.
`atualizarStatusFatia` usa PATCH; sem ele liberado, marcar uma fatia como
entregue falha em produção e funciona só em localhost (mesma origem).
"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)
ORIGEM = "http://localhost:3000"


def _preflight(metodo: str):
    return client.options(
        "/runs/1/fatias/F-001",
        headers={
            "Origin": ORIGEM,
            "Access-Control-Request-Method": metodo,
        },
    )


def test_preflight_de_patch_e_permitido():
    resp = _preflight("PATCH")
    assert resp.status_code == 200
    permitidos = resp.headers["access-control-allow-methods"]
    assert "PATCH" in permitidos


def test_preflight_de_post_continua_permitido():
    resp = _preflight("POST")
    assert resp.status_code == 200
    assert "POST" in resp.headers["access-control-allow-methods"]
