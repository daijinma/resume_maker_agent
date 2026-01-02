"""
应用配置
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """应用设置"""
    # 应用基本信息
    APP_NAME = "Resume Agent"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # 默认 Agent 类型
    DEFAULT_AGENT_TYPE = os.getenv("DEFAULT_AGENT_TYPE", "planner_worker")

