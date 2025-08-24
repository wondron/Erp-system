-- ==== 变量（按需改名/改密码）====
-- 业务库名
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'erp') THEN
        PERFORM pg_sleep(0);
        -- 创建数据库（UTF-8）
        CREATE DATABASE erp
            WITH ENCODING 'UTF8'
                 LC_COLLATE 'C'
                 LC_CTYPE 'C'
                 TEMPLATE template0;
    END IF;
END $$;

-- 下面的对象需要在 erp 数据库内创建，切换到 erp 再执行
-- 如果你用 psql -f，这段不会自动切库；见后面“执行方式”里的两段式执行。
