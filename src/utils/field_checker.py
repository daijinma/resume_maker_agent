"""
缺失字段检查工具
检查简历数据中缺失的字段，返回简单字符串数组
"""
import logging
from typing import Dict, Any, List, Optional
from src.config.field_definitions import FIELD_NAME_MAPPING

logger = logging.getLogger("resume-agent.field_checker")


def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """
    根据路径获取嵌套字典的值
    
    Args:
        data: 数据字典
        path: 字段路径，如 "personal_info.phone" 或 "experience[].company"
    
    Returns:
        字段值，如果不存在返回 None
    """
    if not path:
        return None
    
    # 处理数组字段路径（如 "experience[].company"）
    if "[].]" in path:
        # 提取数组路径和字段名
        array_path, field_name = path.split("[].", 1)
        
        # 获取数组
        parts = array_path.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        # 检查数组是否存在且至少有一个元素
        if not isinstance(current, list) or len(current) == 0:
            return None
        
        # 检查数组中至少一个元素有该字段且不为空
        for item in current:
            if isinstance(item, dict) and field_name in item:
                value = item[field_name]
                if value and (not isinstance(value, str) or value.strip()):
                    return value
        return None
    
    # 处理普通嵌套路径（如 "personal_info.phone"）
    parts = path.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    
    return current


def check_missing_fields(
    data: Dict[str, Any], 
    field_definitions: Dict[str, Any]
) -> List[str]:
    """
    检查缺失的字段，返回简单字符串数组
    
    Args:
        data: 简历数据
        field_definitions: 字段定义（包含 required_fields 和 optional_fields）
    
    Returns:
        缺失字段的简单名称列表，如 ["phone", "email"]
    """
    missing_fields = []
    
    # 检查必填字段
    required_fields = field_definitions.get("required_fields", [])
    for field_def in required_fields:
        path = field_def.get("path", "")
        if not path:
            continue
        
        value = get_nested_value(data, path)
        
        # 判断是否缺失
        is_missing = False
        if value is None:
            is_missing = True
        elif isinstance(value, str) and not value.strip():
            is_missing = True
        elif isinstance(value, list) and len(value) == 0:
            is_missing = True
        
        if is_missing:
            # 映射到简单字段名
            field_name = FIELD_NAME_MAPPING.get(path, path.split(".")[-1].replace("[]", ""))
            if field_name not in missing_fields:
                missing_fields.append(field_name)
                logger.debug(f"检测到缺失字段: {path} -> {field_name}")
    
    return missing_fields

