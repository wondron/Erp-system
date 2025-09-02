FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 安装 uv（可走国内源；若不需要就用默认）
RUN python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip \
 && python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple uv

# 依赖（只 COPY 清单以利用缓存）
COPY pyproject.toml ./
# 若有锁文件，强烈建议一并复制
# COPY uv.lock ./
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

RUN uv venv /opt/venv && . /opt/venv/bin/activate \
 && uv sync --frozen --no-dev --python 3.11

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 复制源码
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY data ./data
COPY scripts ./scripts

# 纯 Python 健康检查（避免安装 netcat）
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["python","-c","import os,socket,sys; s=socket.create_connection((os.getenv('HEALTH_HOST','127.0.0.1'), int(os.getenv('HEALTH_PORT','8000'))), 2); s.close(); sys.exit(0)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
