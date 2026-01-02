import json
import logging
from typing import Dict, Any
from src.agents.base import BaseAgent, time_it
from src.config.models import ModelConfig

logger = logging.getLogger("resume-agent.inference")

class InferenceWorker(BaseAgent):
    def __init__(self):
        # 使用推理模型配置
        config = ModelConfig.get_model_config("inference")
        super().__init__(
            models=config["models"],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens"),
            timeout=config.get("timeout"),
            initial_model_index=config.get("initial_model_index")
        )

    @time_it
    async def analyze(self, resume_data: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
        """
        分析简历数据的逻辑性和常识性。
        
        Args:
            resume_data: 简历数据
            session_id: 会话ID（用于 token 追踪）
        """
        system_prompt = self.load_prompt("inference_worker")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        user_prompt = f"当前日期: {current_date}\n当前简历数据: {json.dumps(resume_data, ensure_ascii=False)}"
        
        try:
            result = await self.run_chain(system_prompt, user_prompt, session_id=session_id)
            return result
        except Exception as e:
            logger.error(f"推理分析失败: {e}")
            return {"insights": [], "summary": "分析失败"}
