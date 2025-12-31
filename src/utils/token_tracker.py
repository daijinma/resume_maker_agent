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
from src.config.settings import Settings

logger = logging.getLogger("resume-agent.token_tracker")


class TokenTracker:
    """Token 使用追踪器"""
    
    def __init__(self, use_database: Optional[bool] = None):
        """
        初始化 Token 追踪器
        
        Args:
            use_database: 是否使用数据库，None 则从配置读取
        """
        self.use_database = use_database if use_database is not None else Settings.USE_DATABASE
        self.pool: Optional[asyncpg.Pool] = None
        self.json_storage_path = "token_usage.json"
        self._json_data: Dict[str, List[Dict[str, Any]]] = {}
        if not self.use_database:
            self._load_json_data()
    
    def _load_json_data(self):
        """加载 JSON 数据"""
        if os.path.exists(self.json_storage_path):
            try:
                with open(self.json_storage_path, "r", encoding="utf-8") as f:
                    self._json_data = json.load(f)
            except Exception as e:
                logger.error(f"加载 token 使用记录失败: {e}")
                self._json_data = {}
        else:
            self._json_data = {}
    
    def _save_json_data(self):
        """保存 JSON 数据"""
        try:
            with open(self.json_storage_path, "w", encoding="utf-8") as f:
                json.dump(self._json_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 token 使用记录失败: {e}")
    
    async def initialize(self, pool_size: int = 10):
        """初始化数据库连接池（仅数据库模式）"""
        if self.use_database and self.pool is None:
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
        """关闭数据库连接池（仅数据库模式）"""
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
            if self.use_database:
                await self._record_to_database(
                    session_id, agent_type, agent_class, model_name,
                    input_tokens, output_tokens, total_tokens
                )
            else:
                self._record_to_json(
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
    
    def _record_to_json(
        self,
        session_id: str,
        agent_type: str,
        agent_class: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int
    ):
        """记录到 JSON 文件"""
        if session_id not in self._json_data:
            self._json_data[session_id] = []
        
        record = {
            "session_id": session_id,
            "agent_type": agent_type,
            "agent_class": agent_class,
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "created_at": datetime.now().isoformat()
        }
        
        self._json_data[session_id].append(record)
        self._save_json_data()
    
    async def get_session_total(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的总 token 消耗
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 包含 input_tokens, output_tokens, total_tokens
        """
        try:
            if self.use_database:
                return await self._get_session_total_from_db(session_id)
            else:
                return self._get_session_total_from_json(session_id)
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
    
    def _get_session_total_from_json(self, session_id: str) -> Dict[str, Any]:
        """从 JSON 获取会话统计"""
        if session_id not in self._json_data:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        
        records = self._json_data[session_id]
        return {
            "input_tokens": sum(r.get("input_tokens", 0) for r in records),
            "output_tokens": sum(r.get("output_tokens", 0) for r in records),
            "total_tokens": sum(r.get("total_tokens", 0) for r in records)
        }
    
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
            if self.use_database:
                return await self._get_statistics_from_db(
                    session_id, agent_type, model_name, start_date, end_date, group_by
                )
            else:
                return self._get_statistics_from_json(
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
    
    def _get_statistics_from_json(
        self,
        session_id: Optional[str],
        agent_type: Optional[str],
        model_name: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        group_by: Optional[str]
    ) -> Dict[str, Any]:
        """从 JSON 获取统计"""
        all_records = []
        
        # 收集所有符合条件的记录
        for sess_id, records in self._json_data.items():
            if session_id and sess_id != session_id:
                continue
            
            for record in records:
                if agent_type and record.get("agent_type") != agent_type:
                    continue
                if model_name and record.get("model_name") != model_name:
                    continue
                
                created_at_str = record.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if start_date and created_at < start_date:
                            continue
                        if end_date and created_at > end_date:
                            continue
                    except:
                        pass
                
                all_records.append(record)
        
        # 计算总计
        total = {
            "input_tokens": sum(r.get("input_tokens", 0) for r in all_records),
            "output_tokens": sum(r.get("output_tokens", 0) for r in all_records),
            "total_tokens": sum(r.get("total_tokens", 0) for r in all_records)
        }
        
        if group_by:
            groups = {}
            for record in all_records:
                if group_by == "agent_type":
                    key = record.get("agent_type", "unknown")
                elif group_by == "model_name":
                    key = record.get("model_name", "unknown")
                elif group_by == "day":
                    created_at_str = record.get("created_at")
                    if created_at_str:
                        try:
                            key = datetime.fromisoformat(created_at_str).date().isoformat()
                        except:
                            key = "unknown"
                    else:
                        key = "unknown"
                else:
                    key = "all"
                
                if key not in groups:
                    groups[key] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                
                groups[key]["input_tokens"] += record.get("input_tokens", 0)
                groups[key]["output_tokens"] += record.get("output_tokens", 0)
                groups[key]["total_tokens"] += record.get("total_tokens", 0)
            
            return {
                "groups": [
                    {group_by: k, **v} for k, v in sorted(groups.items(), key=lambda x: x[1]["total_tokens"], reverse=True)
                ],
                "total": total
            }
        else:
            return {"total": total}


# 全局实例
_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """获取全局 TokenTracker 实例"""
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    return _token_tracker


