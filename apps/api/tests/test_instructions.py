"""Testes do carregador de prompts (guarda o bug de parents[3] no container)."""

import pytest

from src.instructions import load_instructions


def test_carrega_grill_me():
    txt = load_instructions("grill_me")
    assert "Grill Me" in txt
    assert "Checklist" in txt


def test_instrucao_inexistente_levanta():
    with pytest.raises(FileNotFoundError):
        load_instructions("nao_existe_xyz")
