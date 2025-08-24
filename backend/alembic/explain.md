# Alembic 基础知识与用法

## 1. Alembic 是什么？

- **Alembic 是 SQLAlchemy 官方的数据库迁移工具**。  
- 作用：当你修改 ORM 模型（新增表、字段、索引等）时，不需要手动写一堆 `ALTER TABLE`，而是让 Alembic 帮你生成“迁移脚本”，然后用 `upgrade` 命令应用到数据库。  

📌 类比：
- `create_all` → 一次性把 ORM 定义建成表，但不能跟踪历史变化。  
- **Alembic** → 维护一套 **迁移历史**，类似 Git 版本控制，让数据库结构和 ORM 模型保持一致。

---

## 2. 核心概念

1. **env.py**  
   Alembic 的入口文件，定义如何连接数据库、如何加载 `target_metadata`。  

2. **alembic.ini**  
   配置文件，保存数据库 URL、迁移脚本路径。  

3. **versions/**  
   存放迁移脚本的目录，每个脚本就像一次 Git 提交。  

4. **revision**  
   Alembic 的一次迁移版本，包含 `upgrade()` 和 `downgrade()` 方法。  

5. **upgrade/downgrade**  
   - `upgrade()`：升级数据库（新增表/字段）。  
   - `downgrade()`：回滚到旧版本（删除表/字段）。  

---

## 3. 基本工作流

### 第一步：初始化 Alembic
```bash
alembic init alembic
```
会生成目录结构：
```
- alembic.ini
- alembic/
  - env.py
  - script.py.mako
  - versions/
```
### 第二步：配置数据库 URL 和元数据
- 在 alembic.ini 里配置数据库 URL（或留空，用 env.py 动态加载）。
- 在 alembic/env.py 里引入你的项目 Base.metadata：
```python
from app.infrastructure.db import Base
target_metadata = Base.metadata
```
### 第三步：生成迁移脚本
```bash
alembic revision --autogenerate -m "your message"
alembic revision --autogenerate -m "create suppliers table"

```
Alembic 会对比 当前数据库结构 和 Base.metadata，生成迁移脚本到 versions/。
### 第四步：应用迁移
```bash
alembic upgrade head
```
这会执行最新版本的 upgrade()，把数据库结构更新。

### 第五步：回滚（可选）
```bash
alembic downgrade -1   # 回退一步
alembic downgrade base # 回退到初始状态
```

## 4. 迁移脚本长啥样？
Alembic 生成的 versions/xxxx_xxx.py 脚本大致这样：

```python
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "1234567890ab"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
    )

def downgrade():
    op.drop_table("suppliers")
```
- upgrade()：执行升级操作。
- downgrade()：执行回滚操作。

## 5. 常见命令总结
```bash
alembic init alembic                # 初始化
alembic revision -m "msg"           # 创建空迁移脚本
alembic revision --autogenerate -m "msg"  # 根据模型变化自动生成迁移脚本
alembic upgrade head                # 升级到最新版本
alembic downgrade -1                # 回退一步
alembic current                     # 查看当前数据库版本
alembic history                     # 查看迁移历史
```

## 6. Alembic vs create_all
- **create_all**：
    - 一次性把 ORM 定义建成表，但不能跟踪历史变化。  
- **Alembic**：
    - 维护一套 **迁移历史**，类似 Git 版本控制，让数据库结构和 ORM 模型保持一致。
    - 开发时每次改模型要跑 revision --autogenerate → upgrade head

## 7. 在你的项目里怎么用？
因为你已经有了：
- `backend/app/infrastructure/db.py` (有 `Base` 和 `engine`)
- `backend/alembic/` 目录 (脚手架应该已生成)

1. 在 alembic/env.py 加上：
```python
from app.infrastructure.db import Base
target_metadata = Base.metadata
```
2. 在你新建/修改 ORM 模型后，运行：
```bash
alembic revision --autogenerate -m "add purchase orders table"
alembic upgrade head
```
3. 数据库会更新，表结构和代码保持一致。

Alembic 就是 SQLAlchemy 的“版本控制工具”，帮你记录数据库表结构的演变历史，让你像管理代码一样管理数据库。