"""Estágios longos (E3..E6) respondem sem bloquear a requisição.

A E3 leva ~10 minutos; o túnel corta em ~150s e devolve 504. A rota passa a
despachar em background e responder 202, e a UI acompanha pelo GET. Estes
testes cobrem o contrato dessa conversa sem tocar em LLM: o registry é
manipulado direto, e as rotas curto-circuitam antes de chegar ao grafo.
"""

import pytest
from fastapi.testclient import TestClient

from src.execucao import concluir, falhar, iniciar
from src.main import app

client = TestClient(app)

# (estágio no registry, caminho da rota)
ESTAGIOS = [
    ("regras", "/runs/{}/regras"),
    ("historias", "/runs/{}/historias"),
    ("e5", "/runs/{}/e5"),
    ("fatias", "/runs/{}/fatias"),
]


@pytest.fixture
def run_id(request):
    """Um run_id alto e único por teste, e limpeza do registry no fim."""
    rid = 9500 + (abs(hash(request.node.name)) % 400)
    yield rid
    for estagio, _ in ESTAGIOS:
        concluir(rid, estagio)


@pytest.mark.parametrize("estagio,path", ESTAGIOS)
def test_get_informa_rodando_enquanto_o_estagio_trabalha(estagio, path, run_id):
    iniciar(run_id, estagio)
    resp = client.get(path.format(run_id))
    assert resp.status_code == 200
    assert resp.json()["status"] == "rodando"


@pytest.mark.parametrize("estagio,path", ESTAGIOS)
def test_get_informa_o_erro_quando_o_estagio_falha(estagio, path, run_id):
    iniciar(run_id, estagio)
    falhar(run_id, estagio, "provider fora do ar")
    resp = client.get(path.format(run_id))
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["status"] == "erro"
    assert corpo["erro"] == "provider fora do ar"


@pytest.mark.parametrize("estagio,path", ESTAGIOS)
def test_post_recusa_disparo_duplicado(estagio, path, run_id):
    """Sem isto, um 504 no browser reabilita o botão e o segundo clique paga
    outra execução em paralelo — a primeira segue viva no servidor."""
    iniciar(run_id, estagio)
    resp = client.post(path.format(run_id))
    assert resp.status_code == 409
    assert "andamento" in resp.json()["detail"]


@pytest.mark.parametrize("estagio,path", ESTAGIOS)
def test_guarda_reprovada_nao_deixa_o_estagio_marcado(estagio, path):
    """A validação (dossiê ausente, nada aprovado) roda ANTES do despacho e
    é síncrona — é o que preserva o 409 informativo. Se ela reprovar, nada
    pode ficar marcado como rodando: o botão travaria para sempre."""
    from src.execucao import estado

    inexistente = 987654
    resp = client.post(path.format(inexistente))
    assert resp.status_code == 409
    assert estado(inexistente, estagio) is None


@pytest.mark.parametrize("estagio,path", ESTAGIOS)
def test_get_volta_ao_estado_real_depois_de_concluir(estagio, path, run_id):
    """Concluído o trabalho, o registry sai da frente e quem responde é o
    estado do grafo — não pode ficar preso em 'rodando'."""
    iniciar(run_id, estagio)
    concluir(run_id, estagio)
    resp = client.get(path.format(run_id))
    assert resp.status_code == 200
    assert resp.json()["status"] != "rodando"
