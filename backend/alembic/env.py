# backend/alembic/env.py
from __future__ import annotations
import os, sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- 让 "app.*" 可被导入 ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ---- 读取项目配置 / 元数据 ----
from app.core.config import get_settings
from app.infrastructure.db import Base  # Base.metadata 即模型元数据

settings = get_settings()

# Alembic Config 对象，读取 alembic.ini
config = context.config

# 如果 alembic.ini 里没填 sqlalchemy.url，则用 Settings.DATABASE_URL
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)

# 可选：版本表放到业务 schema（默认 public）
VERSION_TABLE = "alembic_version"
VERSION_TABLE_SCHEMA = "erp_app"  # 如不需要放业务 schema，可设为 None

# 读取日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# --- 可选：命名规范，避免 autogenerate 生成多余变更 ---
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
if not target_metadata.naming_convention:
    target_metadata.naming_convention = naming_convention

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
        version_table_schema=VERSION_TABLE_SCHEMA,
        include_schemas=True,  # 让 autogenerate 感知非 public schema
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=VERSION_TABLE,
            version_table_schema=VERSION_TABLE_SCHEMA,
            include_schemas=True,
            compare_type=True,   # 字段类型变化也能检测
            compare_server_default=True,
        )

        with context.begin_transaction():
            # 确保版本表 schema 存在（第一次迁移时很有用）
            if VERSION_TABLE_SCHEMA:
                connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{VERSION_TABLE_SCHEMA}"')
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()