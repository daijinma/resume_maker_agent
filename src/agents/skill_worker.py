import logging
from src.agents.unified_worker import UnifiedWorker
from src.config.models import ModelConfig
from src.config.field_definitions import FIELD_DEFINITIONS

logger = logging.getLogger("resume-agent.workers.skill")


class SkillWorker(UnifiedWorker):
    """技能处理 Worker"""
    
    def __init__(self):
        config = ModelConfig.get_model_config("skill_worker")
        field_defs = FIELD_DEFINITIONS["skill_worker"]
        super().__init__(
            worker_type="skill",
            models=config["models"],
            prompt_name="skill_worker",
            field_definitions=field_defs,
            tools=[],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens"),
            timeout=config.get("timeout"),
            initial_model_index=config.get("initial_model_index")
        )
