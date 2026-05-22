"""Configuration Alembic pour les migrations asynchrones du service-profile."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.db.base import Base  # noqa: E402 — doit être après fileConfig

target_metadata = Base.metadata


def _get_url() -> str:
    """Lit l'URL depuis la config applicative, jamais depuis alembic.ini."""
    from app.core.config import settings

    return settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


def run_migrations_offline() -> None:
    """Mode offline : génère le SQL brut sans connexion réelle."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    """Exécute les migrations sur une connexion existante."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """Mode online : exécute les migrations sur la base réelle."""
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_url()
    connectable = async_engine_from_config(
        cfg, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Point d'entrée pour le mode online."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
