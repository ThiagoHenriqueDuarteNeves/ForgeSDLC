"""Guarda o routing de modelos: todo nó usado por um agente tem modelo.

Regressão do bug em que `arquiteto`/`designer` (E5) chamavam structured_call
sem estar no _NODE_TO_MODEL → ValueError só em runtime (fora dos testes puros).
"""

import pytest

from src.llm import get_model_name

# Todos os nós que chamam structured_call no pipeline.
NOS = [
    "grill",
    "extrator",
    "consolidador",
    "critico",
    "refinador",
    "analista",
    "arquiteto",
    "designer",
    "fatiador",
]


@pytest.mark.parametrize("no", NOS)
def test_no_tem_modelo_resolvido(no):
    assert get_model_name(no)  # não levanta e não é vazio


def test_no_desconhecido_levanta():
    with pytest.raises(ValueError, match="desconhecido"):
        get_model_name("inexistente")
