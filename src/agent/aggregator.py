import json
import logging
from typing import Dict, Any
from src.agent.base import BaseAgent, time_it
from src.config import Config

logger = logging.getLogger("resume-agent.aggregator")

class Aggregator(BaseAgent):
    def __init__(self):
        super().__init__(model=Config.MODEL_AGGREGATOR)

    @time_it
    async def aggregate(self, session_data: Dict[str, Any], last_intent: str, pending_questions: Any = None) -> str:
        """
        汇总所有信息，生成给用户的回复。
        """
        system_prompt = self.load_prompt("aggregator")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        user_prompt = f"当前日期: {current_date}"
        
        # 这里不需要 JSON 模式，直接返回对话文本
        return await self.run_chain(
            system_prompt, 
            user_prompt, 
            json_mode=False,
            resume_data=json.dumps(session_data.get('resume_data', {}), ensure_ascii=False),
            inference_insights=json.dumps(session_data.get('inference_insights', []), ensure_ascii=False),
            last_intent=last_intent,
            pending_questions=json.dumps(pending_questions if pending_questions is not None else session_data.get('pending_questions', []), ensure_ascii=False)
        )
