# Imagem do backend (FastAPI + LangGraph). Python 3.11 fixado pelo projeto.
FROM python:3.11-slim

# uv (gerenciador de deps) copiado da imagem oficial — evita instalar via pip.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instala dependências primeiro (camada cacheável: só refaz se o lock mudar).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Código da aplicação.
COPY src ./src

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
