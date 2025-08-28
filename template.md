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