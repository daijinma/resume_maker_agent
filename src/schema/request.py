"""
请求模型
"""
from pydantic import BaseModel
from typing import Optional, Literal
from .session import AgentType


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[str] = "default"
    agent_type: Optional[AgentType] = AgentType.PLANNER_WORKER


class GenerateRequest(BaseModel):
    """生成简历请求"""
    session_id: Optional[str] = "default"


class StreamRequest(BaseModel):
    """统一的流式请求"""
    action: Literal["chat", "generate", "history", "reasoning_status", "token_stats", "token_summary"]
    session_id: Optional[str] = "default"
    agent_type: Optional[AgentType] = AgentType.PLANNER_WORKER
    message: Optional[str] = None  # chat 操作需要
    limit: Optional[int] = 50  # history 操作需要
    # token_stats 相关参数
    token_agent_type: Optional[str] = None
    token_model: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    group_by: Optional[str] = None

