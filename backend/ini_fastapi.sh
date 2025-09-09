#!/usr/bin/env bash
set -euo pipefail

cd /data/Erp-system/backend

# 一次性把 UTF-8 BOM 与 CRLF 清掉（若本就干净也不会报错）
sed -i '1s/^\xEF\xBB\xBF//' .env || true
sed -i 's/\r$//' .env || true

# 兜底：如果系统有 perl，也再跑一遍保证换行是 LF
if command -v perl >/dev/null 2>&1; then
  perl -pi -e 's/\r\n/\n/g' .env || true
fi

# 加载 .env（忽略空行和注释更稳）
set -a
# shellcheck disable=SC1090
source <(sed '/^\s*#/d; /^\s*$/d' .env)
set +a

# 覆盖/追加 CORS（如无需覆盖可删除这四行）
export ALLOWED_ORIGINS='["*"]'
export ALLOWED_METHODS='["GET","POST","PUT","PATCH","DELETE","OPTIONS"]'
export ALLOWED_HEADERS='["*"]'
export ALLOW_CREDENTIALS=false

# 打印关键信息便于排错
echo "[INFO] APP_NAME=${APP_NAME:-}"
echo "[INFO] ENV=${ENV:-}"
echo "[INFO] PORT=${PORT:-8000}"
echo "[INFO] REDIS_URL=${REDIS_URL:-}"

# 后台启动 uvicorn，记录 PID 与日志
nohup uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --reload \
  > uvicorn.log 2>&1 &

echo $! > uvicorn.pid
echo "[OK] uvicorn started. pid=$(cat uvicorn.pid). Logs: uvicorn.log"
