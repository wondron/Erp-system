#!/usr/bin/env bash
set -euo pipefail

############################################
# 基本配置（可按需覆盖为环境变量）
############################################
PROJECT_ROOT="${PROJECT_ROOT:-/data/Erp-system/backend}"
export PYTHONPATH="$PROJECT_ROOT"
export PYTHONUNBUFFERED=1

# ✅ 强制 IPv4，若 Redis 有密码：REDIS_URL="redis://:PWD@127.0.0.1:6379/0"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

# 可选：单独指定主机/端口/密码用于健康检查（不写也行，默认从上面推断）
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# RQ 队列与 Worker 类
RQ_QUEUES="${RQ_QUEUES:-default}"
RQ_WORKER_CLASS="${RQ_WORKER_CLASS:-rq.SimpleWorker}"

############################################
# 日志 & PID
############################################
LOG_DIR="$PROJECT_ROOT/logs/rqworkers"
mkdir -p "$LOG_DIR"

log_file() { printf "%s/rqworker_%s.log" "$LOG_DIR" "$(date +'%Y-%m-%d')"; }
PID_FILE="$PROJECT_ROOT/rqworker.pid"
MANAGER_PID_FILE="$PROJECT_ROOT/rqworker_manager.pid"
STOP_FILE="$PROJECT_ROOT/rqworker.stop"
NOHUP_OUT="$LOG_DIR/nohup.out"

############################################
# 信号处理（优雅退出）
############################################
STOP_FLAG=0
graceful_stop() {
  STOP_FLAG=1
  echo "[INFO] 捕获停止信号，准备优雅退出..."
  if [[ -f "$PID_FILE" ]]; then
    CHILD_PID="$(cat "$PID_FILE" || true)"
    if [[ -n "${CHILD_PID:-}" && -d "/proc/$CHILD_PID" ]]; then
      echo "[INFO] 终止 RQ 子进程 PID=$CHILD_PID ..."
      kill "$CHILD_PID" 2>/dev/null || true
    fi
  fi
}
trap graceful_stop INT TERM

############################################
# 健康检查：必须是 master 且可写
############################################
health_check() {
  local pw_args=()
  [[ -n "$REDIS_PASSWORD" ]] && pw_args+=( -a "$REDIS_PASSWORD" )

  echo "[INFO] 检查 Redis($REDIS_HOST:$REDIS_PORT) 主从与可写性..."
  docker run --rm --network host redis:7-alpine \
    sh -lc "redis-cli ${pw_args[*]} -h $REDIS_HOST -p $REDIS_PORT INFO replication | grep -q 'role:master'" \
    || { echo "[ERR] 目标 Redis 不是 master，拒绝启动。"; return 1; }

  docker run --rm --network host redis:7-alpine \
    redis-cli "${pw_args[@]}" -h "$REDIS_HOST" -p "$REDIS_PORT" SET rq:bootcheck ok >/dev/null \
    || { echo "[ERR] Redis 写入失败（可能只读/ACL限制），拒绝启动。"; return 1; }

  return 0
}

############################################
# 启动一次 RQ Worker（前台），由管理循环重启
############################################
start_once() {
  cd "$PROJECT_ROOT"
  local LOG_FILE; LOG_FILE="$(log_file)"
  echo "[INFO] 启动 RQ worker -> 日志: $LOG_FILE"
  echo "[INFO] REDIS_URL=$REDIS_URL | QUEUES=$RQ_QUEUES | CLASS=$RQ_WORKER_CLASS"

  rq worker -u "$REDIS_URL" $RQ_QUEUES \
    --worker-class "$RQ_WORKER_CLASS" \
    -P "$PROJECT_ROOT" \
    >> "$LOG_FILE" 2>&1 &
  local child_pid=$!
  echo "$child_pid" > "$PID_FILE"
  echo "[INFO] RQ PID=$child_pid 已启动"
  wait "$child_pid"
  local exit_code=$?
  echo "[WARN] RQ 进程退出，code=$exit_code"
  rm -f "$PID_FILE"
  return "$exit_code"
}

