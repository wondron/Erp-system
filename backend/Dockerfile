# backend/Dockerfile
FROM docker.m.daocloud.io/library/python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    DEBIAN_FRONTEND=noninteractive

# ========== APT：固定 bookworm + 单一国内源 ==========
RUN set -eux; \
    rm -f /etc/apt/sources.list.d/*; \
    \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list; \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list; \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list; \
    \
    apt-get -o Acquire::ForceIPv4=true update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gcc \
        build-essential \
        libpq-dev; \
    rm -rf /var/lib/apt/lists/*

# ========== PIP：固定清华源 ==========
RUN set -eux; \
    python -m pip install --upgrade pip; \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple; \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn; \
    pip config set global.timeout 120

# ---- Python 依赖 ----
COPY requirement.txt /app/requirement.txt
RUN pip install --prefer-binary -r /app/requirement.txt

# ---- 项目代码 ----
COPY . /app

# ---- 启动 ----
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
