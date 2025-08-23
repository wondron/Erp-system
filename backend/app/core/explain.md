配置、日志、中间件。


core 目录职责（FastAPI 应用的“内核配置”）：
1) 配置集中化
   - 使用 pydantic-settings 读取 .env（区分 dev/staging/prod）
   - 统一暴露 Settings 对象，提供 API 前缀、CORS、分页、密钥等常量
   - 负责构建 SQLAlchemy 的数据库连接串（优先 DATABASE_URL，其次拼接 PG_*）

2) 日志初始化
   - setup_logging() 在应用启动时调用
   - 支持普通文本格式与“类 JSON”格式（便于日志采集）
   - 根据 LOG_LEVEL 动态控制日志级别

3) 依赖注入
   - get_settings() 通过 lru_cache 缓存，FastAPI 路由/启动事件中以 Depends 注入

使用示例（main.py 摘要）：
------------------------------------------------------------
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings, setup_logging

setup_logging()  # 放在最前，尽早配置日志
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    **settings.cors_params()
)
# include_router(...) 见 adapters/http/routes.py
------------------------------------------------------------

.env 关键变量建议：
------------------------------------------------------------
ENV=dev
DEBUG=true
SECRET_KEY=please-change-me

# 方式一：完整 DSN（推荐）
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/erp

# 方式二：分字段拼接（当未设置 DATABASE_URL 时生效）
PG_HOST=db
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=postgres
PG_DATABASE=erp

LOG_LEVEL=INFO
LOG_JSON=false
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
------------------------------------------------------------