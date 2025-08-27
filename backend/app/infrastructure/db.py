from __future__ import annotations

import logging
from typing import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import get_settings



logger = logging.getLogger('infrastructure.db')
settings = get_settings()

# ---------- Declarative Base ----------
class Base(DeclarativeBase):
    """
    全项目统一的 Declarative Base。
    所有 ORM 模型都应继承它：from app.infrastructure.db import Base
    domain/models.py 里定义的所有模型要继承它
    所有模型元数据会集中在 Base.metadata，Alembic 迁移就能识别
    """
    pass

logger.info("sqlalchemy_database_uri: %s", settings.sqlalchemy_database_uri)

# ⚠️ IMPORTANT:
# settings.sqlalchemy_database_uri 必须使用异步驱动，例如：
# - Postgres:  postgresql+asyncpg://user:pass@host:5432/dbname


# ----------异步 Engine ----------
# 说明：
# - 使用 QueuePool（默认）并将大小、溢出、pre_ping、echo 等与 settings 对齐
# - 采用 2.0 行为（future=True），避免旧 API 混用
engine: AsyncEngine = create_async_engine(
    settings.sqlalchemy_database_uri,
    echo=settings.SQLALCHEMY_ECHO,
    pool_pre_ping=getattr(settings, "SQLALCHEMY_POOL_PREPING", True),
    # 对于某些 async 驱动（如 aiosqlite）不支持 pool_size/max_overflow，可按需删除
    pool_size=getattr(settings, "SQLALCHEMY_POOL_SIZE", 5),
    max_overflow=getattr(settings, "SQLALCHEMY_MAX_OVERFLOW", 10),
    future=True,
)

# ---------- Session factory ----------
# 说明：
# - autocommit=False / autoflush=False：更明确地控制事务与 flush 时机
# - FastAPI 每请求获取一个全新 Session（见 get_db）
# 生成数据库会话（Session）的工厂。
# 每次请求/任务需要数据库时，从这里 new 一个。
# autocommit=False：不自动提交，要手动 commit。
# autoflush=False：避免过早 flush。

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------- FastAPI 依赖注入 ----------
# def get_db() -> Generator[Session, None, None]:
#     """
#     每次请求提供一个独立的数据库会话：
#       - 成功：仅关闭（由业务自行决定何时 commit）
#       - 异常：回滚并抛出
#     用法：
#         from fastapi import Depends
#         from sqlalchemy.orm import Session
#         from app.infrastructure.db import get_db

#         @router.get("/suppliers")
#         def list_suppliers(db: Session = Depends(get_db)):
#             return db.execute(select(Supplier)).scalars().all()
#     """
#     db = SessionLocal()
#     try:
#         yield db
#         db.commit()
#     except Exception:
#         db.rollback()
#         logger.exception("DB session rolled back due to an exception.")
#         raise
#     finally:
#         db.close()
        
# ---------- FastAPI 依赖注入 (async) ----------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    为每次请求提供一个独立的 AsyncSession：
      - 成功：自动提交
      - 异常：回滚并抛出
    用法：
        @router.get("/suppliers")
        async def list_suppliers(db: AsyncSession = Depends(get_db)):
            rows = await db.execute(select(Supplier))
            return rows.scalars().all()
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("DB session rolled back due to an exception.")
            raise


# ---------- Script/Task 场景的上下文管理（可选） ----------
# 在脚本、批处理里很方便：
# with session_scope() as s:
#     s.add(Supplier(name="新供应商"))
# 自动 commit / rollback。

# ---------- Script/Task 场景的异步上下文管理 ----------
@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    异步脚本/任务中的事务范围工具：
        async with session_scope() as s:
            s.add(obj)
    """
    async with AsyncSessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            logger.exception("Transaction rolled back in session_scope.")
            raise


# ---------- Alembic 支持 ----------
# Alembic 通常仍使用同步引擎在 env.py 里做迁移。
# 如果你要用 async create_all（仅开发调试），见下方 init_db。
target_metadata = Base.metadata


# ---------- 运维工具（仅开发） ----------
async def init_db(create_all: bool = False) -> None:
    """
    本地开发调试可用的初始化方法（使用异步引擎）。
    生产环境请使用 Alembic 迁移，不要随意 create_all。
    """
    if not create_all:
        return
    logger.warning("Calling Base.metadata.create_all() via async engine; prefer Alembic in production.")
    async with engine.begin() as conn:
        # 对于异步引擎，需要 run_sync 来调用同步的元数据方法
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """关停/热更新时释放连接池资源。"""
    try:
        await engine.dispose()
        logger.info("Async SQLAlchemy engine disposed.")
    except TypeError:
        # 兼容老版本 SQLAlchemy（dispose 可能是同步）
        engine.dispose()
        logger.info("Async SQLAlchemy engine disposed (sync fallback).")