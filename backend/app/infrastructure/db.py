# backend/app/infrastructure/db.py
from __future__ import annotations

import contextlib
import logging
from typing import Generator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool
from dataclasses import dataclass
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class User:
    id: int | None
    first_name: str
    last_name: str


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

# ---------- Engine ----------
# 说明：
# - 使用 QueuePool（默认）并将大小、溢出、pre_ping、echo 等与 settings 对齐
# - 采用 2.0 行为（future=True），避免旧 API 混用
engine = create_engine(
    settings.sqlalchemy_database_uri,
    echo=settings.SQLALCHEMY_ECHO,
    poolclass=QueuePool,
    pool_size=settings.SQLALCHEMY_POOL_SIZE,
    max_overflow=settings.SQLALCHEMY_MAX_OVERFLOW,
    pool_pre_ping=settings.SQLALCHEMY_POOL_PREPING,  # 预检测连接可用性，避免掉线
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

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    future=True,
)


# ---------- FastAPI 依赖注入 ----------
def get_db() -> Generator[Session, None, None]:
    """
    每次请求提供一个独立的数据库会话：
      - 成功：仅关闭（由业务自行决定何时 commit）
      - 异常：回滚并抛出
    用法：
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from app.infrastructure.db import get_db

        @router.get("/suppliers")
        def list_suppliers(db: Session = Depends(get_db)):
            return db.execute(select(Supplier)).scalars().all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("DB session rolled back due to an exception.")
        raise
    finally:
        db.close()


# ---------- Script/Task 场景的上下文管理（可选） ----------
# 在脚本、批处理里很方便：
# with session_scope() as s:
#     s.add(Supplier(name="新供应商"))
# 自动 commit / rollback。

@contextlib.contextmanager
def session_scope() -> Iterator[Session]:
    """
    便于脚本/批处理任务中使用的事务范围工具。
    示例：
        with session_scope() as s:
            s.add(obj)
            ...
    """
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        logger.exception("Transaction rolled back in session_scope.")
        raise
    finally:
        s.close()


# ---------- Alembic 支持 ----------
# 在 alembic/env.py 中可直接：
#     from app.infrastructure.db import engine, target_metadata
#     target_metadata = target_metadata
target_metadata = Base.metadata


# ---------- 运维工具（可选） ----------
# 开发调试时可快速建表。
# 生产上禁止直接用 create_all，要用 Alembic。

def init_db(create_all: bool = False) -> None:
    """
    本地开发调试可用的初始化方法。
    注意：生产环境请使用 Alembic 迁移，不要随意 create_all。
    """
    if create_all:
        logger.warning("Calling Base.metadata.create_all(); prefer Alembic for schema migrations in production.")
        Base.metadata.create_all(bind=engine)

# 热重启/关停时释放连接池资源。
def dispose_engine() -> None:
    """在关停/热更新时可显式释放连接池资源。"""
    engine.dispose()
    logger.info("SQLAlchemy engine disposed.")