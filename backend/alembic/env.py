# alembic/env.py
from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import List, Optional

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

# 读取 alembic.ini 的配置对象
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- 项目导入（确保在 backend 目录执行或设置 PYTHONPATH=backend）----
from app.core.config import get_settings
from app.infrastructure.db import Base
from app.infrastructure import orm_models  # noqa: F401  确保模型被导入

settings = get_settings()
target_metadata = Base.metadata


def _get_db_url() -> str:
    """
    统一从应用配置拿异步连接串（推荐：.env 中配置 asyncpg）。
    仅当没有环境变量时，才退回到 alembic.ini 的 sqlalchemy.url。
    """
    url = getattr(settings, "sqlalchemy_database_asyn_uri", None) or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "No DB URL. Please set `sqlalchemy_database_asyn_uri` in .env "
            "(postgresql+asyncpg://user:pass@host:port/db) or sqlalchemy.url in alembic.ini."
        )
    if "asyncpg" not in url:
        raise RuntimeError(f"Alembic async engine expects asyncpg URL, got: {url}")
    # 覆盖 alembic.ini，确保所有命令都用同一个 URL（方案 A 的关键）
    config.set_main_option("sqlalchemy.url", url)
    print("ALEMBIC_DB_URL =", url)  # 调试用，稳定后可注释
    return url


def _collect_schemas() -> List[str]:
    """从模型元数据收集显式 schema（如 'erp_app'）。"""
    return sorted({t.schema for t in target_metadata.tables.values() if t.schema})


def _pick_version_table_schema(schemas: List[str]) -> Optional[str]:
    """alembic_version 放哪：优先 'erp_app'，其次第一个；没有则 None(public)。"""
    if "erp_app" in schemas:
        return "erp_app"
    return schemas[0] if schemas else None


def _process_revision_directives(context, revision, directives):
    """
    autogenerate 时如无变化，跳过生成空迁移。
    """
    if getattr(context.config.cmd_opts, "autogenerate", False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            print("No schema changes detected; skipping empty migration.")


# ---------- Offline ----------
def run_migrations_offline() -> None:
    url = _get_db_url()
    schemas = _collect_schemas()
    version_table_schema = _pick_version_table_schema(schemas)

    # 离线模式无法执行 DDL 创建 schema；只配置元数据与版本表位置
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema=version_table_schema,
        render_as_batch=False,  # 仅 SQLite 需要 True，这里保持 False
        process_revision_directives=_process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------- Online (async) ----------
async def _run_migrations_online() -> None:
    url = _get_db_url()
    schemas = _collect_schemas()
    version_table_schema = _pick_version_table_schema(schemas)

    connectable: AsyncEngine = create_async_engine(url, future=True, poolclass=NullPool)

    async with connectable.connect() as connection:
        # 1) 打印连接信息（这一步会触发 autobegin）
        res = await connection.execute(
            text(
                "SELECT inet_server_addr()::text AS host, "
                "inet_server_port() AS port, current_database() AS db, current_user AS usr"
            )
        )
        print("ALEMBIC connected to:", res.first())

        # 2) 先创建 schema（不再用 connection.begin），然后显式提交
        if schemas:
            for sch in schemas:
                print("Creating schema:", sch)
                await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{sch}"'))
            await connection.commit()  # ★ 关键：提交上面的 DDL（结束隐式事务）

        # 3) 再跑 Alembic 的迁移（Alembic 内部会自己开/关事务）
        def _configure_and_run(sync_conn: Connection):
            context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                include_schemas=True,
                version_table="alembic_version",
                version_table_schema=version_table_schema,
                compare_type=True,
                compare_server_default=True,
                process_revision_directives=_process_revision_directives,
            )
            with context.begin_transaction():
                context.run_migrations()

        await connection.run_sync(_configure_and_run)

    await connectable.dispose()



def run_migrations_online() -> None:
    asyncio.run(_run_migrations_online())


# 入口
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()