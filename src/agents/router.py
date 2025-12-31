import json
import logging
from typing import Dict, Any, List
from src.agents.base import BaseAgent, time_it
from src.config.models import ModelConfig

logger = logging.getLogger("resume-agent.router")

class Router(BaseAgent):
    def __init__(self):
        super().__init__(model=ModelConfig.MODEL_PLANNER)

    @time_it
    async def route(self, user_input: str, session_data: Dict[str, Any], last_question: str = None, session_id: str = None) -> Dict[str, Any]:
        """
        分析用户输入，决定下一步动作
        
        Args:
            user_input: 用户输入
            session_data: 会话数据
            last_question: 上一轮问题
            session_id: 会话ID（用于 token 追踪）
        """
        system_prompt = self.load_prompt("router")
        
        context_str = ""
        if last_question:
            context_str = f"上一轮 AI 提问: {last_question}\n"
            
        user_prompt = f"{context_str}用户输入: {user_input}\n当前会话状态: {json.dumps(session_data.get('resume_data', {}), ensure_ascii=False)}"
        
        return await self.run_chain(system_prompt, user_prompt, session_id=session_id)
