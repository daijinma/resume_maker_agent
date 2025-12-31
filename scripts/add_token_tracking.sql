-- Token 追踪系统数据库迁移脚本
-- 创建时间: 2025-01-23

-- Token 使用记录表：存储每次 LLM 调用的 token 信息
CREATE TABLE IF NOT EXISTS token_usage (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,  -- router, info_worker, experience_worker, skill_worker, inference, aggregator
    agent_class VARCHAR(100),  -- Agent 类名（如 Router, InfoWorker）
    model_name VARCHAR(255) NOT NULL,  -- 使用的模型名称
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent_type ON token_usage(agent_type);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_name);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_session_created ON token_usage(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent_created ON token_usage(agent_type, created_at DESC);

-- 添加注释
COMMENT ON TABLE token_usage IS '存储每次 LLM 调用的 token 使用情况';
COMMENT ON COLUMN token_usage.session_id IS '会话ID，关联到 sessions 表';
COMMENT ON COLUMN token_usage.agent_type IS 'Agent 类型：router, info_worker, experience_worker, skill_worker, inference, aggregator';
COMMENT ON COLUMN token_usage.agent_class IS 'Agent 类名，用于更精确的识别';
COMMENT ON COLUMN token_usage.model_name IS '使用的模型名称';
COMMENT ON COLUMN token_usage.input_tokens IS '输入 token 数量';
COMMENT ON COLUMN token_usage.output_tokens IS '输出 token 数量';
COMMENT ON COLUMN token_usage.total_tokens IS '总 token 数量';


