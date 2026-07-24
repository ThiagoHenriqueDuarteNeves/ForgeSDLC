"""Registry de execução de estágios longos (E3..E6).

Um estágio como a E3 leva ~10 minutos: nenhum túnel ou browser segura a
requisição aberta até o fim. A rota passa a despachar em background e a UI
consulta o estado — que precisa viver no servidor, porque o cliente perde o
seu quando o 504 chega, recarrega a página ou troca de dispositivo.
"""

import threading

import pytest

from src.execucao import concluir, estado, executar, falhar, iniciar


def test_estagio_nunca_iniciado_nao_tem_estado():
    assert estado(9001, "regras") is None


def test_iniciar_marca_o_estagio_como_rodando():
    iniciar(9002, "regras")
    e = estado(9002, "regras")
    assert e is not None
    assert e.status == "rodando"
    assert e.erro is None


def test_iniciar_devolve_falso_quando_ja_esta_rodando():
    assert iniciar(9003, "regras") is True
    assert iniciar(9003, "regras") is False


def test_estagios_do_mesmo_run_sao_independentes():
    iniciar(9004, "regras")
    assert estado(9004, "historias") is None


def test_runs_diferentes_sao_independentes():
    iniciar(9005, "regras")
    assert estado(9006, "regras") is None


def test_concluir_libera_para_novo_disparo():
    iniciar(9007, "regras")
    concluir(9007, "regras")
    assert estado(9007, "regras") is None
    assert iniciar(9007, "regras") is True


def test_falhar_guarda_a_mensagem_do_erro():
    iniciar(9008, "regras")
    falhar(9008, "regras", "provider fora do ar")
    e = estado(9008, "regras")
    assert e is not None
    assert e.status == "erro"
    assert e.erro == "provider fora do ar"


def test_falha_nao_bloqueia_nova_tentativa():
    iniciar(9009, "regras")
    falhar(9009, "regras", "timeout")
    assert iniciar(9009, "regras") is True
    e = estado(9009, "regras")
    assert e is not None
    assert e.status == "rodando"
    assert e.erro is None


def test_executar_limpa_o_estado_quando_o_trabalho_termina():
    iniciar(9020, "regras")
    executar(9020, "regras", lambda: "pronto")
    assert estado(9020, "regras") is None


def test_executar_registra_o_erro_quando_o_trabalho_estoura():
    iniciar(9021, "regras")

    def explode():
        raise RuntimeError("provider recusou a conexão")

    executar(9021, "regras", explode)

    e = estado(9021, "regras")
    assert e is not None
    assert e.status == "erro"
    assert "provider recusou a conexão" in e.erro


def test_executar_nao_propaga_a_excecao():
    """Roda em background: ninguém está esperando para tratar. Propagar só
    encheria o log de traceback sem chegar à UI — o erro vai para o estado."""
    iniciar(9022, "regras")

    def explode():
        raise RuntimeError("falhou")

    executar(9022, "regras", explode)  # não deve levantar


def test_executar_nao_engole_erro_de_programacao():
    """KeyboardInterrupt/SystemExit não são falha de negócio: passam direto."""
    iniciar(9023, "regras")

    def aborta():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        executar(9023, "regras", aborta)


def test_iniciar_concorrente_deixa_passar_apenas_um():
    """Dois cliques simultâneos (duas abas, dois dispositivos) não podem
    disparar duas execuções — cada uma custaria tokens de verdade."""
    vencedores: list[bool] = []
    trava = threading.Lock()
    barreira = threading.Barrier(8)

    def tentar() -> None:
        barreira.wait()
        ok = iniciar(9010, "regras")
        with trava:
            vencedores.append(ok)

    threads = [threading.Thread(target=tentar) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(vencedores) == 1
