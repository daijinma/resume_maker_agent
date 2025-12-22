from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    reply: str
    status: str
    data: Optional[Dict[str, Any]] = None

class GenerateRequest(BaseModel):
    session_id: Optional[str] = "default"

class GenerateResponse(BaseModel):
    status: str
    result: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
