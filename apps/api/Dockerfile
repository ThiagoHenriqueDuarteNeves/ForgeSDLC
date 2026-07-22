# Imagem do backend (FastAPI + LangGraph). Python 3.11 fixado pelo projeto.
FROM python:3.11-slim

# uv (gerenciador de deps) copiado da imagem oficial — evita instalar via pip.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instala dependências primeiro (camada cacheável: só refaz se o lock mudar).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Pré-baixa o modelo de embeddings (ONNX) para a imagem, evitando download
# no primeiro upload em runtime.
RUN uv run python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')"

# Código da aplicação + migrations (para o container aplicar o schema sozinho).
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

EXPOSE 8000
# Aplica migrations pendentes e sobe a API. O compose garante que o db já
# está healthy antes deste passo (depends_on: service_healthy).
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000"]
