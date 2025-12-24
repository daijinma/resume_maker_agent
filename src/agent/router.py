import json
import logging
from typing import Dict, Any, List
from src.agent.base import BaseAgent, time_it
from src.config import Config

logger = logging.getLogger("resume-agent.router")

class Router(BaseAgent):
    def __init__(self):
        super().__init__(model=Config.MODEL_PLANNER)

    @time_it
    async def route(self, user_input: str, session_data: Dict[str, Any], last_question: str = None) -> Dict[str, Any]:
        """
        分析用户输入，决定下一步动作
        """
        system_prompt = self.load_prompt("router")
        
        context_str = ""
        if last_question:
            context_str = f"上一轮 AI 提问: {last_question}\n"
            
        user_prompt = f"{context_str}用户输入: {user_input}\n当前会话状态: {json.dumps(session_data.get('resume_data', {}), ensure_ascii=False)}"
        
        return await self.run_chain(system_prompt, user_prompt)
