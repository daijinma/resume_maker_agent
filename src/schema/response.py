"""
响应模型
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class ChatResponse(BaseModel):
    """聊天响应"""
    reply: str
    status: str
    data: Optional[Dict[str, Any]] = None


class GenerateResponse(BaseModel):
    """生成简历响应"""
    status: str
    result: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class StreamResponse(BaseModel):
    """流式响应"""
    type: str  # 'status', 'partial', 'final', 'error'
    content: str
    debug: Optional[Dict[str, Any]] = None
    pending_questions: Optional[List[str]] = None

