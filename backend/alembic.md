没问题！下面是一套从零搭起 backend/alembic 的完整指引和可直接复制的代码片段，按顺序操作就能跑起来（适配你现有的 db.py / config.py 结构，PostgreSQL + SQLAlchemy 2.0）。

## 在 backend 目录安装 Alembic
```powershell
cd backend
pip install alembic
```

## 初始化骨架
```powershell
# 仍在 backend 目录下
alembic init alembic
```
会生成：
```
backend/
  alembic.ini
  alembic/
    env.py
    README
    script.py.mako
    versions/
```

## 修改 alembic.ini（最小化配置）
把 `sqlalchemy.url` 留空，让我们在 `env.py` 里动态读取你项目的配置；并把版本目录定位到 `backend/alembic/versions`（默认就是）。
```ini
# backend/alembic.ini 关键段落

[alembic]
script_location = alembic

# 留空，交给 env.py 读取 Settings.DATABASE_URL
sqlalchemy.url =

# 可选：更干净的日志
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_alembic]
level = INFO
handlers = console
qualname = alembic
```

## 替换 alembic/env.py（适配你的项目）
用下面这份 **完整 env.py** 覆盖 `backend/alembic/env.py`。它会：

- 把 `backend/` 加到 `sys.path`，能 `import app.*`

- 从 `app.core.config.get_settings()` 读取数据库 `URL`

- 使用 `app.infrastructure.db.Base.metadata` 作为 `target_metadata`（自动检测模型变化）
- 让 Alembic 的版本表建在 `erp_app` schema（可改）
