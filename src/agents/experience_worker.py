import logging
from src.agents.unified_worker import UnifiedWorker
from src.agents.tools import RESUME_TOOLS
from src.config.models import ModelConfig
from src.config.field_definitions import FIELD_DEFINITIONS

logger = logging.getLogger("resume-agent.workers.experience")


class ExperienceWorker(UnifiedWorker):
    """工作经历处理 Worker"""
    
    def __init__(self):
        config = ModelConfig.get_model_config("experience_worker")
        field_defs = FIELD_DEFINITIONS["experience_worker"]
        super().__init__(
            worker_type="experience",
            models=config["models"],
            prompt_name="experience_worker",
            field_definitions=field_defs,
            tools=RESUME_TOOLS,
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens"),
            timeout=config.get("timeout"),
            initial_model_index=config.get("initial_model_index")
        )
