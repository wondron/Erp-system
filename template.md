啵啵啵，刚刚你帮我搭了一个最小可运行的骨架，后端 FastAPI：模块化结构，包含MasterData / Purchasing / Inventory 三个路由示例。前端 Vue 3：基础路由、Pinia 状态管理、一个采购单创建表单的 demo。 数据库是（PostgreSQL + SQLAlchemy）的持久化示例


1. schema 的基本概念
schema 是数据库里的命名空间（类似文件夹/目录）。
一个数据库（database）可以包含多个 schema，每个 schema 里可以有表（table）、视图、函数、序列等对象。
不同 schema 里的对象可以同名，但不会冲突，因为它们有“命名空间”。

2. 和数据库 (database) 的关系
database：相当于一个“库房”
schema：库房里的“分区”
table：分区里的“货架/表格”
所以你现在有一个数据库 erp，里面有多个 schema：
erp_app（你的业务对象放在这里）
public（默认的公共 schema）
information_schema（系统提供的元数据）

1. pg_ctl start   cmd中启动postgreSQL
2. psql -U postgres -p 5433    输入账户
3. 输入  123456   密码




## postgresql 里面创建数据库：
CREATE DATABASE erp;

\l   -- 列出所有数据库
\c erp   --切换到 erp 的数据库
erp=# \i 'D:/python/Erp-system/backend/app/infrastructure/init_in_db.sql'  数据库内初始化。


## 启动fastapi服务
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000



## 检查数据库
pg_ctl start    #后续如果后台启动了就不用这样了
cd backend
set PYTHONPATH=%cd%
set DATABASE_URL=postgresql+asyncpg://postgres:123456@localhost:5433/erp   #代码生成是：postgresql+asyncpg://postgres:postgres@db:5432/erp， db是Docker Compose 的服务名。我们先用localhost也就是本地的意思
python scripts/inspect_db.py


## 前端代码生成
1.  创建一个新项目，会生成一个fronted文件夹
npm create vite@latest frontend

2. 选择 vue 和 TypeScript(ts文件)

  cd frontend
  npm install
  npm run dev

3. 安装依赖项
npm install vue-router pinia axios

4. 在 frontend 执行这样 VS Code / TS 就知道 path 是 Node 内置模块了。
npm install -D @types/node

## 启动开发服务器
```bash
cd D:\01-code\Erp-system\frontend
npm run dev
```


## 测试环境，正式环境的切换：
export ENV=prod
export DEBUG=false
export DATABASE_URL=postgresql://prod_user:prod_pwd@prod-server/proddb
在 Docker / k8s / Linux 服务器 上，通常不会放 .env 文件，而是用系统变量注入：



## 启动redis
redis-server
uvicorn app.main:app --reload --port 8000       #启动 fastapi
rq worker -u redis://localhost:6379/0 default   #启动 Worker（RQ）

docker pull redis:7-alpine # 把数据持久化到本地，避免容器删了数据没了
mkdir D:\01-code\Erp-system\redis-data
docker run -d --name erp-redis -p 6379:6379 -v D:\01-code\Erp-system\redis-data:/data --restart unless-stopped redis:7-alpine
docker ps             # 看到 erp-redis 在运行
docker logs erp-redis # 看启动日志

开一个新的 bash，在 backend 目录：
``` bash
set "PYTHONPATH=%cd%"     # 只在当前窗口设置 PYTHONPATH（让 rq 能 import 到 app.*）
# 启动 RQ worker，连接本机 Redis 6379，消费 default 队列
python -m rq.cli worker --url redis://localhost:6379/0 default
```

### 另开一个终端（同样在 backend 目录）：
uvicorn app.main:app --reload





## docker builder
cd Erp-system/backend
docker build -t erp-backend:latest .


# 最小启动方式
cd Erp-system/backend
set "PYTHONPATH=%cd%" (windows)
export PYTHONPATH=backend (linux)

1. 启动 docker compose up -d
2. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
3. rq worker
  powershell中
    rq worker -u redis://localhost:6379/0 default
  linux中：
    rq worker -u "${REDIS_URL:-redis://localhost:6379/0}" default   (另起一个终端)

4. 验证



## 启动 rq worker
cd backend
export PYTHONPATH=backend
# 如果你有 REDIS_URL（例如 redis://localhost:6379/0），可以加 -u
rq worker -u "${REDIS_URL:-redis://localhost:6379/0}" default




## uv方式安装环境
pip install uv
uv venv --python 3.11
### 启动项目
uv run uvicorn app.main:app --reload