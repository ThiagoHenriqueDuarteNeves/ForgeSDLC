#!/usr/bin/env python
"""Avaliação offline do pipeline Forge — Fase 7 / PRD §7.

Uso (a partir de apps/api, onde vive o venv):
    uv run python ../../scripts/eval.py            # dry-run: valida o dataset
    uv run python ../../scripts/eval.py --push     # empurra o dataset ao Langfuse
    uv run python ../../scripts/eval.py --full      # roda os agentes + DeepEval

Modos:
- dry-run (default): carrega e valida o dataset, imprime o plano e sai 0. É o
  que o job noturno do CI roda sem segredos (sempre verde).
- --full: exige LLM_API_KEY (e o grupo `eval` instalado). Roda E3+E4 sobre cada
  projeto-exemplo e pontua RNs e histórias com DeepEval. Sem a chave, avisa e
  sai 0 (o nightly só avalia de verdade quando os segredos estão presentes).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Torna `src` importável rodando de qualquer diretório (o venv é o de apps/api).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from src.config import settings  # noqa: E402
from src.eval_harness import (  # noqa: E402
    agregar_scores,
    avaliar_projeto,
    dataset_items,
    push_langfuse_dataset,
)
from src.observability import configure_logging, get_logger  # noqa: E402

log = get_logger("eval.cli")


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Avaliação offline do Forge SDLC")
    parser.add_argument("--full", action="store_true", help="roda agentes + DeepEval")
    parser.add_argument("--push", action="store_true", help="empurra o dataset ao Langfuse")
    parser.add_argument("--threshold", type=float, default=0.6, help="corte de qualidade")
    parser.add_argument("--out", type=str, default="", help="arquivo JSON do relatório")
    args = parser.parse_args()

    itens = dataset_items()
    print(f"Dataset: {len(itens)} projetos-exemplo")
    for it in itens:
        print(f"  · {it['nome']} — {len(it['regras_esperadas'])} regras esperadas")

    if args.push:
        n = push_langfuse_dataset()
        print(f"Langfuse: {n} itens empurrados" if n else "Langfuse: não configurado (pulado)")

    if not args.full:
        print("dry-run: dataset OK. Use --full (com LLM_API_KEY) para avaliar.")
        return 0

    if not settings.llm_api_key:
        print("--full pedido, mas LLM_API_KEY vazio → avaliação pulada (sai 0).")
        return 0

    resultados = [avaliar_projeto(it, threshold=args.threshold) for it in itens]
    resumo = agregar_scores(resultados, threshold=args.threshold)
    relatorio = {"resultados": resultados, "resumo": resumo}

    print("\n=== Relatório de avaliação ===")
    print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(relatorio, indent=2, ensure_ascii=False))
        print(f"relatório salvo em {args.out}")

    print(
        f"\nMédia RN={resumo['media_score_rn']:.2f} "
        f"Histórias={resumo['media_score_hist']:.2f} "
        f"(corte {resumo['threshold']}) → "
        + ("APROVADO" if resumo["aprovado"] else "ABAIXO DO CORTE")
    )
    # O nightly é informativo: não derruba o CI por score baixo (sempre 0).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