############################################
# 管理循环：异常退出自动重启（指数退避≤60s）
############################################
run_manager() {
  echo $$ > "$MANAGER_PID_FILE"
  echo "[INFO] RQ 管理器 PID=$$ 启动。Stop 文件: $STOP_FILE"

  health_check

  FAILS=0
  while :; do
    [[ -f "$STOP_FILE" || $STOP_FLAG -eq 1 ]] && { echo "[INFO] 检测到停止请求，退出管理循环。"; break; }

    LOG_FILE="$(log_file)"
    touch "$LOG_FILE"

    start_once
    EXIT_CODE=$?

    [[ $STOP_FLAG -eq 1 || -f "$STOP_FILE" ]] && { echo "[INFO] 已停止，不再重启。"; break; }

    if ! health_check; then
      echo "[WARN] 健康检查失败，待会再尝试重启。"
    fi

    ((FAILS++)) || true
    BACKOFF=$(( 2 ** FAILS ))
    (( BACKOFF > 60 )) && BACKOFF=60
    echo "[INFO] $BACKOFF 秒后重启（累计失败 $FAILS 次）..."
    sleep "$BACKOFF"
  done

  echo "[INFO] RQ 管理器退出。"
  rm -f "$MANAGER_PID_FILE"
}

############################################
# 支持 nohup 启动（后台）
############################################
case "${1:-}" in
  start)
    if [[ "${2:-}" == "--force" ]]; then
      echo "[INFO] 强制重启：先尝试停止旧的管理器..."
      touch "$STOP_FILE" || true
      if [[ -f "$MANAGER_PID_FILE" ]]; then
        kill "$(cat "$MANAGER_PID_FILE")" 2>/dev/null || true
        sleep 2
      fi
      rm -f "$MANAGER_PID_FILE" "$STOP_FILE"
    fi
    if [[ -f "$MANAGER_PID_FILE" ]]; then
      pid="$(cat "$MANAGER_PID_FILE" 2>/dev/null || true)"
      if [[ -n "$pid" && -d "/proc/$pid" ]]; then
        # 进一步校验确实是本脚本
        if tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "bash .*ini_rqworker.sh run"; then
          echo "[WARN] 管理器已在运行中（PID=$pid）。"
          exit 0
        else
          echo "[WARN] 检测到陈旧 PID 文件，清理后重启。"
          rm -f "$MANAGER_PID_FILE"
        fi
      else
        echo "[WARN] 检测到陈旧 PID 文件，清理后重启。"
        rm -f "$MANAGER_PID_FILE"
      fi
    fi
    echo "[INFO] 后台启动 rqworker 管理器..."
    rm -f "$STOP_FILE"
    nohup bash "$0" run > "$NOHUP_OUT" 2>&1 &
    echo "[INFO] 已在后台运行，日志输出到 $NOHUP_OUT"
    ;;
  restart)
    echo "[INFO] 重启 rqworker ..."
    bash "$0" stop || true
    sleep 2
    bash "$0" start
    ;;
  run)
    run_manager
    ;;
  stop)
    echo "[INFO] 请求停止 rqworker..."
    touch "$STOP_FILE"
    if [[ -f "$MANAGER_PID_FILE" ]]; then
      kill "$(cat "$MANAGER_PID_FILE")" 2>/dev/null || true
    fi
    ;;
  status)
    if [[ -f "$MANAGER_PID_FILE" ]]; then
      pid="$(cat "$MANAGER_PID_FILE" 2>/dev/null || true)"
      if [[ -n "$pid" && -d "/proc/$pid" ]] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "bash .*ini_rqworker.sh run"; then
        echo "[OK] rqworker 正在运行（PID=$pid）"
        exit 0
      fi
    fi
    echo "[STOPPED] rqworker 未运行"
    ;;
  *)
    echo "用法: $0 {start|start --force|stop|restart|status}"
    ;;
esac

