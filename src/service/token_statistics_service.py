"""
Token 统计服务
提供多维度 token 使用统计查询
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from src.utils.token_tracker import get_token_tracker

logger = logging.getLogger("service.token_statistics")


class TokenStatisticsService:
    """Token 统计服务"""
    
    def __init__(self):
        self.token_tracker = get_token_tracker()
    
    async def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的 token 统计
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 包含总 token 使用情况
        """
        try:
            total = await self.token_tracker.get_session_total(session_id)
            
            # 获取详细记录（按 agent_type 分组）
            agent_stats = await self.token_tracker.get_statistics(
                session_id=session_id,
                group_by="agent_type"
            )
            
            # 获取按模型分组的统计
            model_stats = await self.token_tracker.get_statistics(
                session_id=session_id,
                group_by="model_name"
            )
            
            return {
                "session_id": session_id,
                "total": total,
                "by_agent_type": agent_stats.get("groups", []),
                "by_model": model_stats.get("groups", []),
                "summary": {
                    "input_tokens": total["input_tokens"],
                    "output_tokens": total["output_tokens"],
                    "total_tokens": total["total_tokens"],
                    "agent_types_count": len(agent_stats.get("groups", [])),
                    "models_count": len(model_stats.get("groups", []))
                }
            }
        except Exception as e:
            logger.error(f"获取会话统计失败: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "total": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "by_agent_type": [],
                "by_model": [],
                "error": str(e)
            }
    
    async def get_agent_statistics(
        self,
        agent_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        按 Agent 类型统计
        
        Args:
            agent_type: Agent 类型（可选，不提供则统计所有）
            start_date: 开始时间
            end_date: 结束时间
            
        Returns:
            Dict: 统计结果
        """
        try:
            result = await self.token_tracker.get_statistics(
                agent_type=agent_type,
                start_date=start_date,
                end_date=end_date,
                group_by="agent_type" if not agent_type else None
            )
            
            if agent_type:
                # 单个 agent 类型，返回总计
                return {
                    "agent_type": agent_type,
                    "statistics": result.get("total", {}),
                    "time_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None
                    }
                }
            else:
                # 所有 agent 类型，返回分组统计
                return {
                    "statistics": result,
                    "time_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None
                    }
                }
        except Exception as e:
            logger.error(f"获取 Agent 统计失败: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_model_statistics(
        self,
        model_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        按模型统计
        
        Args:
            model_name: 模型名称（可选，不提供则统计所有）
            start_date: 开始时间
            end_date: 结束时间
            
        Returns:
            Dict: 统计结果
        """
        try:
            result = await self.token_tracker.get_statistics(
                model_name=model_name,
                start_date=start_date,
                end_date=end_date,
                group_by="model_name" if not model_name else None
            )
            
            if model_name:
                # 单个模型，返回总计
                return {
                    "model_name": model_name,
                    "statistics": result.get("total", {}),
                    "time_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None
                    }
                }
            else:
                # 所有模型，返回分组统计
                return {
                    "statistics": result,
                    "time_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None
                    }
                }
        except Exception as e:
            logger.error(f"获取模型统计失败: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_time_statistics(
        self,
        time_range: str = "day",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        按时间统计
        
        Args:
            time_range: 时间范围分组（day, week, month）
            start_date: 开始时间（默认：30天前）
            end_date: 结束时间（默认：现在）
            
        Returns:
            Dict: 统计结果
        """
        try:
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                if time_range == "day":
                    start_date = end_date - timedelta(days=30)
                elif time_range == "week":
                    start_date = end_date - timedelta(weeks=12)
                elif time_range == "month":
                    start_date = end_date - timedelta(days=365)
                else:
                    start_date = end_date - timedelta(days=30)
            
            result = await self.token_tracker.get_statistics(
                start_date=start_date,
                end_date=end_date,
                group_by=time_range
            )
            
            return {
                "time_range": time_range,
                "statistics": result,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"获取时间统计失败: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_all_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取综合统计
        
        Args:
            start_date: 开始时间
            end_date: 结束时间
            
        Returns:
            Dict: 包含所有维度的统计
        """
        try:
            # 总体统计
            total_stats = await self.token_tracker.get_statistics(
                start_date=start_date,
                end_date=end_date
            )
            
            # 按 Agent 类型统计
            agent_stats = await self.token_tracker.get_statistics(
                start_date=start_date,
                end_date=end_date,
                group_by="agent_type"
            )
            
            # 按模型统计
            model_stats = await self.token_tracker.get_statistics(
                start_date=start_date,
                end_date=end_date,
                group_by="model_name"
            )
            
            # 按天统计（最近30天）
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            daily_stats = await self.token_tracker.get_statistics(
                start_date=start_date,
                end_date=end_date,
                group_by="day"
            )
            
            return {
                "summary": total_stats.get("total", {}),
                "by_agent_type": agent_stats.get("groups", []),
                "by_model": model_stats.get("groups", []),
                "by_day": daily_stats.get("groups", []),
                "time_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            logger.error(f"获取综合统计失败: {e}", exc_info=True)
            return {"error": str(e)}


