"""
辅助函数
"""
import json
from typing import Dict, Any


def deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """深度合并字典"""
    for k, v in source.items():
        if k in target and isinstance(target[k], list) and isinstance(v, list):
            existing = [json.dumps(i, sort_keys=True) for i in target[k]]
            for item in v:
                if json.dumps(item, sort_keys=True) not in existing:
                    target[k].append(item)
        elif k in target and isinstance(target[k], dict) and isinstance(v, dict):
            deep_merge(target[k], v)
        else:
            target[k] = v


def has_data_changed(session_data: Dict[str, Any]) -> bool:
    """检查数据是否发生变化"""
    resume = session_data.get("resume_data", {})
    current_hash = hash(json.dumps({
        "edu": len(resume.get("education", [])),
        "exp": len(resume.get("experience", [])),
        "skills": len(resume.get("skills", [])),
        "personal": bool(resume.get("personal_info", {}).get("name"))
    }, sort_keys=True))
    
    changed = session_data.get("last_resume_hash") != current_hash
    session_data["last_resume_hash"] = current_hash
    return changed

