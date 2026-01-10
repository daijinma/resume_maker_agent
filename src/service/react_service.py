"""
ReAct Service - ReAct 模式服务
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from src.agents.react_agent import ReActAgent
from src.agents.react_tools import REACT_TOOLS
from src.config.models import ModelConfig
from .session_service import SessionService

logger = logging.getLogger("service.react")


class ReActService:
    """ReAct 模式服务"""
    
    def __init__(self, session_service: SessionService):
        """
        初始化 ReAct 服务
        
        Args:
            session_service: 会话服务
        """
        self.session_service = session_service
        
        # 获取 react_agent 模型配置
        react_config = ModelConfig.get_model_config("react_agent")
        
        # 创建 ReAct Agent（带工具）
        self.react_agent = ReActAgent(
            models=react_config.get("models", ["meta-llama/llama-3.3-70b-instruct:free"]),
            temperature=react_config.get("temperature", 0.7),
            max_tokens=react_config.get("max_tokens", 8192),
            timeout=react_config.get("timeout", 60.0),
            max_iterations=react_config.get("max_iterations", 5),
            tools=REACT_TOOLS
        )
    
    async def process_message(
        self,
        session_id: str,
        user_input: str,
        on_tool_call: Optional[Callable] = None,
        on_sse_event: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            session_id: 会话 ID
            user_input: 用户输入
            on_tool_call: 工具调用回调
            on_sse_event: SSE事件回调函数
        
        Returns:
            Dict: 处理结果
        """
        # 1. 保存用户消息到历史
        await self.session_service.add_message(
            session_id, "user", user_input, "react"
        )
        
        # 2. 获取会话数据和历史记录
        session_data = await self.session_service.get_session(session_id)
        history = await self.session_service.get_history(session_id, limit=20)
        
        # 3. 构建对话历史（转换为模型需要的格式）
        conversation_history = []
        for msg in history[:-1]:  # 排除最后一条（当前用户消息）
            if msg.get("role") in ["user", "assistant"]:
                conversation_history.append({
                    "role": msg["role"],
                    "content": msg.get("content", "")
                })
        
        # 4. 发送 SSE 事件：开始处理
        if on_sse_event:
            try:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("model_request", {
                        "agent_type": "react",
                        "agent_class": "ReActService",
                        "model_name": self.react_agent.model_name
                    })
                else:
                    on_sse_event("model_request", {
                        "agent_type": "react",
                        "agent_class": "ReActService",
                        "model_name": self.react_agent.model_name
                    })
            except Exception as e:
                logger.warning(f"发送模型请求事件失败: {e}")
        
        # 5. 执行 ReAct 循环
        try:
            result = await self.react_agent.run_react_loop(
                user_question=user_input,
                session_id=session_id,
                on_sse_event=on_sse_event,
                conversation_history=conversation_history
            )
            
            # 提取答案
            response_text = result.get("answer", "")
            
        except Exception as e:
            logger.error(f"ReAct 循环失败: {e}", exc_info=True)
            response_text = f"抱歉，处理您的消息时出现了错误：{str(e)}"
            result = {
                "answer": response_text,
                "iterations": 0,
                "total_tokens": {"input": 0, "output": 0, "total": 0},
                "total_duration": 0.0
            }
        
        # 6. 发送 SSE 事件：处理完成
        if on_sse_event:
            try:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("model_response", {
                        "agent_type": "react",
                        "agent_class": "ReActService",
                        "model_name": self.react_agent.model_name,
                        "duration": result.get("total_duration", 0.0),
                        "input_tokens": result.get("total_tokens", {}).get("input", 0),
                        "output_tokens": result.get("total_tokens", {}).get("output", 0),
                        "total_tokens": result.get("total_tokens", {}).get("total", 0),
                        "iterations": result.get("iterations", 0)
                    })
                else:
                    on_sse_event("model_response", {
                        "agent_type": "react",
                        "agent_class": "ReActService",
                        "model_name": self.react_agent.model_name,
                        "duration": result.get("total_duration", 0.0),
                        "input_tokens": result.get("total_tokens", {}).get("input", 0),
                        "output_tokens": result.get("total_tokens", {}).get("output", 0),
                        "total_tokens": result.get("total_tokens", {}).get("total", 0),
                        "iterations": result.get("iterations", 0)
                    })
            except Exception as e:
                logger.warning(f"发送模型响应事件失败: {e}")
        
        # 7. 保存 AI 响应到历史
        await self.session_service.add_message(
            session_id, "assistant", response_text, "react"
        )
        
        # 8. 保存会话
        session_data["last_question"] = response_text
        session_data["agent_type"] = "react"
        await self.session_service.save_session(session_id, session_data)
        
        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
            "agent_type": "react",
            "debug": {
                "model": self.react_agent.model_name,
                "duration": result.get("total_duration", 0.0),
                "iterations": result.get("iterations", 0),
                "total_tokens": result.get("total_tokens", {}).get("total", 0),
                "steps": result.get("steps", [])
            }
        }

