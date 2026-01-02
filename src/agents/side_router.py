import json
import logging
from typing import Dict, Any, List, Optional, Callable
from src.agents.base import BaseAgent, time_it
from src.config.models import ModelConfig

logger = logging.getLogger("resume-agent.side_router")


class SideRouter(BaseAgent):
    """Side-Router Agent：判断是否应该用口语化/转折话术直接提问"""
    
    def __init__(self):
        config = ModelConfig.get_model_config("side_router")
        super().__init__(
            models=config["models"],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 1024),
            timeout=config.get("timeout", 15.0),
            initial_model_index=config.get("initial_model_index")
        )

    @time_it
    async def route(
        self,
        user_input: str,
        session_data: Dict[str, Any],
        pending_questions: List[Dict[str, Any]],
        conversation_history: List[Dict[str, Any]],
        session_id: str = None,
        on_sse_event: Optional[Callable] = None
    ) -> str:
        """
        判断是否应该用口语化/转折话术直接提问
        
        Args:
            user_input: 用户输入
            session_data: 会话数据
            pending_questions: 待提问的问题列表
            conversation_history: 对话历史（最近5轮）
            session_id: 会话ID（用于 token 追踪）
            on_sse_event: SSE事件回调函数
        
        Returns:
            str: 如果场景合适，返回话术+question；如果不合适，返回空字符串
        """
        system_prompt = self.load_prompt("side_router")
        
        # 构建用户 prompt
        user_prompt_parts = []
        
        # 添加待提问问题
        if pending_questions:
            questions_text = "\n".join([
                f"- {q.get('content', '')} (字段: {q.get('field', 'unknown')}, 原因: {q.get('reason', '')})"
                for q in pending_questions
            ])
            user_prompt_parts.append(f"待提问的问题：\n{questions_text}")
        
        # 添加对话历史
        if conversation_history:
            history_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in conversation_history[-5:]
            ])
            user_prompt_parts.append(f"最近对话历史：\n{history_text}")
        
        # 添加用户输入
        user_prompt_parts.append(f"用户最新输入：{user_input}")
        
        # 添加简历数据
        user_prompt_parts.append(f"当前简历数据：{json.dumps(session_data.get('resume_data', {}), ensure_ascii=False)}")
        
        user_prompt = "\n\n".join(user_prompt_parts)
        
        # 调用模型，不使用 JSON 模式，直接返回文本
        response = await self.run_chain(
            system_prompt,
            user_prompt,
            json_mode=False,
            session_id=session_id,
            on_sse_event=on_sse_event
        )
        
        # 如果返回空字符串或只包含空白字符，返回空字符串
        if not response or not response.strip():
            return ""
        
        return response.strip()

