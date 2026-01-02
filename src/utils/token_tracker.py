"""
Token 追踪工具
记录每次 LLM 调用的 token 使用情况
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncpg
from src.config.database import DatabaseConfig

logger = logging.getLogger("resume-agent.token_tracker")


class TokenTracker:
    """Token 使用追踪器（使用数据库存储）"""
    
    def __init__(self):
        """初始化 Token 追踪器"""
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self, pool_size: int = 10):
        """初始化数据库连接池"""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    DatabaseConfig.DATABASE_URL,
                    min_size=DatabaseConfig.DB_MIN_SIZE,
                    max_size=pool_size
                )
                logger.info("Token 追踪器数据库连接池已初始化")
            except Exception as e:
                logger.error(f"初始化 Token 追踪器数据库连接池失败: {e}")
                raise
    
    async def close(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Token 追踪器数据库连接池已关闭")
    
    async def record_usage(
        self,
        session_id: str,
        agent_type: str,
        agent_class: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: Optional[int] = None
    ):
        """
        记录 token 使用情况
        
        Args:
            session_id: 会话ID
            agent_type: Agent 类型（router, info_worker, experience_worker, skill_worker, inference, aggregator）
            agent_class: Agent 类名
            model_name: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            total_tokens: 总 token 数（如果为 None，则自动计算）
        """
        if total_tokens is None:
            total_tokens = input_tokens + output_tokens
        
        try:
            await self._record_to_database(
                session_id, agent_type, agent_class, model_name,
                input_tokens, output_tokens, total_tokens
            )
        except Exception as e:
            # 记录失败不应影响主业务逻辑
            logger.error(f"记录 token 使用情况失败: {e}", exc_info=True)
    
    async def _record_to_database(
        self,
        session_id: str,
        agent_type: str,
        agent_class: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int
    ):
        """记录到数据库"""
        await self.initialize()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO token_usage 
                (session_id, agent_type, agent_class, model_name, 
                 input_tokens, output_tokens, total_tokens)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, session_id, agent_type, agent_class, model_name,
                input_tokens, output_tokens, total_tokens)
    
    async def get_session_total(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的总 token 消耗
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 包含 input_tokens, output_tokens, total_tokens
        """
        try:
            return await self._get_session_total_from_db(session_id)
        except Exception as e:
            logger.error(f"获取会话 token 统计失败: {e}", exc_info=True)
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
    async def _get_session_total_from_db(self, session_id: str) -> Dict[str, Any]:
        """从数据库获取会话统计"""
        await self.initialize()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(total_tokens) as total_tokens
                FROM token_usage
                WHERE session_id = $1
            """, session_id)
            
            if row:
                return {
                    "input_tokens": row["input_tokens"] or 0,
                    "output_tokens": row["output_tokens"] or 0,
                    "total_tokens": row["total_tokens"] or 0
                }
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    
    async def get_statistics(
        self,
        session_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        model_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        多维度统计查询
        
        Args:
            session_id: 会话ID（可选）
            agent_type: Agent 类型（可选）
            model_name: 模型名称（可选）
            start_date: 开始时间（可选）
            end_date: 结束时间（可选）
            group_by: 分组方式（'agent_type', 'model_name', 'day', 'week', 'month'）
            
        Returns:
            Dict: 统计结果
        """
        try:
            return await self._get_statistics_from_db(
                session_id, agent_type, model_name, start_date, end_date, group_by
            )
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}", exc_info=True)
            return {"total": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
    
    async def _get_statistics_from_db(
        self,
        session_id: Optional[str],
        agent_type: Optional[str],
        model_name: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        group_by: Optional[str]
    ) -> Dict[str, Any]:
        """从数据库获取统计"""
        await self.initialize()
        
        conditions = []
        params = []
        param_idx = 1
        
        if session_id:
            conditions.append(f"session_id = ${param_idx}")
            params.append(session_id)
            param_idx += 1
        
        if agent_type:
            conditions.append(f"agent_type = ${param_idx}")
            params.append(agent_type)
            param_idx += 1
        
        if model_name:
            conditions.append(f"model_name = ${param_idx}")
            params.append(model_name)
            param_idx += 1
        
        if start_date:
            conditions.append(f"created_at >= ${param_idx}")
            params.append(start_date)
            param_idx += 1
        
        if end_date:
            conditions.append(f"created_at <= ${param_idx}")
            params.append(end_date)
            param_idx += 1
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        if group_by:
            if group_by == "agent_type":
                group_clause = "GROUP BY agent_type"
                select_extra = ", agent_type"
            elif group_by == "model_name":
                group_clause = "GROUP BY model_name"
                select_extra = ", model_name"
            elif group_by == "day":
                group_clause = "GROUP BY DATE(created_at)"
                select_extra = ", DATE(created_at) as date"
            elif group_by == "week":
                group_clause = "GROUP BY DATE_TRUNC('week', created_at)"
                select_extra = ", DATE_TRUNC('week', created_at) as week"
            elif group_by == "month":
                group_clause = "GROUP BY DATE_TRUNC('month', created_at)"
                select_extra = ", DATE_TRUNC('month', created_at) as month"
            else:
                group_clause = ""
                select_extra = ""
        else:
            group_clause = ""
            select_extra = ""
        
        query = f"""
            SELECT 
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(total_tokens) as total_tokens
                {select_extra}
            FROM token_usage
            {where_clause}
            {group_clause}
            ORDER BY total_tokens DESC
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            if group_by:
                result = {
                    "groups": [],
                    "total": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                }
                for row in rows:
                    group_data = {
                        "input_tokens": row["input_tokens"] or 0,
                        "output_tokens": row["output_tokens"] or 0,
                        "total_tokens": row["total_tokens"] or 0
                    }
                    if group_by == "agent_type":
                        group_data["agent_type"] = row["agent_type"]
                    elif group_by == "model_name":
                        group_data["model_name"] = row["model_name"]
                    elif group_by == "day":
                        group_data["date"] = row["date"].isoformat() if row["date"] else None
                    elif group_by == "week":
                        group_data["week"] = row["week"].isoformat() if row["week"] else None
                    elif group_by == "month":
                        group_data["month"] = row["month"].isoformat() if row["month"] else None
                    
                    result["groups"].append(group_data)
                    result["total"]["input_tokens"] += group_data["input_tokens"]
                    result["total"]["output_tokens"] += group_data["output_tokens"]
                    result["total"]["total_tokens"] += group_data["total_tokens"]
                
                return result
            else:
                if rows:
                    row = rows[0]
                    return {
                        "total": {
                            "input_tokens": row["input_tokens"] or 0,
                            "output_tokens": row["output_tokens"] or 0,
                            "total_tokens": row["total_tokens"] or 0
                        }
                    }
                return {"total": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}


# 全局实例
_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """获取全局 TokenTracker 实例"""
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    return _token_tracker


