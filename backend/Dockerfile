# backend/Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    DEBIAN_FRONTEND=noninteractive

# ---- 更稳的换源 + 失败自动切换 ----
RUN set -eux; \
    # 1) 写入清华镜像
    printf '%s\n' \
      'deb https://mirrors.tuna.tsinghua.edu.cn/debian bookworm main contrib non-free non-free-firmware' \
      'deb https://mirrors.tuna.tsinghua.edu.cn/debian bookworm-updates main contrib non-free non-free-firmware' \
      'deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware' \
      > /etc/apt/sources.list; \
    # 2) 先用清华源尝试更新，失败则切到阿里云重试
    (apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 update) || ( \
      echo 'TUNA 失败，切换到 Aliyun 再试'; \
      printf '%s\n' \
        'deb https://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware' \
        'deb https://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware' \
        'deb https://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware' \
        > /etc/apt/sources.list; \
      apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=5 update \
    ); \
    # 3) 安装系统依赖
    apt-get install -y --no-install-recommends \
      libpq-dev build-essential gcc curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# ---- Python 依赖 ----
COPY requirement.txt .
RUN pip install --upgrade pip && pip install -r requirement.txt

# ---- 复制项目 ----
COPY . .

# ---- 启动命令 ----
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
