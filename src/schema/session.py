"""
会话模型
"""
from enum import Enum


class AgentType(str, Enum):
    """Agent 类型枚举"""
    PLANNER_WORKER = "planner_worker"  # Planner-Worker 架构（现有的）
    DUAL_TRACK = "dual_track"  # 双轨架构（新的）
    SIMPLE_CHAT = "simple_chat"  # 无架构，简单聊天（使用 gemini）

