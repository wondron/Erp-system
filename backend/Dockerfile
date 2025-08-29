# ===== 1) Builder：装依赖到独立目录，便于缓存 =====
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 基础系统依赖（某些包需要；尽量精简）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖清单以利用缓存
COPY requirements.txt ./requirements.txt

# 安装依赖到 /opt/venv
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ===== 2) Runtime：拷贝 venv 与源码，使用非 root =====
FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # 重要：让 uvicorn 监听 0.0.0.0
    HOST=0.0.0.0 \
    PORT=8000

# 只装运行期需要的系统库（尽量少）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# 复制项目源码（根据你的结构复制 backend 下的 app、alembic、配置等）
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY .env.example ./.env.example
# 如果有 init 脚本，也一并复制：
# COPY docker/entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

# 创建非 root 用户
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 可选：容器健康检查（依赖 /health 路由）
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# 启动命令：
# - 若需要 alembic 迁移，可以改为先运行升级命令再启动 uvicorn（见下方说明）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
