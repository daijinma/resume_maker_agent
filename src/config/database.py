"""
数据库配置
"""
import os
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfig:
    """数据库配置"""
    # 数据库连接配置
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://resume_agent:resume_agent_pass@localhost:5432/resume_agent_db"
    )
    
    # 连接池配置
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    DB_MIN_SIZE = int(os.getenv("DB_MIN_SIZE", "2"))

