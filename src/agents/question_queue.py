"""
问题队列管理器 (QuestionQueue)

负责管理问题的优先级排序、去重、提取等操作。
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger("dual-track.question_queue")


class QuestionQueue:
    """问题队列管理器"""
    
    # 字段优先级映射
    FIELD_PRIORITY = {
        "name": 1,
        "phone": 2,
        "email": 3,
        "school": 4,
        "major": 5,
        "degree": 6,
        "experience": 7,
        "skills": 11,
    }
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.questions: List[Dict[str, Any]] = []
        self.answered: List[str] = []
    
    def add_question(
        self, 
        question_id: str,
        content: str,
        field: Optional[str] = None,
        reason: Optional[str] = None,
        priority: Optional[int] = None
    ) -> bool:
        """
        添加问题到队列
        
        Args:
            question_id: 问题唯一标识
            content: 问题内容
            field: 相关字段名
            reason: 提问原因
            priority: 优先级（如果为 None，则根据 field 自动计算）
        
        Returns:
            bool: 是否成功添加（如果已存在则返回 False）
        """
        # 检查是否已存在
        if any(q["id"] == question_id for q in self.questions):
            logger.debug(f"问题 {question_id} 已存在，跳过")
            return False
        
        # 计算优先级
        if priority is None:
            priority = self.FIELD_PRIORITY.get(field, 99) if field else 99
        
        question = {
            "id": question_id,
            "content": content,
            "priority": priority,
            "field": field,
            "reason": reason,
            "created_at": datetime.now().isoformat()
        }
        
        self.questions.append(question)
        self._sort_by_priority()
        logger.info(f"已添加问题: {question_id} (优先级: {priority})")
        return True
    
    def get_next_question(self, limit: int = 1) -> List[Dict[str, Any]]:
        """
        获取下一个待提问的问题
        
        Args:
            limit: 返回问题数量
        
        Returns:
            List[Dict]: 问题列表
        """
        unanswered = [
            q for q in self.questions 
            if q["id"] not in self.answered
        ]
        return unanswered[:limit]
    
    def mark_answered(self, question_id: str):
        """标记问题为已回答"""
        if question_id not in self.answered:
            self.answered.append(question_id)
            logger.info(f"问题 {question_id} 已标记为已回答")
    
    def remove_question(self, question_id: str):
        """移除问题"""
        self.questions = [q for q in self.questions if q["id"] != question_id]
        if question_id in self.answered:
            self.answered.remove(question_id)
        logger.info(f"已移除问题: {question_id}")
    
    def deduplicate(self):
        """去重：相同字段只保留优先级最高的问题"""
        field_questions: Dict[str, Dict] = {}
        
        for q in self.questions:
            if q["id"] in self.answered:
                continue
            
            field = q.get("field")
            if not field:
                continue
            
            if field not in field_questions:
                field_questions[field] = q
            else:
                # 保留优先级更高的
                if q["priority"] < field_questions[field]["priority"]:
                    field_questions[field] = q
        
        # 更新问题列表
        other_questions = [
            q for q in self.questions 
            if not q.get("field") or q["id"] in self.answered
        ]
        
        self.questions = list(field_questions.values()) + other_questions
        self._sort_by_priority()
        logger.info("已完成问题去重")
    
    def _sort_by_priority(self):
        """按优先级排序"""
        self.questions.sort(key=lambda x: (x["priority"], x["created_at"]))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于存储）"""
        return {
            "questions": self.questions,
            "answered": self.answered,
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_questions": len(self.questions),
                "answered_count": len(self.answered)
            }
        }
    
    @classmethod
    def from_dict(cls, session_id: str, data: Dict[str, Any]) -> "QuestionQueue":
        """从字典创建实例"""
        queue = cls(session_id)
        queue.questions = data.get("questions", [])
        queue.answered = data.get("answered", [])
        return queue
    
    def clear_answered(self):
        """清除已回答的问题"""
        self.questions = [q for q in self.questions if q["id"] not in self.answered]
        self.answered = []
        logger.info("已清除已回答的问题")

