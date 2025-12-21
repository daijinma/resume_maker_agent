import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    BASE_URL = "https://openrouter.ai/api/v1"
    
    # 模型选择策略
    # Planner: 要求响应极快，意图识别准确
    MODEL_PLANNER = "xiaomi/mimo-v2-flash:free"
    
    # Info Worker: 提取类任务，要求准确
    MODEL_INFO_WORKER = "xiaomi/mimo-v2-flash:free"
    
    # Experience Worker: 核心润色任务，要求极高的写作质量和逻辑
    MODEL_EXP_WORKER = "meta-llama/llama-3.3-70b-instruct:free"
    
    # Skill/Honors Worker: 分类与总结任务
    MODEL_SKILL_WORKER = "nvidia/nemotron-3-nano-30b-a3b:free"
    
    # Aggregator: 聚合与格式化，要求 JSON 稳定性
    MODEL_AGGREGATOR = "nex-agi/deepseek-v3.1-nex-n1:free"

    DEFAULT_HEADERS = {
        "HTTP-Referer": "https://github.com/copilot",
        "X-Title": "Resume Multi-Agent System",
    }
