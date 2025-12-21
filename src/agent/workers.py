import json
import logging
from typing import Dict, Any
from src.agent.base import BaseAgent, time_it
from src.agent.tools import RESUME_TOOLS
from src.config import Config

logger = logging.getLogger("resume-agent.workers")

class InfoWorker(BaseAgent):
    def __init__(self):
        super().__init__(model=Config.MODEL_INFO_WORKER, tools=RESUME_TOOLS)

    @time_it
    async def process(self, user_input: str, current_data: Dict[str, Any], on_tool_call=None) -> Dict[str, Any]:
        system_prompt = self.load_prompt("info_worker")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        user_prompt = f"当前日期: {current_date}\n用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        return await self.run_chain(system_prompt, user_prompt, on_tool_call=on_tool_call)

class ExperienceWorker(BaseAgent):
    def __init__(self):
        super().__init__(model=Config.MODEL_EXP_WORKER, tools=RESUME_TOOLS)

    @time_it
    async def process(self, user_input: str, current_data: Dict[str, Any], on_tool_call=None) -> Dict[str, Any]:
        system_prompt = self.load_prompt("experience_worker")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        user_prompt = f"当前日期: {current_date}\n用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        return await self.run_chain(system_prompt, user_prompt, on_tool_call=on_tool_call)

class SkillWorker(BaseAgent):
    def __init__(self):
        super().__init__(model=Config.MODEL_SKILL_WORKER)

    @time_it
    async def process(self, user_input: str, current_data: Dict[str, Any], on_tool_call=None) -> Dict[str, Any]:
        system_prompt = self.load_prompt("skill_worker")
        user_prompt = f"用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        return await self.run_chain(system_prompt, user_prompt, on_tool_call=on_tool_call)
