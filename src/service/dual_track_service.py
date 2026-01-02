"""
Dual-Track 架构服务
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from src.agents.router import Router
from src.agents.side_router import SideRouter
from src.agents.info_worker import InfoWorker
from src.agents.experience_worker import ExperienceWorker
from src.agents.skill_worker import SkillWorker
from src.agents.education_worker import EducationWorker
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
        self.side_router = SideRouter()
        self.workers = {
            "info": InfoWorker(),
            "experience": ExperienceWorker(),
            "skill": SkillWorker(),
            "education": EducationWorker()
        }
        self.aggregator = Aggregator()
        
        # 背景推理服务（使用默认推理模型配置）
        background_reasoner = BackgroundReasoner()
        self.async_background_reasoner = AsyncBackgroundReasoner(
            background_reasoner,
            session_service
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
            session_id, "user", user_input, "dual_track"
        )
        
        # 2. 获取会话数据
        session_data = await self.session_service.get_session(session_id)
        
        # 3. 检查是否有待提问问题（在 Router 之前）
        pending_questions = await self.session_service.get_pending_questions(
            session_id, limit=1
        )
        
        if pending_questions:
            # 过滤掉已经被当前轮次回答的问题
            pending_questions = self._filter_answered_questions(
                pending_questions, session_data["resume_data"], user_input
            )
        
        # 4. 如果有 pending_questions，启动两条完全独立的并行路线
        is_side_router = False  # 共享标志：SideRouter 是否返回了有效响应
        
        if pending_questions:
            # 获取5轮对话历史
            conversation_history = []
            try:
                conversation_history = await self.session_service.get_history(session_id, limit=5)
            except Exception as e:
                logger.warning(f"获取对话历史失败: {e}")
            
            last_question = session_data.get("last_question")
            
            # 路线1：SideRouter 路线（快速路径）
            async def side_router_route():
                nonlocal is_side_router
                side_response = await self.side_router.route(
                    user_input, session_data, pending_questions, conversation_history, session_id=session_id, on_sse_event=on_sse_event
                )
                if side_response and side_response.strip():
                    is_side_router = True
                    return side_response
                return None
            
            # 路线2：Router 路线（Router -> Worker -> Aggregator）
            async def router_route():
                # Router
                route_result = await self.router.route(
                    user_input, session_data, last_question=last_question, session_id=session_id, on_sse_event=on_sse_event
                )
                intents = route_result.get("intents", ["chat"])
                
                # Worker（如果需要）
                if len(intents) > 1 or (len(intents) == 1 and intents[0] != "chat"):
                    await self._run_workers(intents, user_input, session_data, on_tool_call, session_id, on_sse_event=on_sse_event)
                    
                    # 检查数据是否变化，如果变化则触发背景推理
                    if has_data_changed(session_data):
                        await self.async_background_reasoner.trigger_reasoning(
                            session_id,
                            session_data["resume_data"],
                            delay=0.5
                        )
                
                # 检查 is_side_router，如果为 False 才执行 Aggregator
                if not is_side_router:
                    # 从问题队列提取待提问的问题
                    current_pending_questions = await self.session_service.get_pending_questions(session_id, limit=1)
                    current_pending_questions = self._filter_answered_questions(
                        current_pending_questions, session_data["resume_data"], user_input
                    )
                    
                    # Aggregator 生成响应
                    response_text = await self._get_response_with_questions(
                        session_data, intents, current_pending_questions, session_id, user_input, on_sse_event=on_sse_event
                    )
                    
                    # 标记已回答的问题
                    if current_pending_questions:
                        for q in current_pending_questions:
                            await self.session_service.mark_question_answered(session_id, q["id"])
                    
                    # 保存 AI 响应到历史
                    await self.session_service.add_message(
                        session_id, "assistant", response_text, "dual_track"
                    )
                    
                    # 保存会话
                    session_data["last_question"] = response_text
                    session_data["agent_type"] = "dual_track"
                    await self.session_service.save_session(session_id, session_data)
                    
                    return {
                        "status": "success",
                        "response": response_text,
                        "session_id": session_id,
                        "pending_questions": [q.get("field", q.get("content", "")) for q in current_pending_questions],
                        "agent_type": "dual_track",
                        "debug": {
                            "intents": intents,
                            "questions_count": len(current_pending_questions),
                            "background_reasoning_status": session_data.get("background_reasoning_status", "pending")
                        }
                    }
                else:
                    # SideRouter 已经返回，只保存会话状态（Worker 可能已经更新了数据）
                    session_data["agent_type"] = "dual_track"
                    await self.session_service.save_session(session_id, session_data)
                    return None
            
            # 启动两条路线并行执行
            side_route_task = asyncio.create_task(side_router_route())
            router_route_task = asyncio.create_task(router_route())
            
            # 等待 SideRouter 路线完成（通常更快）
            side_response = await side_route_task
            
            # 如果 SideRouter 返回有效响应，使用它并返回
            if side_response:
                # 标记已回答的问题
                for q in pending_questions:
                    await self.session_service.mark_question_answered(session_id, q["id"])
                
                # 保存 AI 响应到历史
                await self.session_service.add_message(
                    session_id, "assistant", side_response, "dual_track"
                )
                
                # 保存基本会话状态
                session_data["last_question"] = side_response
                session_data["agent_type"] = "dual_track"
                await self.session_service.save_session(session_id, session_data)
                
                # Router 路线继续在后台执行（Worker 处理），但不执行 Aggregator
                
                return {
                    "status": "success",
                    "response": side_response,
                    "session_id": session_id,
                    "pending_questions": [q.get("field", q.get("content", "")) for q in pending_questions],
                    "agent_type": "dual_track",
                    "debug": {
                        "questions_count": len(pending_questions),
                        "response_type": "side_router",
                        "background_processing": True,  # Router 路线在后台继续执行
                        "background_reasoning_status": session_data.get("background_reasoning_status", "pending")
                    }
                }
            
            # SideRouter 返回空，等待 Router 路线完成
            router_result = await router_route_task
            if router_result:
                return router_result
        else:
            # 没有 pending_questions，只执行 Router
            last_question = session_data.get("last_question")
            route_result = await self.router.route(
                user_input, session_data, last_question=last_question, session_id=session_id, on_sse_event=on_sse_event
            )
            intents = route_result.get("intents", ["chat"])
        
        # 5. 快速响应路径：如果有待提问问题，立即快速响应 + 后台处理
        if pending_questions:
            # 使用快速响应模型生成确认回复 + 下一个问题
            response_text = await self._fast_response(
                session_data, pending_questions, user_input, session_id, on_sse_event=on_sse_event
            )
            
            # 标记已回答的问题
            for q in pending_questions:
                await self.session_service.mark_question_answered(
                    session_id, q["id"]
                )
            
            # 保存 AI 响应到历史
            await self.session_service.add_message(
                session_id, "assistant", response_text, "dual_track"
            )
            
            # 保存基本会话状态（响应和问题标记）
            session_data["last_question"] = response_text
            session_data["agent_type"] = "dual_track"
            await self.session_service.save_session(session_id, session_data)
            
            # 创建后台任务，异步执行 Worker 处理和背景推理
            # 只有在有实际意图（非纯聊天）时才执行后台处理
            if len(intents) > 1 or (len(intents) == 1 and intents[0] != "chat"):
                asyncio.create_task(
                    self._background_process(
                        session_id, user_input, intents, on_tool_call, on_sse_event
                    )
                )
                logger.info(f"已创建后台处理任务: {session_id}, intents: {intents}")
            
            return {
                "status": "success",
                "response": response_text,
                "session_id": session_id,
                "pending_questions": [q["content"] for q in pending_questions],
                "agent_type": "dual_track",
                "debug": {
                    "intents": intents,
                    "questions_count": len(pending_questions),
                    "response_type": "fast_response",
                    "background_processing": len(intents) > 1 or (len(intents) == 1 and intents[0] != "chat"),
                    "background_reasoning_status": session_data.get("background_reasoning_status", "pending")
                }
            }
        
        # 5. 执行 Worker（如果需要）
        if len(intents) > 1 or (len(intents) == 1 and intents[0] != "chat"):
            await self._run_workers(intents, user_input, session_data, on_tool_call, session_id, on_sse_event=on_sse_event)
            
            # 检查数据是否变化，如果变化则触发背景推理
            if has_data_changed(session_data):
                await self.async_background_reasoner.trigger_reasoning(
                    session_id,
                    session_data["resume_data"],
                    delay=0.5  # 延迟 0.5 秒，避免阻塞
                )
        
        # 6. 从问题队列提取待提问的问题（在 Worker 执行之后，确保基于最新数据状态）
        pending_questions = await self.session_service.get_pending_questions(
            session_id, limit=1
        )
        
        # 7. 过滤掉已经被当前轮次回答的问题
        pending_questions = self._filter_answered_questions(
            pending_questions, session_data["resume_data"], user_input
        )
        
        # 8. 如果有 pending_questions，尝试使用 SideRouter
        if pending_questions:
            # 获取5轮对话历史
            conversation_history = []
            try:
                conversation_history = await self.session_service.get_history(session_id, limit=5)
            except Exception as e:
                logger.warning(f"获取对话历史失败: {e}")
            
            # 调用 SideRouter
            side_response = await self.side_router.route(
                user_input, session_data, pending_questions, conversation_history, session_id=session_id, on_sse_event=on_sse_event
            )
            
            # 如果 SideRouter 返回非空字符串，使用它并跳过 Aggregator
            if side_response and side_response.strip():
                # 标记已回答的问题
                for q in pending_questions:
                    await self.session_service.mark_question_answered(
                        session_id, q["id"]
                    )
                
                # 保存 AI 响应到历史
                await self.session_service.add_message(
                    session_id, "assistant", side_response, "dual_track"
                )
                
                # 保存会话
                session_data["last_question"] = side_response
                session_data["agent_type"] = "dual_track"
                await self.session_service.save_session(session_id, session_data)
                
                return {
                    "status": "success",
                    "response": side_response,
                    "session_id": session_id,
                    "pending_questions": [q.get("field", q.get("content", "")) for q in pending_questions],
                    "agent_type": "dual_track",
                    "debug": {
                        "intents": intents,
                        "questions_count": len(pending_questions),
                        "response_type": "side_router",
                        "background_reasoning_status": session_data.get("background_reasoning_status", "pending")
                    }
                }
        
        # 9. 生成响应（整合问题）- 使用 Aggregator
        response_text = await self._get_response_with_questions(
            session_data, intents, pending_questions, session_id, user_input, on_sse_event=on_sse_event
        )
        
        # 10. 标记已回答的问题
        if pending_questions:
            for q in pending_questions:
                await self.session_service.mark_question_answered(
                    session_id, q["id"]
                )
        
        # 11. 保存 AI 响应到历史
        await self.session_service.add_message(
            session_id, "assistant", response_text, "dual_track"
        )
        
        # 12. 保存会话
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
        session_id: str = None,
        on_sse_event: Optional[Callable] = None
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
                    session_id=session_id,
                    on_sse_event=on_sse_event
                )
            )
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks)
        all_missing_fields = []
        
        for res in results:
            # 处理新的返回格式：{extracted_data: {}, missing_fields: []}
            if isinstance(res, dict):
                # 合并提取的数据
                extracted = res.get("extracted_data", res)
                deep_merge(session_data["resume_data"], extracted)
                
                # 收集缺失字段（简单数组）
                # 注意：缺失字段不添加到问题队列，而是直接传递给 Aggregator 在本轮次生成问题
                missing = res.get("missing_fields", [])
                if missing:
                    all_missing_fields.extend(missing)
        
        # 保存到 session_data，供 Aggregator 使用（去重）
        # Worker 识别的缺失字段由 Aggregator 在本轮次直接生成问题返回
        # 问题队列（pending_questions）只包含 BackgroundReasoner 生成的逻辑推理问题
        session_data["worker_missing_fields"] = list(set(all_missing_fields))
        
        return results
    
    def _filter_answered_questions(
        self,
        pending_questions: List[Dict[str, Any]],
        resume_data: Dict[str, Any],
        user_input: str
    ) -> List[Dict[str, Any]]:
        """
        过滤掉已经被回答的问题
        
        检查 resume_data 中是否已存在相关信息，如果用户输入中提到了相关数据，则跳过该问题
        
        Args:
            pending_questions: 待提问的问题列表
            resume_data: 简历数据
            user_input: 用户输入
        
        Returns:
            过滤后的问题列表
        """
        filtered = []
        
        for q in pending_questions:
            field = q.get("field", "")
            question_content = q.get("content", "").lower()
            
            # 检查工作经历/公司相关的问题
            if field in ["experience", "company"] or "公司" in question_content or "工作经历" in question_content:
                experience = resume_data.get("experience", [])
                if experience and len(experience) > 0:
                    # 检查是否有公司信息
                    companies = [
                        exp.get("company", "") 
                        for exp in experience 
                        if exp.get("company") and exp.get("company").strip()
                    ]
                    if companies:
                        # 检查用户输入中是否提到了已存在的公司名（说明用户在回答这个问题）
                        mentioned_in_input = any(
                            company in user_input for company in companies if company and len(company) > 0
                        )
                        # 如果用户输入中提到了公司，说明正在回答，跳过此问题
                        if mentioned_in_input:
                            logger.info(
                                f"问题 {q.get('id')} (field: {field}) 已被用户回答，"
                                f"用户输入中提到了公司: {[c for c in companies if c in user_input][:2]}，跳过"
                            )
                            continue
            
            # 检查个人信息相关的问题
            elif field in ["name"]:
                personal_info = resume_data.get("personal_info", {})
                if personal_info.get("name"):
                    logger.info(f"问题 {q.get('id')} (field: {field}) 已被用户回答，跳过")
                    continue
            
            elif field in ["email"]:
                personal_info = resume_data.get("personal_info", {})
                if personal_info.get("email"):
                    logger.info(f"问题 {q.get('id')} (field: {field}) 已被用户回答，跳过")
                    continue
            
            elif field in ["phone"]:
                personal_info = resume_data.get("personal_info", {})
                if personal_info.get("phone"):
                    logger.info(f"问题 {q.get('id')} (field: {field}) 已被用户回答，跳过")
                    continue
            
            # 检查教育背景相关的问题
            elif field in ["school", "major", "degree"] or "教育" in question_content or "学历" in question_content:
                education = resume_data.get("education", [])
                if education and len(education) > 0:
                    has_school = any(edu.get("school") for edu in education)
                    if has_school:
                        logger.info(f"问题 {q.get('id')} (field: {field}) 已被用户回答，跳过")
                        continue
            
            # 检查技能相关的问题
            elif field in ["skills"] or "技能" in question_content:
                skills = resume_data.get("skills", [])
                if skills and len(skills) > 0:
                    logger.info(f"问题 {q.get('id')} (field: {field}) 已被用户回答，跳过")
                    continue
            
            # 如果问题未被过滤，保留它
            filtered.append(q)
        
        return filtered
    
    async def _fast_response(
        self,
        session_data: Dict[str, Any],
        pending_questions: List[Dict[str, Any]],
        user_input: str,
        session_id: str = None,
        on_sse_event: Optional[Callable] = None
    ) -> str:
        """
        快速响应：使用小模型生成确认回复 + 下一个问题
        
        用于纯聊天场景（intent=["chat"]），跳过 Worker 流程，快速响应
        
        Args:
            session_data: 会话数据
            pending_questions: 待提问的问题列表
            user_input: 用户输入
            session_id: 会话ID
        
        Returns:
            生成的响应文本
        """
        from src.agents.base import BaseAgent
        
        # 获取快速响应模型配置
        fast_config = ModelConfig.get_model_config("fast_response")
        fast_model = fast_config["models"][0] if fast_config["models"] else "qwen/qwen3-4b:free"
        
        # 创建快速响应 Agent
        fast_agent = BaseAgent(
            models=fast_model,
            temperature=fast_config.get("temperature", 0.3),
            max_tokens=fast_config.get("max_tokens", 2048),
            timeout=fast_config.get("timeout", 20.0)
        )
        
        # 从 pending_questions 提取字段名
        missing_fields = []
        if pending_questions:
            for q in pending_questions:
                field = q.get("field")
                if field and field not in missing_fields:
                    missing_fields.append(field)
        
        # 构建快速响应 prompt
        system_prompt = """你是一位资深 HR 招聘官，正在通过聊天帮助候选人完善简历。
