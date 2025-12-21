import json
import logging
from typing import Dict, Any
from src.agent.base import BaseAgent, time_it
from src.config import Config

logger = logging.getLogger("resume-agent.inference")

class InferenceWorker(BaseAgent):
    def __init__(self):
        super().__init__(model=Config.MODEL_PLANNER) # 使用较强的模型进行逻辑分析

    @time_it
    async def analyze(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析简历数据的逻辑性和常识性。
        """
        system_prompt = self.load_prompt("inference_worker")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        user_prompt = f"当前日期: {current_date}\n当前简历数据: {json.dumps(resume_data, ensure_ascii=False)}"
        
        try:
            result = await self.run_chain(system_prompt, user_prompt)
            return result
        except Exception as e:
            logger.error(f"推理分析失败: {e}")
            return {"insights": [], "summary": "分析失败"}
