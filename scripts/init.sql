-- 双轨异步推理架构数据库初始化脚本
-- 创建时间: 2025-01-23

-- 清理可能存在的冲突类型（如果存在）
DROP TYPE IF EXISTS conversation_history CASCADE;

-- 会话表：存储用户会话数据
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    resume_data JSONB NOT NULL DEFAULT '{}',
    question_queue JSONB NOT NULL DEFAULT '{}',
    background_reasoning_status VARCHAR(50) DEFAULT 'pending',
    last_reasoning_time TIMESTAMP,
    history JSONB DEFAULT '[]',  -- 对话历史（两种架构共享）
    last_question TEXT,  -- 最后一个问题（两种架构共享）
    pending_questions JSONB DEFAULT '[]',  -- Planner-Worker 架构使用
    inference_insights JSONB DEFAULT '[]',  -- 两种架构共享
    last_resume_hash VARCHAR(255),  -- Planner-Worker 架构使用
    agent_type VARCHAR(50) DEFAULT 'planner_worker',  -- 最后使用的 agent 类型
    session_name VARCHAR(255),  -- 会话的自定义名称
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 问题队列表：存储每个会话的问题
CREATE TABLE IF NOT EXISTS question_queue (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    question_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 99,
    field VARCHAR(100),
    reason TEXT,
    answered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    answered_at TIMESTAMP,
    UNIQUE(session_id, question_id)
);

-- 推理结果表：存储背景推理的分析结果
CREATE TABLE IF NOT EXISTS reasoning_results (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    insights JSONB NOT NULL DEFAULT '[]',
    summary TEXT,
    model_used VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话历史表：存储所有对话记录
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    agent_type VARCHAR(50) NOT NULL,  -- 'planner_worker' or 'dual_track'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_sessions_reasoning_status ON sessions(background_reasoning_status);
CREATE INDEX IF NOT EXISTS idx_question_queue_session ON question_queue(session_id);
CREATE INDEX IF NOT EXISTS idx_question_queue_priority ON question_queue(session_id, priority, answered);
CREATE INDEX IF NOT EXISTS idx_question_queue_unanswered ON question_queue(session_id, answered) WHERE answered = FALSE;
CREATE INDEX IF NOT EXISTS idx_reasoning_results_session ON reasoning_results(session_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_results_created ON reasoning_results(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_history_session ON conversation_history(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversation_history_agent_type ON conversation_history(session_id, agent_type);
CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent_type ON token_usage(agent_type);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_name);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_session_created ON token_usage(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent_created ON token_usage(agent_type, created_at DESC);

-- 更新 updated_at 的触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为 sessions 表创建触发器
DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

