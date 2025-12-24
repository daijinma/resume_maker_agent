import json
import logging
from typing import Dict, Any
from src.agent.base import BaseAgent, time_it
from src.agent.tools import RESUME_TOOLS
from src.config import Config

logger = logging.getLogger("resume-agent.workers.info")

class InfoWorker(BaseAgent):
    def __init__(self):
        # 优化：不再将工具绑定到 LLM，减少 round-trip 延迟
        super().__init__(model=Config.MODEL_INFO_WORKER, tools=[])

    @time_it
    async def process(self, user_input: str, current_data: Dict[str, Any], on_tool_call=None) -> Dict[str, Any]:
        system_prompt = self.load_prompt("info_worker")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        user_prompt = f"当前日期: {current_date}\n用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        
        result = await self.run_chain(system_prompt, user_prompt, on_tool_call=on_tool_call)
        
        # 优化：本地 Python 逻辑处理日期预测，代替 LLM 工具调用
        if "education" in result and isinstance(result["education"], list):
            from src.agent.tools import edu_date_predictor
            for edu in result["education"]:
                duration = edu.get("duration", "")
                degree = edu.get("degree", "")
                # 如果只有开始时间，尝试本地预测结束时间
                if duration and "-" not in duration and degree:
                    predicted = edu_date_predictor(duration, degree)
                    if "无法预测" not in predicted:
                        edu["duration"] = f"{duration} - {predicted} (预计)"
                        logger.info(f"本地预测教育时间: {edu['duration']}")
        
        return result
