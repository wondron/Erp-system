#!/usr/bin/env bash
set -euo pipefail

############################################
# 基础路径配置
############################################
PROJECT_ROOT="/data/Erp-system/backend"
cd "$PROJECT_ROOT"

# 日志目录（每天一个文件）
LOG_DIR="$PROJECT_ROOT/logs/fastapi"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/uvicorn_$(date +'%Y-%m-%d').log"
PID_FILE="$PROJECT_ROOT/uvicorn.pid"

############################################
# 清理 .env 文件的 BOM / CRLF
############################################
if [[ -f .env ]]; then
  sed -i '1s/^\xEF\xBB\xBF//' .env || true
  sed -i 's/\r$//' .env || true
  if command -v perl >/dev/null 2>&1; then
    perl -pi -e 's/\r\n/\n/g' .env || true
  fi
else
  echo "[WARN] .env 文件未找到，跳过加载。"
fi

############################################
# 加载环境变量
############################################
set -a
# shellcheck disable=SC1090
source <(sed '/^\s*#/d; /^\s*$/d' .env 2>/dev/null || true)
set +a

############################################
# 默认 CORS 兜底设置
############################################
export ALLOWED_ORIGINS='["*"]'
export ALLOWED_METHODS='["GET","POST","PUT","PATCH","DELETE","OPTIONS"]'
export ALLOWED_HEADERS='["*"]'
export ALLOW_CREDENTIALS=false

############################################
# 打印启动信息
############################################
echo "[INFO] ========= FASTAPI 启动信息 ========="
echo "[INFO] APP_NAME        = ${APP_NAME:-}"
echo "[INFO] ENV             = ${ENV:-}"
echo "[INFO] PORT            = ${PORT:-8000}"
echo "[INFO] REDIS_URL       = ${REDIS_URL:-}"
echo "[INFO] 日志文件         = $LOG_FILE"
echo "[INFO] ====================================="

############################################
# 若已有 uvicorn 在运行则先停止
############################################
if [[ -f "$PID_FILE" ]]; then
  OLD_PID=$(cat "$PID_FILE" || true)
  if [[ -n "${OLD_PID}" && -d "/proc/$OLD_PID" ]]; then
    echo "[INFO] 检测到旧进程 PID=$OLD_PID，准备停止..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
fi

############################################
# 启动 Uvicorn
############################################
echo "[INFO] 启动 FastAPI 应用..."
nohup uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --reload \
  >> "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

echo "[OK] FastAPI 已启动"
echo "[OK] PID: $NEW_PID"
echo "[OK] Logs: $LOG_FILE"
