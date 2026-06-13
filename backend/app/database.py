"""SQLAlchemy engine, session factory and declarative base."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# SQLite (used as a zero-dependency local fallback) needs check_same_thread off
# because the pipeline runs in a background thread.
connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Bring the database schema up to date.

    For the real (e.g. PostgreSQL) database we run Alembic migrations so schema
    changes are versioned and applied incrementally. For SQLite — the
    zero-dependency local/test fallback, always a throwaway fresh file — we just
    create tables directly, which keeps tests fast and dependency-free.
    """
    from . import models  # noqa: F401  (ensure models are registered)

    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        return

    _run_migrations()


def _run_migrations() -> None:
    """Apply Alembic migrations up to head against the configured database."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")
