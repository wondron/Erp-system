# backend/alembic/env.py
import os, sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # backend 目录的绝对路径
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.infrastructure.db import target_metadata 
from alembic import context
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 优先取 ALEMBIC_DATABASE_URL；退化到 DATABASE_URL_ASYNC 的“同步版替身”
db_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL")
if db_url:
    print("-----------------")
    print("db url : ", db_url)
    config.set_main_option("sqlalchemy.url", db_url)

def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
