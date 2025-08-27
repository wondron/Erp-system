"""
Centralized application settings & logging setup.

- Uses pydantic-settings (Pydantic v2) to load environment variables from .env
- Builds SQLAlchemy database URL
- Exposes `get_settings()` for FastAPI dependency injection
- Provides `setup_logging()` to configure logging via dictConfig
"""

from __future__ import annotations

import logging
from functools import lru_cache
from logging.config import dictConfig
from typing import List, Optional
from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- Meta ----
    APP_NAME: str = "ERP System"
    ENV: str = "dev"  # dev | staging | prod
    DEBUG: bool = True
    VERSION: str = "0.1.0"

    # ---- Server ----
    API_V1_PREFIX: str = "/api/v1"  # 路由前缀，防止与前端路由冲突
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---- Database (PostgreSQL + SQLAlchemy) ----
    # Preferred: full DSN via DATABASE_URL (e.g., postgresql+asyncpg://user:pass@host:5432/db)
    DB_CREATE_ALL: bool = False
    DATABASE_URL: Optional[AnyUrl] = None

    # ---- Security ----
    SECRET_KEY: str = "change-me-in-.env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"] 
    ALLOWED_METHODS: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    ALLOWED_HEADERS: List[str] = ["*"]  # 允许所有请求头
    ALLOW_CREDENTIALS: bool = True      # 允许跨域请求

    # ---- SQLAlchemy 配置 ----
    SQLALCHEMY_ECHO: bool = False  # 是否打印 SQL 语句
    SQLALCHEMY_POOL_SIZE: int = 10  # 连接池大小
    SQLALCHEMY_MAX_OVERFLOW: int = 20   # 最大连接数
    SQLALCHEMY_POOL_PREPING: bool = True  # 预连接，防止连接断开

    # ---- Pagination defaults ----
    PAGE_SIZE_DEFAULT: int = 20  # 默认每页条数
    PAGE_SIZE_MAX: int = 200

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR | CRITICAL
    LOG_JSON: bool = False   # if True, enable JSON-like formatter friendly for log collectors

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,  # 区分大小写
        extra="ignore",       # 忽略未定义的配置项
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        return str(self.DATABASE_URL)

    @field_validator("ENV")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        v = v.lower()
        if v not in {"dev", "staging", "prod"}:
            raise ValueError("ENV must be one of: dev | staging | prod")
        return v

    def cors_params(self) -> dict:
        return {
            "allow_origins": self.ALLOWED_ORIGINS,
            "allow_credentials": self.ALLOW_CREDENTIALS,
            "allow_methods": self.ALLOWED_METHODS,
            "allow_headers": self.ALLOWED_HEADERS,
        }


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings loader. Use this in DI:
        settings = Depends(get_settings)
    """
    return Settings()

_LOGGING_CONFIGURED = False

def setup_logging(level: Optional[str] = None, json_mode: Optional[bool] = None, *, force: bool = False) -> None:
    """
    全局初始化日志。多次调用也不会重复添加 handler。
    - level/json_mode 可覆盖 settings
    - force=True 时强制重新配置（会先移除旧 handlers）
    """
    global _LOGGING_CONFIGURED
    settings = get_settings()

    # 已配置且不强制时直接返回（避免重复 handler）
    if _LOGGING_CONFIGURED and not force:
        return

    # 解析级别 / 输出格式
    lvl = (level or settings.LOG_LEVEL).upper()
    use_json = settings.LOG_JSON if json_mode is None else bool(json_mode)

    if use_json:
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s",'
            '"message":"%(message)s","module":"%(module)s","func":"%(funcName)s","line":%(lineno)d}'
        )
        datefmt = "%Y-%m-%dT%H:%M:%S"
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

    # —— 关键：清理现有 root handlers，避免重复输出 ——
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    config = {
        "version": 1,
        "disable_existing_loggers": False,  # 不强行禁掉已存在的 logger（如 uvicorn/sqlalchemy）
        "formatters": {
            "default": {"format": fmt, "datefmt": datefmt}
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",   # 明确到 stdout
            },
        },
        "root": {
            "level": lvl,
            "handlers": ["console"],
        },
        "loggers": {
            # 细化第三方库日志，防止重复与噪声
            "uvicorn": {"level": lvl, "handlers": [], "propagate": True},
            "uvicorn.error": {"level": lvl, "handlers": [], "propagate": True},
            # access 日志默认有独立 handler；把它的 propagate 关掉，避免再冒泡到 root 产生重复
            "uvicorn.access": {"level": lvl, "handlers": [], "propagate": False},
            # SQLAlchemy 建议用 'sqlalchemy.engine'
            "sqlalchemy.engine": {
                "level": "DEBUG" if settings.SQLALCHEMY_ECHO else "INFO",
                "handlers": [],
                "propagate": True,
            },
        },
    }

    dictConfig(config)

    # 标记为已配置
    _LOGGING_CONFIGURED = True

    logging.getLogger(__name__).debug(
        "Logging configured", extra={"level": lvl, "json": use_json}
    )

if __name__ == "__main__":
    #cd 到backend 目录下运行
    # settings = get_settings()
    # print(settings.model_dump_json(indent=2))

    #setup_logging()在main.py中调用一次就行， 后面的两句哪里用哪里调用
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting the application")
    settings = get_settings()
    print(settings.model_dump_json(indent=2))