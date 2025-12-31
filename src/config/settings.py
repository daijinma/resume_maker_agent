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
    
    # 是否使用数据库
    USE_DATABASE = os.getenv("USE_DATABASE", "true").lower() == "true"
    
    # 会话存储路径（JSON 模式）
    SESSION_STORAGE_PATH = os.getenv("SESSION_STORAGE_PATH", "sessions.json")

