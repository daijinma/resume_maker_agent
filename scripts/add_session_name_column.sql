-- 添加 session_name 列到 sessions 表（如果不存在）
-- 用于存储会话的自定义名称

-- 检查并添加 session_name 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'sessions' 
        AND column_name = 'session_name'
    ) THEN
        ALTER TABLE sessions ADD COLUMN session_name VARCHAR(255);
        RAISE NOTICE '已添加 session_name 列到 sessions 表';
    ELSE
        RAISE NOTICE 'session_name 列已存在，无需添加';
    END IF;
END $$;

