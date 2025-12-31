-- 添加 history 列到 sessions 表（如果不存在）
-- 用于修复 "column history does not exist" 错误

-- 检查并添加 history 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'sessions' 
        AND column_name = 'history'
    ) THEN
        ALTER TABLE sessions ADD COLUMN history JSONB DEFAULT '[]';
        RAISE NOTICE '已添加 history 列到 sessions 表';
    ELSE
        RAISE NOTICE 'history 列已存在，无需添加';
    END IF;
END $$;

-- 检查并添加其他可能缺失的列
DO $$
BEGIN
    -- last_question
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'last_question'
    ) THEN
        ALTER TABLE sessions ADD COLUMN last_question TEXT;
        RAISE NOTICE '已添加 last_question 列';
    END IF;
    
    -- pending_questions
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'pending_questions'
    ) THEN
        ALTER TABLE sessions ADD COLUMN pending_questions JSONB DEFAULT '[]';
        RAISE NOTICE '已添加 pending_questions 列';
    END IF;
    
    -- inference_insights
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'inference_insights'
    ) THEN
        ALTER TABLE sessions ADD COLUMN inference_insights JSONB DEFAULT '[]';
        RAISE NOTICE '已添加 inference_insights 列';
    END IF;
    
    -- last_resume_hash
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'last_resume_hash'
    ) THEN
        ALTER TABLE sessions ADD COLUMN last_resume_hash VARCHAR(255);
        RAISE NOTICE '已添加 last_resume_hash 列';
    END IF;
    
    -- agent_type
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'agent_type'
    ) THEN
        ALTER TABLE sessions ADD COLUMN agent_type VARCHAR(50) DEFAULT 'planner_worker';
        RAISE NOTICE '已添加 agent_type 列';
    END IF;
    
    -- background_reasoning_status
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'background_reasoning_status'
    ) THEN
        ALTER TABLE sessions ADD COLUMN background_reasoning_status VARCHAR(50) DEFAULT 'pending';
        RAISE NOTICE '已添加 background_reasoning_status 列';
    END IF;
    
    -- last_reasoning_time
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'last_reasoning_time'
    ) THEN
        ALTER TABLE sessions ADD COLUMN last_reasoning_time TIMESTAMP;
        RAISE NOTICE '已添加 last_reasoning_time 列';
    END IF;
    
    -- created_at
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE sessions ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        RAISE NOTICE '已添加 created_at 列';
    END IF;
    
    -- updated_at
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'sessions' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE sessions ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        RAISE NOTICE '已添加 updated_at 列';
    END IF;
END $$;

