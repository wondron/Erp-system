# backend/app/main.py
from __future__ import annotations

import logging
from typing import Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.core.config import get_settings
from app.adapters.http.routes import api_router
from app.infrastructure.db import init_db, dispose_engine  # 关停时顺便释放连接

logger = logging.getLogger("uvicorn")
settings = get_settings()

def _fmt(v: Iterable | str | None) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, tuple, set)):
        return ", ".join(map(str, v))
    return str(v)

def _log_routes(app: FastAPI) -> None:
    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    logger.info("---- Mounted Routes ---- (%d total)", len(routes))
    for r in routes:
        methods = ",".join(sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}))
        endpoint = f"{r.endpoint.__module__}.{r.endpoint.__name__}"
        tags = ",".join(r.tags or [])
        logger.info("%-10s %-35s tags=[%s] name=%s -> %s",
                    methods, r.path, tags, r.name, endpoint)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    create_all = bool(getattr(settings, "DB_CREATE_ALL", False))  # .env: DB_CREATE_ALL=true（仅开发）
    if create_all:
        try:
            init_db(create_all=True)
            logger.warning("DB init: Base.metadata.create_all() executed (dev only).")
        except Exception:
            logger.exception("DB init failed")

    # 打印 CORS 配置与路由清单
    allow_credentials_effective = settings.ALLOW_CREDENTIALS and settings.ALLOWED_ORIGINS != ["*"]
    logger.info(
        "CORS configured: origins=[%s] | methods=[%s] | headers=[%s] | credentials=%s",
        _fmt(settings.ALLOWED_ORIGINS),
        _fmt(settings.ALLOWED_METHODS),
        _fmt(settings.ALLOWED_HEADERS),
        allow_credentials_effective,
    )
    _log_routes(app)

    yield

    # ---- shutdown ----
    try:
        dispose_engine()
    except Exception:
        logger.exception("dispose_engine failed")

# 创建应用并挂载中间件/路由
app = FastAPI(title="ERP System", lifespan=lifespan)

# CORS（* 时浏览器规范不允许带凭证）
allow_credentials = settings.ALLOW_CREDENTIALS and settings.ALLOWED_ORIGINS != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=allow_credentials,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)

app.include_router(api_router)
