# app/core/logger.py
from __future__ import annotations

import logging
from logging.config import dictConfig
from typing import Optional

_LOGGING_CONFIGURED = False

def _parse_level(value: Optional[str]) -> str:
    if not value:
        return "INFO"
    value = str(value).upper()
    if value in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
        return value
    return "INFO"

def setup_logging(
    level: Optional[str] = None,
    json_mode: Optional[bool] = None,
    *,
    force: bool = False,
    access_propagate: bool = False,
) -> None:
    """
    幂等初始化日志系统。
    - level/json_mode 可覆盖 settings
    - force=True 时强制重新配置（会移除旧 handlers）
    - access_propagate=False 时屏蔽 uvicorn.access 冒泡到 root（避免重复日志）
    """
    global _LOGGING_CONFIGURED

    # 已配置且未要求强制重配则直接返回
    if _LOGGING_CONFIGURED and not force:
        return

    # 延迟 & 容错地读取 settings，避免循环依赖
    settings = None
    try:
        from app.core.config import get_settings  # 延迟导入很关键
        settings = get_settings()
    except Exception:
        settings = None  # 回退到默认

    lvl = _parse_level(level or (getattr(settings, "LOG_LEVEL", None)))
    use_json = bool(json_mode if json_mode is not None else getattr(settings, "LOG_JSON", False))
    echo_sql = bool(getattr(settings, "SQLALCHEMY_ECHO", False))

    # 选择格式
    if use_json:
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s",'
            '"message":"%(message)s","module":"%(module)s","func":"%(funcName)s","line":%(lineno)d}'
        )
        datefmt = "%Y-%m-%dT%H:%M:%S"
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

    # 如需强制重配或首次配置：清理 root 现有 handlers，避免重复输出
    if force or not _LOGGING_CONFIGURED:
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)

    config = {
        "version": 1,
        "disable_existing_loggers": False,  # 不屏蔽第三方 logger
        "formatters": {"default": {"format": fmt, "datefmt": datefmt}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"level": lvl, "handlers": ["console"]},
        "loggers": {
            # 细化第三方库
            "uvicorn": {"level": lvl, "handlers": [], "propagate": True},
            "uvicorn.error": {"level": lvl, "handlers": [], "propagate": True},
            "uvicorn.access": {
                "level": lvl,
                "handlers": [],
                "propagate": bool(access_propagate),  # 默认不冒泡，避免重复
            },
            # SQLAlchemy 建议监听 'sqlalchemy.engine'
            "sqlalchemy.engine": {
                "level": "DEBUG" if echo_sql else "INFO",
                "handlers": [],
                "propagate": True,
            },
        },
    }

    dictConfig(config)
    _LOGGING_CONFIGURED = True
    logging.getLogger("erp.app").debug("Logging configured", extra={"level": lvl, "json": use_json})
