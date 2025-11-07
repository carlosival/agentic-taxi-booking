from logging.config import fileConfig
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
import os
import sys
from alembic import context


def process_revision_directives(context, revision, directives):
    """Called by Alembic when generating migrations."""
    print("🔥 process_revision_directives hook triggered!")  # For debug
    if os.getenv("ALEMBIC_UNSAFE_OK"):
        print("⚠️  Skipping safety checks because ALEMBIC_UNSAFE_OK=1")
        return

    from alembic.operations import MigrationScript
    from db.check_migrations import check_migration_safety

    script = directives[0]
    if isinstance(script, MigrationScript):
        upgrade_ops = script.upgrade_ops
        check_migration_safety(upgrade_ops)

# ──────────────────────────────────────────────
# Load env vars (already passed via Docker or shell)
# ──────────────────────────────────────────────
# Load env variable
db_user = os.getenv("POSTGRES_USER")
db_pass = os.getenv("POSTGRES_PASSWORD")
db_host = os.getenv("POSTGRES_HOST")
db_port = os.getenv("POSTGRES_PORT")
db = os.getenv("POSTGRES_DB")

DATABASE_URL=f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db}"

# ──────────────────────────────────────────────
# Alembic Config and logging
# ──────────────────────────────────────────────
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
# Override Alembic config with env var
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ──────────────────────────────────────────────
# Import metadata for autogenerate support
# ──────────────────────────────────────────────
# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# Import your Base (models metadata)
from db.models import Base  # adjust path to your actual Base
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# ──────────────────────────────────────────────
# Offline migrations (no DB connection)
# ──────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives
    )

    with context.begin_transaction():
        context.run_migrations()


# ──────────────────────────────────────────────
# Online migrations (async engine)
# ──────────────────────────────────────────────
def do_run_migrations(connection):
    """Run migrations inside an async connection (sync context)."""
    context.configure(connection=connection, target_metadata=target_metadata, process_revision_directives=process_revision_directives,
    compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode (asyncpg-compatible)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
