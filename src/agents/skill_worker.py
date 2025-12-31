import json
import logging
from typing import Dict, Any
from src.agents.base import BaseAgent, time_it
from src.config.models import ModelConfig

logger = logging.getLogger("resume-agent.workers.skill")

class SkillWorker(BaseAgent):
    def __init__(self):
        super().__init__(model=ModelConfig.MODEL_SKILL_WORKER)

    @time_it
    async def process(self, user_input: str, current_data: Dict[str, Any], on_tool_call=None, session_id: str = None) -> Dict[str, Any]:
        system_prompt = self.load_prompt("skill_worker")
        user_prompt = f"用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        return await self.run_chain(system_prompt, user_prompt, on_tool_call=on_tool_call, session_id=session_id)
