-- ===== 在数据库 erp 内执行 =====

-- 1) 业务用户与只读用户（若不存在则创建）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_app') THEN
        CREATE ROLE erp_app LOGIN PASSWORD 'change_me_strong_password';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_readonly') THEN
        CREATE ROLE erp_readonly LOGIN PASSWORD 'readonly_strong_password';
    END IF;
END $$;

-- 2) 业务 schema
CREATE SCHEMA IF NOT EXISTS erp_app AUTHORIZATION erp_app;

-- 可选：把 search_path 设为业务 schema 优先
ALTER DATABASE erp SET search_path = erp_app, public;
ALTER ROLE erp_app IN DATABASE erp SET search_path = erp_app, public;

-- 3) 常用扩展（按需）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

-- 4) 权限
-- 让 erp_app 拥有 schema，并可在其中建表/序列等
GRANT USAGE, CREATE ON SCHEMA erp_app TO erp_app;

-- 只读用户：允许连接与只读访问
GRANT CONNECT ON DATABASE erp TO erp_readonly;
GRANT USAGE ON SCHEMA erp_app TO erp_readonly;

-- 现有对象的读权限
GRANT SELECT ON ALL TABLES IN SCHEMA erp_app TO erp_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA erp_app TO erp_readonly;

-- 将来新建对象的默认权限（很重要）
ALTER DEFAULT PRIVILEGES FOR ROLE erp_app IN SCHEMA erp_app
    GRANT SELECT ON TABLES TO erp_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE erp_app IN SCHEMA erp_app
    GRANT USAGE, SELECT ON SEQUENCES TO erp_readonly;

-- 5) 安全起见，避免 public 对象可写
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
