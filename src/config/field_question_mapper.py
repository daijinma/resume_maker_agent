"""
字段优先级配置
用于 Dual-Track 模式对缺失字段进行优先级排序
"""
from typing import Dict

# 字段优先级映射（数字越小优先级越高）
FIELD_PRIORITY: Dict[str, int] = {
    "name": 1,
    "phone": 2,
    "email": 3,
    "school": 4,
    "major": 5,
    "degree": 6,
    "company": 7,
    "role": 8,
    "period": 9,
    "skills": 11,
}

