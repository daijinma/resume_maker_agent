"""
数据库工具
"""
import asyncpg
from typing import Optional
from src.config.database import DatabaseConfig


async def create_db_pool(
    database_url: Optional[str] = None,
    min_size: int = 2,
    max_size: int = 10
) -> asyncpg.Pool:
    """创建数据库连接池"""
    url = database_url or DatabaseConfig.DATABASE_URL
    pool = await asyncpg.create_pool(
        url,
        min_size=min_size,
        max_size=max_size
    )
    return pool

