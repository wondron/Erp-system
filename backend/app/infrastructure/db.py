# app/infrastructure/db.py
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, AsyncIterator, Iterable
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
    AsyncSession,
)

from app.core.config import get_settings

logger = logging.getLogger("infrastructure.db")
settings = get_settings()

# =========================================================
# Base：全项目唯一 Declarative Base（所有 ORM 都必须继承它）
# =========================================================
class Base(DeclarativeBase):
    pass


# =========================================================
# Async Engine
# 说明：
# - 使用 asyncpg（你在 settings 里应当是 postgresql+asyncpg://...）
# - 打开 pre_ping，规避空闲连接失效
# - pool_size / max_overflow 仅对支持的驱动生效；不支持也不会报错
# - echo 可从配置开关
# =========================================================
logger.info("sqlalchemy_database_asyn_uri: %s", settings.sqlalchemy_database_asyn_uri)

_pool_pre_ping = getattr(
    settings, "SQLALCHEMY_POOL_PREPING",  # 兼容你之前的小拼写
    getattr(settings, "SQLALCHEMY_POOL_PRE_PING", True)
)

engine: AsyncEngine = create_async_engine(
    settings.sqlalchemy_database_asyn_uri,
    echo=getattr(settings, "SQLALCHEMY_ECHO", False),
    json_serializer=lambda o: json.dumps(o, ensure_ascii=False, allow_nan=False),
    pool_pre_ping=_pool_pre_ping,
    pool_size=getattr(settings, "SQLALCHEMY_POOL_SIZE", 5),
    max_overflow=getattr(settings, "SQLALCHEMY_MAX_OVERFLOW", 10),
    future=True,
)


# =========================================================
# Async Session 工厂
# =========================================================
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# =========================================================
# FastAPI 依赖：每请求一个独立会话
# - 成功：自动提交
# - 异常：回滚并抛出
# =========================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("DB session rolled back due to an exception.")
            raise


# =========================================================
# 异步脚本/任务：事务范围管理
# =========================================================
@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            logger.exception("Transaction rolled back in session_scope.")
            raise


# =========================================================
# Alembic 识别的元数据
# =========================================================
target_metadata = Base.metadata


# =========================================================
# 初始化（仅开发场景建议使用 create_all；生产请用 Alembic）
# 关键点：
# 1) 先导入所有 ORM 模块（确保表注册到 Base.metadata）
# 2) 先创建 schema（erp_app / erp_product）
# 3) 再 create_all()
# 4) 可选设置 search_path（便于裸表名查询）
# =========================================================
def import_all_models() -> None:
    """
    在 create_all 之前显式导入所有定义 ORM 模型类的模块，
    确保所有表都注册到 Base.metadata。
    """
    # ⚠️ 按你的真实路径导入。只要覆盖到所有模型定义文件即可。
    import app.infrastructure.orm_models  # noqa: F401


async def _ensure_schemas(conn, schemas: Iterable[str]) -> None:
    for sch in schemas:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{sch}"'))


async def init_db(create_all: bool = False) -> None:
    """
    本地开发调试可用的初始化方法。
    生产环境请使用 Alembic 迁移，不要直接 create_all。
    """
    if not create_all:
        return

    # 1) 导入模型
    import_all_models()

    logger.warning(
        "Calling Base.metadata.create_all() via async engine; prefer Alembic in production."
    )

    # 你当前使用的两个 schema
    schemas = ["erp_app", "erp_product"]

    async with engine.begin() as conn:
        # 2) 先创建 schema
        await _ensure_schemas(conn, schemas)

        # 3) 可选：设置 search_path（方便裸表名 SQL 调试/视图）
        #    注意：若你的 SQL 里写了明确 schema.表名，这个不是必须的。
        try:
            await conn.execute(text('SET search_path TO erp_product, erp_app, public'))
        except Exception:
            # 某些托管环境可能禁止 SET；忽略即可
            logger.debug("SET search_path ignored.")

        # 4) 正式建表（根据已注册的模型元数据）
        await conn.run_sync(Base.metadata.create_all)


# =========================================================
# 关闭引擎（热更新/优雅退出）
# =========================================================
async def dispose_engine() -> None:
    try:
        await engine.dispose()
        logger.info("Async SQLAlchemy engine disposed.")
    except TypeError:
        engine.dispose()
        logger.info("Async SQLAlchemy engine disposed (sync fallback).")
