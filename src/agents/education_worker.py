import logging
from typing import Dict, Any
from src.agents.unified_worker import UnifiedWorker
from src.config.models import ModelConfig
from src.config.field_definitions import FIELD_DEFINITIONS

logger = logging.getLogger("resume-agent.workers.education")


class EducationWorker(UnifiedWorker):
    """教育背景处理 Worker"""
    
    def __init__(self):
        config = ModelConfig.get_model_config("education_worker")
        field_defs = FIELD_DEFINITIONS["education_worker"]
        super().__init__(
            worker_type="education",
            models=config["models"],
            prompt_name="education_worker",
            field_definitions=field_defs,
            tools=[],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens"),
            timeout=config.get("timeout"),
            initial_model_index=config.get("initial_model_index")
        )
    
    async def post_process(
        self, 
        extracted_data: Dict[str, Any], 
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        后处理：本地 Python 逻辑处理日期预测
        """
        # 优化：本地 Python 逻辑处理日期预测，代替 LLM 工具调用
        if "education" in extracted_data and isinstance(extracted_data["education"], list):
            from src.agents.tools import edu_date_predictor
            for edu in extracted_data["education"]:
                duration = edu.get("duration", "")
                degree = edu.get("degree", "")
                # 如果只有开始时间，尝试本地预测结束时间
                if duration and "-" not in duration and degree:
                    predicted = await edu_date_predictor.ainvoke({"start_date": duration, "degree_type": degree})
                    if "无法预测" not in predicted:
                        edu["duration"] = f"{duration} - {predicted} (预计)"
                        logger.info(f"本地预测教育时间: {edu['duration']}")
        
        return extracted_data

