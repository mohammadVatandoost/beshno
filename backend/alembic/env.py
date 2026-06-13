"""Alembic migration environment.

Wired to the application so there is one source of truth:
- the database URL comes from app settings (DATABASE_URL / .env), and
- ``target_metadata`` is the app's declarative ``Base.metadata`` (importing
  ``models`` registers every table), so ``--autogenerate`` sees the live models.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import the app's metadata and settings. ``alembic.ini`` sets
# ``prepend_sys_path = .`` so the ``app`` package is importable from backend/.
from app import models  # noqa: F401  (registers all tables on Base.metadata)
from app.config import get_settings
from app.database import Base

config = context.config

# Inject the application's DB URL so we never duplicate it in alembic.ini.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    # disable_existing_loggers must stay False: migrations run in-process during
    # app startup (init_db -> alembic upgrade). The default (True) would tear down
    # uvicorn's and the app's already-configured loggers, silencing all request
    # and application logs for the life of the server.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,  # safe ALTERs on SQLite too
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
