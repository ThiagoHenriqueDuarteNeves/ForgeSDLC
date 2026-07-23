#!/usr/bin/env python
"""Exporta o schema OpenAPI da API para docs/openapi.json.

Uso (a partir de apps/api, onde vive o venv):
    uv run python ../../scripts/export_openapi.py           # grava o arquivo
    uv run python ../../scripts/export_openapi.py --check   # falha se desatualizado

O schema é derivado dos `response_model` das rotas — ele é um reflexo do código,
não uma fonte paralela. Por isso o `--check`: no CI ele denuncia rota nova ou
schema alterado sem o arquivo regenerado, em vez de deixar a doc apodrecer.

Não sobe a aplicação nem toca o banco: importa o `app` e pede o schema.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# Torna `src` importável rodando de qualquer diretório (o venv é o de apps/api).
sys.path.insert(0, str(RAIZ / "apps" / "api"))

from src.main import app  # noqa: E402

DESTINO = RAIZ / "docs" / "openapi.json"


def gerar() -> str:
    """Serializa o OpenAPI com chaves ordenadas — diff estável entre execuções."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="não escreve; sai 1 se docs/openapi.json estiver diferente do código",
    )
    args = parser.parse_args()

    schema = gerar()
    rel = DESTINO.relative_to(RAIZ)

    if args.check:
        if not DESTINO.exists():
            print(f"FALHA: {rel} não existe. Rode sem --check.")
            return 1
        if DESTINO.read_text(encoding="utf-8") != schema:
            print(f"FALHA: {rel} está desatualizado. Rode sem --check.")
            return 1
        print(f"OK: {rel} bate com o código.")
        return 0

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(schema, encoding="utf-8")

    doc = json.loads(schema)
    print(f"{rel}: {len(doc['paths'])} rotas, {len(doc['components']['schemas'])} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
