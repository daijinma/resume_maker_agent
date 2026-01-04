"""
Simple Chat 服务 - 无架构，直接使用 Gemini 进行普通聊天
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from src.agents.base import BaseAgent
from src.config.models import ModelConfig
from .session_service import SessionService

logger = logging.getLogger("service.simple_chat")


class SimpleChatService:
    """Simple Chat 服务 - 无架构聊天"""
    
    def __init__(self, session_service: SessionService):
        """
        初始化 Simple Chat 服务
        
        Args:
            session_service: 会话服务
        """
        self.session_service = session_service
        
        # 获取 simple_chat 模型配置
        chat_config = ModelConfig.get_model_config("simple_chat")
        
        # 创建聊天 Agent
        self.chat_agent = BaseAgent(
            models=chat_config["models"],
            temperature=chat_config.get("temperature", 0.7),
            max_tokens=chat_config.get("max_tokens", 8192),
            timeout=chat_config.get("timeout", 60.0)
        )
        
        # 加载提示词
        self.system_prompt = self._load_prompt()
    
    def _load_prompt(self) -> str:
        """加载 simple_chat 提示词"""
        prompt_path = Path(__file__).parent.parent / "prompts" / "simple_chat.md"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"无法加载 simple_chat 提示词: {e}，使用默认提示词")
            return "你是一位友好、专业、知识渊博的 AI 助手。你的目标是帮助用户解决各种问题，进行自然流畅的对话。"
    
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
            on_tool_call: 工具调用回调（简单聊天不使用工具）
            on_sse_event: SSE事件回调函数
        
        Returns:
            Dict: 处理结果
        """
        # 1. 保存用户消息到历史
        await self.session_service.add_message(
            session_id, "user", user_input, "simple_chat"
        )
        
        # 2. 获取会话数据和历史记录
        session_data = await self.session_service.get_session(session_id)
        history = await self.session_service.get_history(session_id, limit=20)
        
        # 3. 构建对话历史（转换为模型需要的格式）
        # 排除最后一条用户消息（即当前消息），因为 run_chain 会自动添加
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
                        "agent_type": "simple_chat",
                        "agent_class": "SimpleChatService",
                        "model_name": self.chat_agent.model_name
                    })
                else:
                    on_sse_event("model_request", {
                        "agent_type": "simple_chat",
                        "agent_class": "SimpleChatService",
                        "model_name": self.chat_agent.model_name
                    })
            except Exception as e:
                logger.warning(f"发送模型请求事件失败: {e}")
        
        # 5. 调用模型生成回复
        try:
            result = await self.chat_agent.run_chain(
                system_prompt=self.system_prompt,
                user_input=user_input,
                json_mode=False,  # 普通聊天不需要 JSON 格式
                session_id=session_id,
                on_sse_event=on_sse_event,
                conversation_history=conversation_history
            )
            
            # 提取回复内容
            if isinstance(result, dict):
                response_text = result.get("content", result.get("response", str(result)))
            else:
                response_text = str(result)
            
        except Exception as e:
            logger.error(f"生成回复失败: {e}", exc_info=True)
            response_text = f"抱歉，处理您的消息时出现了错误：{str(e)}"
        
        # 6. 发送 SSE 事件：处理完成
        if on_sse_event:
            try:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("model_response", {
                        "agent_type": "simple_chat",
                        "agent_class": "SimpleChatService",
                        "model_name": self.chat_agent.model_name,
                        "duration": self.chat_agent.last_duration,
                        "input_tokens": getattr(self.chat_agent, 'last_input_tokens', 0),
                        "output_tokens": getattr(self.chat_agent, 'last_output_tokens', 0)
                    })
                else:
                    on_sse_event("model_response", {
                        "agent_type": "simple_chat",
                        "agent_class": "SimpleChatService",
                        "model_name": self.chat_agent.model_name,
                        "duration": self.chat_agent.last_duration,
                        "input_tokens": getattr(self.chat_agent, 'last_input_tokens', 0),
                        "output_tokens": getattr(self.chat_agent, 'last_output_tokens', 0)
                    })
            except Exception as e:
                logger.warning(f"发送模型响应事件失败: {e}")
        
        # 7. 保存 AI 响应到历史
        await self.session_service.add_message(
            session_id, "assistant", response_text, "simple_chat"
        )
        
        # 8. 保存会话
        session_data["last_question"] = response_text
        session_data["agent_type"] = "simple_chat"
        await self.session_service.save_session(session_id, session_data)
        
        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
            "agent_type": "simple_chat",
            "debug": {
                "model": self.chat_agent.model_name,
                "duration": self.chat_agent.last_duration
            }
        }