你的风格：职场商务、自然口语、简洁专业。

任务：
1. 简短确认用户刚才说的话（1-2句话）
2. 根据缺失字段，自然地提出一个问题

要求：
- 不要列举或机械确认
- 用"好的"、"了解了"等简短确认
- 自然过渡到下一个问题
- 一次只提1个问题（选择优先级最高的字段）
"""
        
        # 构建用户 prompt
        missing_fields_str = ", ".join(missing_fields) if missing_fields else "无"
        user_prompt = f"""用户刚才说：{user_input}

缺失的字段：{missing_fields_str}

请生成一个简短的确认回复，然后根据缺失字段自然地提出一个问题。"""
        
        # 调用模型生成响应
        response = await fast_agent.run_chain(
            system_prompt,
            user_prompt,
            json_mode=False,
            session_id=session_id,
            on_sse_event=on_sse_event
        )
        
        return response
    
    async def _background_process(
        self,
        session_id: str,
        user_input: str,
        intents: List[str],
        on_tool_call: Optional[Callable] = None,
        on_sse_event: Optional[Callable] = None
    ) -> None:
        """
        后台异步处理：执行 Worker 处理、数据变化检测、背景推理和保存
        
        这个方法在快速响应后异步执行，不阻塞主流程
        
        Args:
            session_id: 会话 ID
            user_input: 用户输入
            intents: 意图列表
            on_tool_call: 工具调用回调
            on_sse_event: SSE事件回调函数
        """
        try:
            # 重新获取最新的会话数据，避免覆盖快速响应时保存的数据
            session_data = await self.session_service.get_session(session_id)
            
            # 执行 Worker（如果需要）
            if len(intents) > 1 or (len(intents) == 1 and intents[0] != "chat"):
                # Worker 处理会通过 deep_merge 更新 session_data["resume_data"]
                await self._run_workers(
                    intents, user_input, session_data, on_tool_call, session_id, on_sse_event=on_sse_event
                )
                
                # 检查数据是否变化，如果变化则触发背景推理
                if has_data_changed(session_data):
                    await self.async_background_reasoner.trigger_reasoning(
                        session_id,
                        session_data["resume_data"],
                        delay=0.5  # 延迟 0.5 秒，避免阻塞
                    )
                    logger.info(f"后台处理检测到数据变化，已触发背景推理: {session_id}")
                
                # 保存更新后的数据（包括 Worker 处理的结果）
                # 注意：这里会保留快速响应时保存的 last_question 等字段
                session_data["agent_type"] = "dual_track"
                await self.session_service.save_session(session_id, session_data)
                logger.info(f"后台处理完成，已保存会话数据: {session_id}")
        except Exception as e:
            logger.error(f"后台处理失败: {e}", exc_info=True)
    
    async def _get_response_with_questions(
        self,
        session_data: Dict[str, Any],
        intents: List[str],
        pending_questions: List[Dict[str, Any]],
        session_id: str = None,
        user_input: str = None,
        on_sse_event: Optional[Callable] = None
    ) -> str:
        """
        生成响应，整合缺失字段
        
        注意：
        - pending_questions: 只包含 BackgroundReasoner 生成的逻辑推理问题（遗漏信息、信息漏洞）
        - worker_missing_fields: Worker 识别的缺失字段，由 Aggregator 在本轮次直接生成问题返回
        """
        # 获取最近对话历史（最多5轮）
        conversation_history = []
        if session_id:
            try:
                conversation_history = await self.session_service.get_history(session_id, limit=5)
            except Exception as e:
                logger.warning(f"获取对话历史失败: {e}")
        
        # 从 pending_questions 提取字段名（这些是 BackgroundReasoner 生成的逻辑推理问题）
        # pending_questions 格式: [{"id": "...", "content": "...", "field": "phone", ...}]
        missing_fields_from_reasoning = []
        if pending_questions:
            for q in pending_questions:
                field = q.get("field")
                if field and field not in missing_fields_from_reasoning:
                    missing_fields_from_reasoning.append(field)
        
        # 合并 Worker 识别的缺失字段和逻辑推理识别的缺失字段
        # Worker 缺失字段：由 Worker 在本轮次识别，由 Aggregator 直接生成问题返回
        # 逻辑推理缺失字段：由 BackgroundReasoner 异步生成，存储在问题队列中
        worker_missing_fields = session_data.get("worker_missing_fields", [])
        all_missing_fields = list(set(worker_missing_fields + missing_fields_from_reasoning))
        
        # 将合并后的缺失字段保存到 session_data，让 Aggregator 使用
        session_data["worker_missing_fields"] = all_missing_fields
        
        response = await self.aggregator.aggregate(
            session_data,
            ", ".join(intents),
            pending_questions=None,  # 不再传递问题内容，只传递缺失字段
            session_id=session_id,
            user_input=user_input,
            conversation_history=conversation_history,
            on_sse_event=on_sse_event
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

