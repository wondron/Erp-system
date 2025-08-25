from app.infrastructure.db import init_db
from app.infrastructure.db import Base
import app.domain.models
# 必须要加，不然连不上

# 方式 1：打印所有表
print("=== tables ===")
for tbl_name, table in Base.metadata.tables.items():
    print(tbl_name, "->", table)

# 方式 2：打印所有 ORM 类
print("=== ORM classes ===")
for mapper in Base.registry.mappers:
    print(mapper.class_.__name__, "->", mapper.local_table)
    
    
init_db(create_all=True)