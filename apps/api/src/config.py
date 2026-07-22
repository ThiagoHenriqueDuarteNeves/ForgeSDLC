"""Configuração da aplicação, lida de variáveis de ambiente.

Toda configuração de runtime (provider de LLM, tetos de orçamento, banco)
vem daqui — nunca hardcodada. Ver PRD §3.1 e §6.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env local: na raiz do repo. Ao rodar de apps/api, sobe dois níveis.
    # No container as variáveis vêm por ambiente (os.environ tem prioridade).
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), extra="ignore"
    )

    app_name: str = "forge-api"
    app_version: str = "0.1.0"

    # Origens permitidas (CORS) para a web em dev. Lista separada por vírgula
    # via env CORS_ORIGINS. Default cobre as portas comuns do Next dev
    # (3000, e 3001 quando a 3000 está ocupada).
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Provider de LLM (DeepSeek V4, formato OpenAI) — ver PRD §3.1.
    # Preenchido de verdade a partir da Fase 3; declarado aqui para o factory
    # src/llm.py existir desde a fundação.
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    model_grill: str = "deepseek-v4-pro"
    model_extrator: str = "deepseek-v4-pro"
    model_critico: str = "deepseek-v4-pro"
    model_consolidador: str = "deepseek-v4-flash"
    model_refinador: str = "deepseek-v4-pro"
    model_analista: str = "deepseek-v4-pro"
    model_arquiteto: str = "deepseek-v4-pro"
    model_designer: str = "deepseek-v4-pro"
    model_fatiador: str = "deepseek-v4-pro"

    # Tetos duros por run (Fase 8). 0 = sem limite (só para dev).
    max_tokens_per_run: int = 0
    max_usd_per_run: float = 0.0

    # Diretório dos prompts dos agentes (instructions/*.md). Vazio = auto.
    instructions_dir: str = ""

    # Observabilidade (Langfuse) — Fase 3. Vazio = tracing DESLIGADO (no-op):
    # o pipeline roda sem Langfuse. Quando preenchido, toda chamada de agente
    # é traçada (CLAUDE.md: código sem trace não entra). O host aponta para o
    # compose separado (docker-compose.langfuse.yml expõe a UI em :3001).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # Banco — usado a partir da Fase 1b.
    # Default aponta para localhost (execuções no host: alembic, testes).
    # Dentro do container, o docker-compose sobrescreve para host `db`.
    database_url: str = "postgresql+psycopg://forge:forge@localhost:5432/forge"


settings = Settings()
