# 项目根目录
PROJECT_ROOT="/data/Erp-system/backend"

# 环境变量
export PYTHONPATH="$PROJECT_ROOT"
export PYTHONUNBUFFERED=1
export REDIS_URL="redis://localhost:6379/0"

# 切换到项目目录
cd "$PROJECT_ROOT"

# 启动 rq worker
nohup rq worker -u "$REDIS_URL" default \
  --worker-class rq.SimpleWorker \
  -P "$PROJECT_ROOT" \
  > rqworker.log 2>&1 &
