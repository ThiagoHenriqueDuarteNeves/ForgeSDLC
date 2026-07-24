"""Registry de execução dos estágios longos (E3..E6).

Um estágio como a E3 faz ~9 chamadas de LLM gerando 12-20k tokens cada e leva
~10 minutos. Nenhum túnel ou browser mantém a requisição aberta até lá, então
a rota despacha o trabalho em background e responde 202. A UI então consulta
o estado — que precisa morar aqui, no servidor: o cliente perde o dele quando
o gateway devolve 504, quando a página recarrega ou quando se abre a UI em
outro dispositivo.

Em memória e por processo, como o rate limit (`ratelimit.py`). Suficiente
enquanto a API roda em um worker; multi-worker exigiria store compartilhado
(Redis), e aí o `iniciar` viraria um SETNX.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

RODANDO = "rodando"
ERRO = "erro"


@dataclass(frozen=True)
class Execucao:
    status: str  # rodando | erro
    erro: str | None = None


_lock = threading.Lock()
_execucoes: dict[tuple[int, str], Execucao] = {}


def iniciar(run_id: int, estagio: str) -> bool:
    """Marca o estágio como rodando. False se já estava — o disparo é recusado.

    Testar-e-marcar acontece sob a trava: dois cliques simultâneos (duas abas,
    dois dispositivos) não podem virar duas execuções, cada uma queimando
    tokens de verdade.
    """
    with _lock:
        atual = _execucoes.get((run_id, estagio))
        if atual is not None and atual.status == RODANDO:
            return False
        _execucoes[(run_id, estagio)] = Execucao(status=RODANDO)
        return True


def concluir(run_id: int, estagio: str) -> None:
    """Sucesso: esquece o estágio. O estado real passa a ser o do grafo."""
    with _lock:
        _execucoes.pop((run_id, estagio), None)


def falhar(run_id: int, estagio: str, erro: str) -> None:
    """Guarda o erro para a UI mostrar — sem isto o polling ficaria eterno."""
    with _lock:
        _execucoes[(run_id, estagio)] = Execucao(status=ERRO, erro=erro)


def estado(run_id: int, estagio: str) -> Execucao | None:
    """Estado atual, ou None se o estágio não está rodando nem falhou."""
    with _lock:
        return _execucoes.get((run_id, estagio))


def executar(run_id: int, estagio: str, trabalho: Callable[[], object]) -> None:
    """Roda o trabalho e registra o desfecho. Não propaga falha de negócio.

    Ninguém está esperando esta chamada — ela vive numa BackgroundTask. Deixar
    a exceção subir só encheria o log de traceback sem chegar à UI; o caminho
    até o usuário é o estado, consultado pelo polling.
    """
    try:
        trabalho()
    except Exception as e:  # noqa: BLE001 — o desfecho vira estado, não crash.
        logger.exception("estágio %s do run %s falhou", estagio, run_id)
        falhar(run_id, estagio, str(e) or e.__class__.__name__)
    else:
        concluir(run_id, estagio)
