-- 清理可能冲突的 PostgreSQL 类型
-- 用于修复 "duplicate key value violates unique constraint pg_type_typname_nsp_index" 错误

-- 删除可能存在的冲突类型
DROP TYPE IF EXISTS conversation_history CASCADE;

-- 如果需要，也可以清理其他可能冲突的类型
-- DROP TYPE IF EXISTS sessions CASCADE;
-- DROP TYPE IF EXISTS question_queue CASCADE;
-- DROP TYPE IF EXISTS reasoning_results CASCADE;

