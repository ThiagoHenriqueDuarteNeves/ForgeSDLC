"""Avaliação offline (Fase 7): dataset íntegro + agregação de scores.

Determinístico — não toca LLM nem DeepEval. Só cobre o que roda no CI sem
segredos: a validação do dataset e a lógica de agregação/veredito.
"""

import pytest

from src.eval_harness import DATASET, agregar_scores, dataset_items


def test_dataset_tem_tres_projetos_bem_formados():
    itens = dataset_items()
    assert len(itens) == 3
    for it in itens:
        assert it["nome"]
        assert len(it["descricao"]) > 50
        assert it["regras_esperadas"]  # ao menos uma regra de referência


def test_dataset_items_e_a_mesma_lista():
    assert dataset_items() is DATASET


def test_agregar_aprova_quando_ambas_medias_acima_do_corte():
    resultados = [
        {"nome": "a", "score_rn": 0.8, "score_hist": 0.7},
        {"nome": "b", "score_rn": 0.7, "score_hist": 0.9},
    ]
    resumo = agregar_scores(resultados, threshold=0.6)
    assert resumo["projetos"] == 2
    assert resumo["media_score_rn"] == pytest.approx(0.75)
    assert resumo["aprovado"] is True


def test_agregar_reprova_quando_uma_media_abaixo():
    resultados = [{"nome": "a", "score_rn": 0.9, "score_hist": 0.4}]
    resumo = agregar_scores(resultados, threshold=0.6)
    assert resumo["aprovado"] is False


def test_agregar_reprova_sem_scores():
    resumo = agregar_scores(
        [{"nome": "a", "score_rn": None, "score_hist": None}], threshold=0.6
    )
    assert resumo["aprovado"] is False
    assert resumo["media_score_rn"] == 0.0
