# backend/scripts/inspect_db.py
from __future__ import annotations

import os
import sys
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import inspect as sa_inspect

# 允许以 "python backend/scripts/inspect_db.py" 方式运行
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 读取连接串：优先环境变量，其次项目 Settings
try:
    from app.core.config import get_settings  # noqa: E402
    DB_URL = get_settings().sqlalchemy_database_uri
except Exception as e:  # 兜底：如果配置导入失败，提示使用环境变量
    print(f"[WARN] cannot import app.core.config: {e}")
    DB_URL = os.environ.get("DATABASE_URL")

if not DB_URL:
    raise SystemExit(
        "No DATABASE_URL provided. Set env DATABASE_URL or ensure app.core.config works.\n"
        "Example: postgresql+psycopg://erp_app:password@localhost:5432/erp"
    )

print(f"[INFO] Using DATABASE_URL = {DB_URL}")

# 建立引擎（显示 echo=True 可看到 SQL）
engine = create_engine(DB_URL, future=True, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Session:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def q(session: Session, sql: str):
    """便捷查询并返回 list[dict]"""
    res = session.execute(text(sql))
    cols = res.keys()
    return [dict(zip(cols, row)) for row in res.fetchall()]


def main():
    print("\n=== 1) 基本连通性/版本信息 ===")
    with engine.connect() as conn:
        ver = conn.execute(text("select version()")).scalar()
        print(f"server_version: {ver}")

    with session_scope() as s:
        basics = q(
            s,
            """
            select
              current_database() as db,
              current_user       as user,
              current_schema     as schema,
              setting            as search_path
            from pg_settings
            where name = 'search_path'
            """,
        )
        for row in basics:
            print(f"db={row['db']} user={row['user']} schema={row['schema']} search_path={row['search_path']}")

    print("\n=== 2) schema 一览 ===")
    with session_scope() as s:
        for row in q(
            s,
            """
            select nspname as schema, pg_get_userbyid(nspowner) as owner
            from pg_namespace
            where nspname not like 'pg_%'
            order by 1
            """,
        ):
            print(row)

    print("\n=== 3) 已安装扩展 ===")
    with session_scope() as s:
        for row in q(s, "select extname, extversion from pg_extension order by 1"):
            print(row)

    print("\n=== 4) 角色(用户) ===")
    with session_scope() as s:
        for row in q(
            s,
            """
            select rolname as role,
                   rolsuper as is_superuser,
                   rolcreaterole as can_create_role,
                   rolcreatedb as can_create_db,
                   rolcanlogin as can_login
            from pg_roles
            order by 1
            """,
        ):
            print(row)

    print("\n=== 5) erp_app schema 下的表 ===")
    insp = sa_inspect(engine)
    if "erp_app" in insp.get_schema_names():
        tables = insp.get_table_names(schema="erp_app")
        print("tables:", tables)
    else:
        print("schema 'erp_app' not found")

    print("\n=== 6) 读写自检（在 erp_app.test_table 上） ===")
    with session_scope() as s:
        # 建表（幂等）
        s.execute(
            text(
                """
                create extension if not exists pgcrypto;
                create schema if not exists erp_app;
                create table if not exists erp_app.test_table (
                    id uuid default gen_random_uuid() primary key,
                    name text
                )
                """
            )
        )
        # 写一行
        s.execute(text("insert into erp_app.test_table(name) values (:n)"), {"n": "hello from sqlalchemy"})
        # 读出来
        rows = q(s, "select * from erp_app.test_table order by 1 desc limit 5")
        for r in rows:
            print(r)

    print("\n=== 7) 结束：成功 ===")


if __name__ == "__main__":
    main()
