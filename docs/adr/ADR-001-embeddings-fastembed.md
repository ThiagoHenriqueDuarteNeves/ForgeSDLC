# ADR-001 — Runtime dos embeddings: fastembed (ONNX)

- **Status:** aceito
- **Data:** 2026-07-22
- **Fase:** 2 (Ingestão / E1)

## Contexto

O PRD e o `docs/FASES.md` especificam embeddings locais com o modelo
`sentence-transformers/all-MiniLM-L6-v2` (384 dimensões), já refletido na
coluna `chunks.embedding` (`Vector(384)`).

A biblioteca `sentence-transformers` traz PyTorch + transformers como
dependências. Isso infla a imagem Docker da API para ~2–3 GB e torna o build
lento — desproporcional para o que precisamos, que é apenas *inferência* de
embeddings em CPU (não treinamento, não fine-tuning).

## Opções

1. **sentence-transformers (como escrito).** Fiel à letra do FASES.md. Custo:
   imagem ~2–3 GB, build lento, PyTorch em produção só para inferência.
2. **fastembed (ONNX).** Roda o **mesmo** modelo `all-MiniLM-L6-v2` via ONNX
   Runtime, sem PyTorch. Imagem ~300 MB, rápido em CPU, mesmas 384 dimensões.

## Decisão

Adotar **fastembed (ONNX)** como runtime de inferência do modelo.

O **modelo não muda**: continua `all-MiniLM-L6-v2`, 384 dimensões, saída
compatível com o schema existente. Muda apenas a biblioteca que executa o
modelo — de PyTorch para ONNX Runtime.

## Consequências

- **Positivas:** imagem da API ~10x menor, build e cold start muito mais
  rápidos, menos superfície de dependência (sem torch/CUDA).
- **Negativas / riscos:** fastembed depende do ONNX Runtime; se no futuro
  precisarmos de um modelo sem export ONNX disponível, revisitamos. O
  modelo ONNX é baixado e cacheado no build da imagem (offline em runtime).
- **Reversível:** trocar de volta para sentence-transformers é mudança de
  `src/embeddings.py` + deps, sem migração de dados (dimensão idêntica).

## Notas

Registrado por exigência do `CLAUDE.md` ("Se o Claude Code propor desvio de
arquitetura, exija um ADR"). Desvio de biblioteca, não de modelo.
