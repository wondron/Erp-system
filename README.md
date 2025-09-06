## 本地开发
1. requirement 安装
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirement.txt
```

2. 启动数据库与 Redis
使用 docker-compose-dev.yml 启动
```bash
docker compose -f docker-compose.yml up -d
```

3. 初始化数据库（Alembic）
```linux
cd /data/Erp-system/backend
export PYTHONPATH=$(pwd)
export DATABASE_URL_YIBU='postgresql+asyncpg://kumori:123456@localhost:5432/erpdb'
export sqlalchemy_database_asyn_uri=$DATABASE_URL_YIBU
alembic upgrade head
```

``` windows cmd
cd backend
set PYTHONPATH=%cd%
set DATABASE_URL_YIBU=postgresql+asyncpg://kumori:123456@localhost:5432/erpdb
set sqlalchemy_database_asyn_uri=%DATABASE_URL_YIBU%
alembic upgrade head
```


```bash
cd backend
set -a; source .env.dev; set +a   # Windows 可用: setx /M ... 或临时在 PowerShell $env:VAR=...
alembic upgrade head
```
看到 Context impl PostgresqlImpl、Running upgrade ... 就是 OK。


4. 启动 API 和 RQ Worker
两个终端分别执行：
```bash
# 终端2：RQ Worker
cd backend
source .venv/bin/activate
set -a; source .env.dev; set +a
rq worker -u "$REDIS_URL" default


# windows cmd:（不带env参数）
# 终端1：FastAPI
cd /d D:\01-code\Erp-system\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


set "PROJECT_ROOT=D:\01-code\Erp-system\backend"
set "PYTHONPATH=%PROJECT_ROOT%"
set "PYTHONUNBUFFERED=1"
set "REDIS_URL=redis://localhost:6379/0"
cd /d %PROJECT_ROOT%
rq worker -u %REDIS_URL% default --worker-class rq.SimpleWorker -P %PROJECT_ROOT%
```



# 一键启动（服务器）
1. 启动
>docker compose --env-file .env.prod -f docker-compose-prod.yml up -d
2. 查看状态，端口有没有开启
docker compose --env-file .env.prod -f docker-compose-prod.yml ps

正常状态是：
```bash
NAME           IMAGE                COMMAND                   SERVICE    CREATED         STATUS                    PORTS
erp-backend    backend-backend      "sh -c ' alembic upg…"   backend    4 seconds ago   Up Less than a second     0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
erp-postgres   postgres:16-alpine   "docker-entrypoint.s…"   postgres   24 hours ago    Up 15 minutes (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
erp-redis      redis:7-alpine       "docker-entrypoint.s…"   redis      24 hours ago    Up 15 minutes (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
erp-worker     backend-worker       "rq worker -u redis:…"   worker     4 seconds ago   Up 4 seconds
```

3. 查看日志：
docker compose -f docker-compose-prod.yml logs backend
docker compose -f docker-compose-prod.yml logs -f backend worker postgres

4. 常用的命令
| 功能             | 命令                                   |
| -------------- | ------------------------------------ |
| 查看正在运行的容器      | `docker ps`                          |
| 查看所有容器（包括已退出的） | `docker ps -a`                       |
| 启动容器           | `docker start <容器名/ID>`              |
| 停止容器           | `docker stop <容器名/ID>`               |
| 重启容器           | `docker restart <容器名/ID>`            |
| 删除容器           | `docker rm <容器名/ID>`                 |
| 进入容器           | `docker exec -it <容器名> bash`（或 `sh`） |
| 退出容器终端         | `exit` 或 `Ctrl+D`                    |
