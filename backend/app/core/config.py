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
    # Preferred: full DSN via DATABASE_URL (e.g., postgresql+psycopg://user:pass@host:5432/db)
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


def setup_logging(level: Optional[str] = None, json_mode: Optional[bool] = None) -> None:
    """
    Configure logging for the app. Call early in startup (e.g., in main.py before app starts).
    """
    settings = get_settings()
    level = (level or settings.LOG_LEVEL).upper()
    json_mode = settings.LOG_JSON if json_mode is None else json_mode

    if json_mode:
        # Minimal JSON-like formatter for log aggregators
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s",'
            '"message":"%(message)s","module":"%(module)s","func":"%(funcName)s","line":%(lineno)d}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": fmt, "datefmt": "%Y-%m-%dT%H:%M:%S"}
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {
            "level": level,
            "handlers": ["default"],
        },
        # Silence overly chatty libs in production-like envs if needed
        "loggers": {
            "uvicorn.error": {"level": level},
            "uvicorn.access": {"level": level},
            "sqlalchemy.engine.Engine": {
                "level": "INFO" if not settings.SQLALCHEMY_ECHO else "DEBUG"
            },
        },
    }

    dictConfig(config)
    logging.getLogger(__name__).debug("Logging configured", extra={"level": level, "json": json_mode})


if __name__ == "__main__":
    #cd 到backend 目录下运行
    # settings = get_settings()
    # print(settings.model_dump_json(indent=2))

    #setup_logging()在main.py中调用一次就行， 后面的两句哪里用哪里调用
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting the application")