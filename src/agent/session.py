import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("resume-agent.session")

class SessionManager:
    """
    会话管理器：
    负责将用户的对话状态（slots, pending_questions 等）持久化到本地 JSON 文件中。
    """
    def __init__(self, storage_path: str = "sessions.json") -> None:
        self.storage_path = storage_path
        self.sessions: Dict[str, Any] = self._load_sessions()

    def _load_sessions(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载会话文件失败: {e}")
        return {}

    def save_session(self, session_id: str, data: Any) -> None:
        """保存特定会话的数据"""
        # 将 PlannerState 对象转换为字典存储
        if hasattr(data, "__dict__"):
            self.sessions[session_id] = data.__dict__
        else:
            self.sessions[session_id] = data
            
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存会话文件失败: {e}")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """获取特定会话的数据，如果不存在则返回初始结构"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "resume_data": {
                    "personal_info": {},
                    "education": [],
                    "experience": [],
                    "skills": []
                },
                "history": []
            }
        return self.sessions[session_id]
