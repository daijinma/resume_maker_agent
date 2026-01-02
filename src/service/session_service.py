"""
统一的会话管理服务
使用 PostgreSQL 数据库存储
"""
import json
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncpg
from src.config.database import DatabaseConfig

logger = logging.getLogger("service.session")

# #region agent log helper
def _write_debug_log(data: dict):
    """安全地写入调试日志"""
    try:
        import json as json_lib
        import time
        log_data = {
            "sessionId": data.get("sessionId", "debug-session"),
            "runId": data.get("runId", "run1"),
            "hypothesisId": data.get("hypothesisId", "?"),
            "location": data.get("location", "unknown"),
            "message": data.get("message", ""),
            "data": data.get("data", {}),
            "timestamp": data.get("timestamp", int(time.time() * 1000))
        }
        with open('/Users/daijinma/Desktop/work/agnet1/.cursor/debug.log', 'a', encoding='utf-8') as f:
            f.write(json_lib.dumps(log_data, ensure_ascii=False) + '\n')
        logger.info(f"[DEBUG] {log_data['location']}: {log_data['message']} - {json_lib.dumps(log_data['data'], ensure_ascii=False)}")
    except Exception as e:
        logger.debug(f"Debug log write failed: {e}")
# #endregion


class DBSessionStorage:
    """PostgreSQL 数据库存储"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DatabaseConfig.DATABASE_URL
        self.pool: Optional[asyncpg.Pool] = None
    
    async def _ensure_tables_exist(self):
        """确保数据库表存在，如果不存在则创建"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            # 清理可能存在的冲突类型（如果存在）
            try:
                await conn.execute("""
                    DROP TYPE IF EXISTS conversation_history CASCADE
                """)
            except Exception as e:
                logger.debug(f"清理类型时出现异常（可忽略）: {e}")
            
            # 检查并创建 conversation_history 表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    agent_type VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查并创建 sessions 表（如果不存在）
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
                    resume_data JSONB NOT NULL DEFAULT '{}',
                    question_queue JSONB NOT NULL DEFAULT '{}',
                    background_reasoning_status VARCHAR(50) DEFAULT 'pending',
                    last_reasoning_time TIMESTAMP,
                    history JSONB DEFAULT '[]',
                    last_question TEXT,
                    pending_questions JSONB DEFAULT '[]',
                    inference_insights JSONB DEFAULT '[]',
                    last_resume_hash VARCHAR(255),
                    agent_type VARCHAR(50) DEFAULT 'planner_worker',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查并添加缺失的列（用于迁移现有表）
            # 检查 history 列是否存在
            column_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'sessions' 
                    AND column_name = 'history'
                )
            """)
            
            if not column_exists:
                logger.info("添加缺失的 history 列到 sessions 表")
                await conn.execute("""
                    ALTER TABLE sessions 
                    ADD COLUMN history JSONB DEFAULT '[]'
                """)
            
            # 检查其他可能缺失的列
            columns_to_check = [
                ('last_question', 'TEXT'),
                ('pending_questions', 'JSONB DEFAULT \'[]\''),
                ('inference_insights', 'JSONB DEFAULT \'[]\''),
                ('last_resume_hash', 'VARCHAR(255)'),
                ('agent_type', 'VARCHAR(50) DEFAULT \'planner_worker\''),
                ('background_reasoning_status', 'VARCHAR(50) DEFAULT \'pending\''),
                ('last_reasoning_time', 'TIMESTAMP'),
                ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for column_name, column_def in columns_to_check:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'sessions' 
                        AND column_name = $1
                    )
                """, column_name)
                
                if not exists:
                    logger.info(f"添加缺失的 {column_name} 列到 sessions 表")
                    await conn.execute(f"""
                        ALTER TABLE sessions 
                        ADD COLUMN {column_name} {column_def}
                    """)
            
            # 创建索引（如果不存在）
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_history_session 
                ON conversation_history(session_id, created_at)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_history_agent_type 
                ON conversation_history(session_id, agent_type)
            """)
            
            # 检查并创建 token_usage 表（如果不存在）
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    agent_type VARCHAR(50) NOT NULL,
                    agent_class VARCHAR(100),
                    model_name VARCHAR(255) NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建 token_usage 表的索引（如果不存在）
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_session 
                ON token_usage(session_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_agent_type 
                ON token_usage(agent_type)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_model 
                ON token_usage(model_name)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_created_at 
                ON token_usage(created_at)
            """)
            
            logger.debug("数据库表已确保存在")
    
    async def initialize(self, pool_size: int = 10):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=DatabaseConfig.DB_MIN_SIZE,
                max_size=pool_size
            )
            logger.info("数据库连接池已初始化")
            # 确保表存在
            await self._ensure_tables_exist()
    
    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("数据库连接池已关闭")
    
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        # #region agent log
        _write_debug_log({
            "hypothesisId": "A",
            "location": "session_service.py:227",
            "message": "DBSessionStorage.get_session entry",
            "data": {"session_id": session_id, "pool_is_none": self.pool is None}
        })
        # #endregion
        
        try:
            await self.initialize()
        except Exception as e:
            # #region agent log
            import traceback
            _write_debug_log({
                "hypothesisId": "A",
                "location": "session_service.py:234",
                "message": "initialize failed",
                "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
            })
            # #endregion
            raise
        
        # #region agent log
        _write_debug_log({
            "hypothesisId": "A",
            "location": "session_service.py:240",
            "message": "Before acquire connection",
            "data": {}
        })
        # #endregion
        
        async with self.pool.acquire() as conn:
            # #region agent log
            _write_debug_log({
                "hypothesisId": "A",
                "location": "session_service.py:243",
                "message": "Before fetchrow",
                "data": {}
            })
            # #endregion
            
            try:
                row = await conn.fetchrow("""
                    SELECT session_id, resume_data, question_queue, 
                           background_reasoning_status, last_reasoning_time,
                           history, last_question, pending_questions,
                           inference_insights, last_resume_hash, agent_type,
                           created_at, updated_at
                    FROM sessions
                    WHERE session_id = $1
                """, session_id)
                
                # #region agent log
                _write_debug_log({
                    "hypothesisId": "A",
                    "location": "session_service.py:258",
                    "message": "After fetchrow",
                    "data": {"row_is_none": row is None}
                })
                # #endregion
            except Exception as e:
                # #region agent log
                import traceback
                _write_debug_log({
                    "hypothesisId": "A",
                    "location": "session_service.py:264",
                    "message": "fetchrow failed",
                    "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
                })
                # #endregion
                raise
            
            if row:
                # 确保 resume_data 是字典类型（asyncpg 应该自动解析 JSONB，但做安全检查）
                resume_data = row["resume_data"]
                if isinstance(resume_data, str):
                    try:
                        resume_data = json.loads(resume_data)
                    except:
                        resume_data = {}
                elif resume_data is None:
                    resume_data = {}
                
                # 确保 question_queue 是字典类型
                question_queue = row["question_queue"]
                if isinstance(question_queue, str):
                    try:
                        question_queue = json.loads(question_queue)
                    except:
                        question_queue = {}
                elif question_queue is None:
                    question_queue = {}
                
                # 确保 history 是列表类型
                history = row["history"]
                if isinstance(history, str):
                    try:
                        history = json.loads(history)
                    except:
                        history = []
                elif history is None:
                    history = []
                
                # 确保 pending_questions 是列表类型
                pending_questions = row["pending_questions"]
                if isinstance(pending_questions, str):
                    try:
                        pending_questions = json.loads(pending_questions)
                    except:
                        pending_questions = []
                elif pending_questions is None:
                    pending_questions = []
                
                # 确保 inference_insights 是列表类型
                inference_insights = row["inference_insights"]
                if isinstance(inference_insights, str):
                    try:
                        inference_insights = json.loads(inference_insights)
                    except:
                        inference_insights = []
                elif inference_insights is None:
                    inference_insights = []
                
                return {
                    "session_id": row["session_id"],
                    "resume_data": resume_data,
                    "question_queue": question_queue,
                    "background_reasoning_status": row["background_reasoning_status"] or "pending",
                    "last_reasoning_time": row["last_reasoning_time"].isoformat() if row["last_reasoning_time"] else None,
                    "history": history,
                    "last_question": row["last_question"],
                    "pending_questions": pending_questions,
                    "inference_insights": inference_insights,
                    "last_resume_hash": row["last_resume_hash"],
                    "agent_type": row["agent_type"] or "planner_worker",
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
            else:
                # #region agent log
                _write_debug_log({
                    "hypothesisId": "A",
                    "location": "session_service.py:307",
                    "message": "Creating new session",
                    "data": {"session_id": session_id}
                })
                # #endregion
                
                default_data = {
                    "personal_info": {},
                    "education": [],
                    "experience": [],
                    "skills": []
                }
                
                try:
                    await conn.execute("""
                        INSERT INTO sessions (session_id, resume_data, question_queue, history)
                        VALUES ($1, $2, $3, $4)
                    """, session_id, json.dumps(default_data), json.dumps({}), json.dumps([]))
                    
                    # #region agent log
                    _write_debug_log({
                        "hypothesisId": "A",
                        "location": "session_service.py:320",
                        "message": "New session created successfully",
                        "data": {}
                    })
                    # #endregion
                    
                    logger.info(f"已创建新会话: {session_id}")
                except Exception as e:
                    # #region agent log
                    import traceback
                    _write_debug_log({
                        "hypothesisId": "A",
                        "location": "session_service.py:327",
                        "message": "Failed to create new session",
                        "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
                    })
                    # #endregion
                    raise
                
                return {
                    "session_id": session_id,
                    "resume_data": default_data,
                    "question_queue": {},
                    "background_reasoning_status": "pending",
                    "last_reasoning_time": None,
                    "history": [],
                    "last_question": None,
                    "pending_questions": [],
                    "inference_insights": [],
                    "last_resume_hash": None,
                    "agent_type": "planner_worker",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
    
    async def save_session(self, session_id: str, data: Dict[str, Any]):
        await self.initialize()
        
        async with self.pool.acquire() as conn:
            resume_data = data.get("resume_data", {})
            question_queue = data.get("question_queue", {})
            background_reasoning_status = data.get("background_reasoning_status", "pending")
            last_reasoning_time = data.get("last_reasoning_time")
            history = data.get("history", [])
            last_question = data.get("last_question")
            pending_questions = data.get("pending_questions", [])
            inference_insights = data.get("inference_insights", [])
            last_resume_hash = data.get("last_resume_hash")
            agent_type = data.get("agent_type", "planner_worker")
            
            # 修复：确保 last_resume_hash 是字符串（hash() 返回整数）
            if last_resume_hash is not None and not isinstance(last_resume_hash, str):
                last_resume_hash = str(last_resume_hash)
            
            if isinstance(last_reasoning_time, str):
                try:
                    last_reasoning_time = datetime.fromisoformat(last_reasoning_time)
                except:
                    last_reasoning_time = None
            
            await conn.execute("""
                INSERT INTO sessions 
                (session_id, resume_data, question_queue, 
                 background_reasoning_status, last_reasoning_time,
                 history, last_question, pending_questions,
                 inference_insights, last_resume_hash, agent_type)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (session_id) 
                DO UPDATE SET
                    resume_data = EXCLUDED.resume_data,
                    question_queue = EXCLUDED.question_queue,
                    background_reasoning_status = EXCLUDED.background_reasoning_status,
                    last_reasoning_time = EXCLUDED.last_reasoning_time,
                    history = EXCLUDED.history,
                    last_question = EXCLUDED.last_question,
                    pending_questions = EXCLUDED.pending_questions,
                    inference_insights = EXCLUDED.inference_insights,
                    last_resume_hash = EXCLUDED.last_resume_hash,
                    agent_type = EXCLUDED.agent_type,
                    updated_at = CURRENT_TIMESTAMP
            """, 
                session_id,
                json.dumps(resume_data) if isinstance(resume_data, dict) else resume_data,
                json.dumps(question_queue) if isinstance(question_queue, dict) else question_queue,
                background_reasoning_status,
                last_reasoning_time,
                json.dumps(history) if isinstance(history, list) else history,
                last_question,
                json.dumps(pending_questions) if isinstance(pending_questions, list) else pending_questions,
                json.dumps(inference_insights) if isinstance(inference_insights, list) else inference_insights,
                last_resume_hash,
                agent_type
            )
            
            logger.debug(f"已保存会话: {session_id}")
    
    async def add_message(self, session_id: str, role: str, content: str, agent_type: str):
        """添加消息到对话历史"""
        # #region agent log
        _write_debug_log({
            "hypothesisId": "B",
            "location": "session_service.py:394",
            "message": "add_message entry",
            "data": {"session_id": session_id, "role": role, "content_len": len(content)}
        })
        # #endregion
        
        try:
            await self.initialize()
            # 确保表存在（额外安全检查）
            await self._ensure_tables_exist()
        except Exception as e:
            # #region agent log
            import traceback
            _write_debug_log({
                "hypothesisId": "B",
                "location": "session_service.py:402",
                "message": "initialize/_ensure_tables_exist failed",
                "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
            })
            # #endregion
            raise
        
        async with self.pool.acquire() as conn:
            # #region agent log
            _write_debug_log({
                "hypothesisId": "B",
                "location": "session_service.py:407",
                "message": "Before INSERT conversation_history",
                "data": {}
            })
            # #endregion
            
            try:
                # 添加到 conversation_history 表
                await conn.execute("""
                    INSERT INTO conversation_history (session_id, role, content, agent_type)
                    VALUES ($1, $2, $3, $4)
                """, session_id, role, content, agent_type)
                
                # #region agent log
                _write_debug_log({
                    "hypothesisId": "B",
                    "location": "session_service.py:415",
                    "message": "After INSERT conversation_history success",
                    "data": {}
                })
                # #endregion
            except Exception as e:
                # #region agent log
                import traceback
                _write_debug_log({
                    "hypothesisId": "B",
                    "location": "session_service.py:421",
                    "message": "INSERT conversation_history failed",
                    "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
                })
                # #endregion
                raise
            
            # 更新 sessions 表的 history 字段
            session_data = await self.get_session(session_id)
            history = session_data.get("history", [])
            history.append({
                "role": role,
                "content": content,
                "agent_type": agent_type,
                "timestamp": datetime.now().isoformat()
            })
            
            await conn.execute("""
                UPDATE sessions
                SET history = $1
                WHERE session_id = $2
            """, json.dumps(history), session_id)
    
    async def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取对话历史（返回最近的记录）"""
        await self.initialize()
        # 确保表存在（额外安全检查）
        await self._ensure_tables_exist()
        
        async with self.pool.acquire() as conn:
            query = """
                SELECT role, content, agent_type, created_at
                FROM conversation_history
                WHERE session_id = $1
                ORDER BY created_at DESC
            """
            params = [session_id]
            
            if limit:
                query += " LIMIT $2"
                params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            # 反转顺序，使最早的在前（保持对话顺序）
            rows = list(reversed(rows))
            
            return [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "agent_type": row["agent_type"],
                    "timestamp": row["created_at"].isoformat() if row["created_at"] else None
                }
                for row in rows
            ]
    
    async def get_pending_questions(self, session_id: str, limit: int = 1) -> List[Dict[str, Any]]:
        """获取待提问的问题"""
        await self.initialize()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT question_id, content, priority, field, reason
                FROM question_queue
                WHERE session_id = $1 AND answered = FALSE
                ORDER BY priority ASC, created_at ASC
                LIMIT $2
            """, session_id, limit)
            
            return [
                {
                    "id": row["question_id"],
                    "content": row["content"],
                    "priority": row["priority"],
                    "field": row["field"],
                    "reason": row["reason"]
                }
                for row in rows
            ]
    
    async def mark_question_answered(self, session_id: str, question_id: str):
        """标记问题为已回答"""
        await self.initialize()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE question_queue
                SET answered = TRUE, answered_at = CURRENT_TIMESTAMP
                WHERE session_id = $1 AND question_id = $2
            """, session_id, question_id)
    
    async def save_question_queue(self, session_id: str, question_queue_data: Dict[str, Any]):
        """保存问题队列到数据库表"""
        await self.initialize()
        
        async with self.pool.acquire() as conn:
            # 先更新 sessions 表的 question_queue 字段
            await conn.execute("""
                UPDATE sessions
                SET question_queue = $1
                WHERE session_id = $2
            """, json.dumps(question_queue_data), session_id)
            
            # 同时更新 question_queue 表
            questions = question_queue_data.get("questions", [])
            answered = question_queue_data.get("answered", [])
            
            # 删除旧的问题
            await conn.execute("""
                DELETE FROM question_queue WHERE session_id = $1
            """, session_id)
            
            # 插入新问题
            for q in questions:
                question_id = q.get("id")
                if question_id in answered:
                    continue
                
                await conn.execute("""
                    INSERT INTO question_queue 
                    (session_id, question_id, content, priority, field, reason, answered)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (session_id, question_id) 
                    DO UPDATE SET
                        content = EXCLUDED.content,
                        priority = EXCLUDED.priority,
                        field = EXCLUDED.field,
                        reason = EXCLUDED.reason,
                        answered = EXCLUDED.answered
                """,
                    session_id,
                    question_id,
                    q.get("content", ""),
                    q.get("priority", 99),
                    q.get("field"),
                    q.get("reason"),
                    False
                )
            
            logger.debug(f"已保存问题队列: {session_id}")


class SessionService:
    """统一的会话管理服务（使用数据库存储）"""
    
    def __init__(self):
        """初始化会话服务"""
        self.storage = DBSessionStorage()
    
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """获取会话数据"""
        return await self.storage.get_session(session_id)
    
    async def save_session(self, session_id: str, data: Dict[str, Any]):
        """保存会话数据"""
        await self.storage.save_session(session_id, data)
    
    async def add_message(self, session_id: str, role: str, content: str, agent_type: str):
        """添加消息到对话历史"""
        await self.storage.add_message(session_id, role, content, agent_type)
    
    async def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return await self.storage.get_history(session_id, limit)
    
    async def get_pending_questions(self, session_id: str, limit: int = 1) -> List[Dict[str, Any]]:
        """获取待提问的问题"""
        return await self.storage.get_pending_questions(session_id, limit)
    
    async def mark_question_answered(self, session_id: str, question_id: str):
        """标记问题为已回答"""
        await self.storage.mark_question_answered(session_id, question_id)
    
    async def initialize(self):
        """初始化数据库连接"""
        await self.storage.initialize()
    
    async def get_question_queue(self, session_id: str) -> Dict[str, Any]:
        """获取问题队列数据"""
        await self.storage.initialize()
        session_data = await self.storage.get_session(session_id)
        return session_data.get("question_queue", {"questions": [], "answered": []})
    
    async def save_question_queue(self, session_id: str, question_queue_data: Dict[str, Any]):
        """保存问题队列"""
        await self.storage.save_question_queue(session_id, question_queue_data)
    
    async def close(self):
        """关闭数据库连接"""
        await self.storage.close()
    
    async def list_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有会话列表（按创建时间倒序）"""
        await self.storage.initialize()
        await self.storage._ensure_tables_exist()
        
        async with self.storage.pool.acquire() as conn:
            query = """
                SELECT session_id, agent_type, created_at, updated_at
                FROM sessions
                ORDER BY created_at DESC
            """
            params = []
            
            if limit:
                query += " LIMIT $1"
                params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return [
                {
                    "session_id": row["session_id"],
                    "agent_type": row["agent_type"] or "planner_worker",
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                }
                for row in rows
            ]
    
    async def get_session_token_summary(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的 token 使用摘要
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 包含总输入/输出 token 和总消耗
        """
        try:
            from src.utils.token_tracker import get_token_tracker
            token_tracker = get_token_tracker()
            total = await token_tracker.get_session_total(session_id)
            
            return {
                "session_id": session_id,
                "input_tokens": total.get("input_tokens", 0),
                "output_tokens": total.get("output_tokens", 0),
                "total_tokens": total.get("total_tokens", 0),
                "summary": {
                    "input_tokens": total.get("input_tokens", 0),
                    "output_tokens": total.get("output_tokens", 0),
                    "total_tokens": total.get("total_tokens", 0)
                }
            }
        except Exception as e:
            logger.error(f"获取会话 token 摘要失败: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "error": str(e)
            }

