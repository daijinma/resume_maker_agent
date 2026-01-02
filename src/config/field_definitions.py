"""
字段定义配置
定义各 Worker 需要检查的字段及其优先级
"""
from typing import Dict, Any, List

# 字段路径到字段名的映射（用于返回简单字段名）
FIELD_NAME_MAPPING: Dict[str, str] = {
    # personal_info 字段
    "personal_info.name": "name",
    "personal_info.phone": "phone",
    "personal_info.email": "email",
    # education 字段
    "education[].school": "school",
    "education[].major": "major",
    "education[].degree": "degree",
    # experience 字段
    "experience[].company": "company",
    "experience[].role": "role",
    "experience[].period": "period",
    # skills 字段
    "skills[].category": "skills",
}

# 各 Worker 的字段定义
FIELD_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "info_worker": {
        "required_fields": [
            {"path": "personal_info.name", "priority": 1, "reason": "姓名是必填项"},
            {"path": "personal_info.phone", "priority": 2, "reason": "联系方式缺失"},
            {"path": "personal_info.email", "priority": 3, "reason": "邮箱缺失"},
        ],
        "optional_fields": []
    },
    "education_worker": {
        "required_fields": [
            {"path": "education[].school", "priority": 4, "reason": "教育背景-学校名称"},
            {"path": "education[].major", "priority": 5, "reason": "教育背景-专业信息"},
            {"path": "education[].degree", "priority": 6, "reason": "教育背景-学历信息"},
        ],
        "optional_fields": []
    },
    "experience_worker": {
        "required_fields": [
            {"path": "experience[].company", "priority": 7, "reason": "工作经历-公司名称"},
            {"path": "experience[].role", "priority": 8, "reason": "工作经历-职位"},
            {"path": "experience[].period", "priority": 9, "reason": "工作经历-时间"},
        ],
        "optional_fields": []
    },
    "skill_worker": {
        "required_fields": [
            {"path": "skills[].category", "priority": 11, "reason": "技能信息"},
        ],
        "optional_fields": []
    }
}

