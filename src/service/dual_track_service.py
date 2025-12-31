"""
Dual-Track 架构服务
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from src.agents.router import Router
from src.agents.info_worker import InfoWorker
from src.agents.experience_worker import ExperienceWorker
from src.agents.skill_worker import SkillWorker
from src.agents.aggregator import Aggregator
from src.agents.question_queue import QuestionQueue
from src.agents.background_reasoner import BackgroundReasoner, AsyncBackgroundReasoner
from src.config.models import ModelConfig
from src.utils.helpers import deep_merge, has_data_changed
from .session_service import SessionService

logger = logging.getLogger("service.dual_track")


class DualTrackService:
    """Dual-Track 架构服务"""
    
    def __init__(self, session_service: SessionService):
        """
        初始化 Dual-Track 服务
        
        Args:
            session_service: 会话服务（必须使用数据库模式）
        """
        self.session_service = session_service
        
        # 初始化组件
        self.router = Router()
        self.workers = {
            "info": InfoWorker(),
            "experience": ExperienceWorker(),
            "skill": SkillWorker()
        }
        self.aggregator = Aggregator()
        
        # 背景推理服务
        background_reasoner = BackgroundReasoner(model=ModelConfig.MODEL_INFERENCE)
        self.async_background_reasoner = AsyncBackgroundReasoner(
            background_reasoner,
            session_service
        )
    
    async def process_message(
        self,
        session_id: str,
        user_input: str,
        on_tool_call: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            session_id: 会话 ID
            user_input: 用户输入
            on_tool_call: 工具调用回调
        
        Returns:
            Dict: 处理结果
        """
        # 1. 保存用户消息到历史
        await self.session_service.add_message(
            session_id, "user", user_input, "dual_track"
        )
        
        # 2. 获取会话数据
        session_data = await self.session_service.get_session(session_id)
        
        # 3. 从问题队列提取待提问的问题
        pending_questions = await self.session_service.get_pending_questions(
            session_id, limit=1
        )
        
        # 4. 快速路由（小模型）
        last_question = session_data.get("last_question")
        route_result = await self.router.route(
            user_input, session_data, last_question=last_question, session_id=session_id
        )
        intents = route_result.get("intents", ["chat"])
        
        # 5. 执行 Worker（如果需要）
        if len(intents) > 1 or (len(intents) == 1 and intents[0] != "chat"):
            await self._run_workers(intents, user_input, session_data, on_tool_call, session_id)
            
            # 检查数据是否变化，如果变化则触发背景推理
            if has_data_changed(session_data):
                await self.async_background_reasoner.trigger_reasoning(
                    session_id,
                    session_data["resume_data"],
                    delay=0.5  # 延迟 0.5 秒，避免阻塞
                )
        
        # 6. 生成响应（整合问题）
        response_text = await self._get_response_with_questions(
            session_data, intents, pending_questions, session_id
        )
        
        # 7. 标记已回答的问题
        if pending_questions:
            for q in pending_questions:
                await self.session_service.mark_question_answered(
                    session_id, q["id"]
                )
        
        # 8. 保存 AI 响应到历史
        await self.session_service.add_message(
            session_id, "assistant", response_text, "dual_track"
        )
        
        # 9. 保存会话
        session_data["last_question"] = response_text
        session_data["agent_type"] = "dual_track"
        await self.session_service.save_session(session_id, session_data)
        
        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
            "pending_questions": [q["content"] for q in pending_questions],
            "agent_type": "dual_track",
            "debug": {
                "intents": intents,
                "questions_count": len(pending_questions),
                "background_reasoning_status": session_data.get("background_reasoning_status", "pending")
            }
        }
    
    async def _run_workers(
        self,
        intents: List[str],
        user_input: str,
        session_data: Dict[str, Any],
        on_tool_call: Optional[Callable] = None,
        session_id: str = None
    ) -> List[Dict[str, Any]]:
        """并行执行专家 Worker"""
        tasks = []
        for intent in intents:
            if intent not in self.workers:
                continue
            
            if on_tool_call:
                async def wrapped_callback(tool_name, tool_args, captured_intent=intent):
                    try:
                        await on_tool_call(captured_intent, tool_name, tool_args)
                    except TypeError:
                        await on_tool_call(tool_name, tool_args)
                worker_callback = wrapped_callback
            else:
                worker_callback = None
            
            tasks.append(
                self.workers[intent].process(
                    user_input,
                    session_data["resume_data"],
                    on_tool_call=worker_callback,
                    session_id=session_id
                )
            )
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks)
        for res in results:
            deep_merge(session_data["resume_data"], res)
        
        return results
    
    async def _get_response_with_questions(
        self,
        session_data: Dict[str, Any],
        intents: List[str],
        pending_questions: List[Dict[str, Any]],
        session_id: str = None
    ) -> str:
        """生成响应，整合问题队列中的问题"""
        response = await self.aggregator.aggregate(
            session_data,
            ", ".join(intents),
            pending_questions=[q["content"] for q in pending_questions] if pending_questions else [],
            session_id=session_id
        )
        return response
    
    async def get_reasoning_status(self, session_id: str) -> Dict[str, Any]:
        """获取背景推理状态"""
        session_data = await self.session_service.get_session(session_id)
        pending_questions = await self.session_service.get_pending_questions(
            session_id, limit=10
        )
        
        return {
            "session_id": session_id,
            "background_reasoning_status": session_data.get("background_reasoning_status", "pending"),
            "last_reasoning_time": session_data.get("last_reasoning_time"),
            "pending_questions_count": len(pending_questions),
            "pending_questions": [
                {
                    "id": q["id"],
                    "content": q["content"],
                    "priority": q.get("priority"),
                    "field": q.get("field")
                }
                for q in pending_questions
            ],
            "inference_insights": session_data.get("inference_insights", [])
        }

