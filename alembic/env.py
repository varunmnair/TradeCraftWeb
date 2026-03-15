from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import DATABASE_URL  # noqa: E402
from db.models import Base  # noqa: E402

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline():
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url", DATABASE_URL))
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = os.getenv("DATABASE_URL", DATABASE_URL)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
