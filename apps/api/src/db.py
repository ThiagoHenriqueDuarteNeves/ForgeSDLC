"""Camada de acesso ao banco (SQLAlchemy 2.0).

`engine` e `SessionLocal` são o ponto único de conexão; `Base` é a classe
declarativa da qual todos os modelos herdam (fonte de verdade do schema, o
que o Alembic autogera compara contra o banco).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Classe base declarativa de todos os modelos."""


def get_session() -> Iterator[Session]:
    """Dependency do FastAPI: abre uma sessão por request e fecha ao fim."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
