"""
Planner-Worker 架构服务
"""
import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Callable
from src.agents.router import Router
from src.agents.info_worker import InfoWorker
from src.agents.experience_worker import ExperienceWorker
from src.agents.skill_worker import SkillWorker
from src.agents.education_worker import EducationWorker
from src.agents.inference import InferenceWorker
from src.agents.aggregator import Aggregator
from src.agents.executor import Executor
from src.config.models import ModelConfig
from src.utils.helpers import deep_merge, has_data_changed
from .session_service import SessionService

logger = logging.getLogger("service.planner_worker")

# #region agent log helper
def _write_debug_log(data: dict):
    """安全地写入调试日志"""
    try:
        log_data = {
            "sessionId": data.get("sessionId", "debug-session"),
            "runId": data.get("runId", "run1"),
            "hypothesisId": data.get("hypothesisId", "?"),
            "location": data.get("location", "unknown"),
            "message": data.get("message", ""),
            "data": data.get("data", {}),
            "timestamp": data.get("timestamp", int(time.time() * 1000))
        }
        with open('/Users/daijinma/Desktop/work/agnet1/.cursor/debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
        logger.info(f"[DEBUG] {log_data['location']}: {log_data['message']} - {json.dumps(log_data['data'], ensure_ascii=False)}")
    except Exception as e:
        logger.debug(f"Debug log write failed: {e}")
# #endregion


class PlannerWorkerService:
    """Planner-Worker 架构服务"""
    
    def __init__(self, session_service: SessionService):
        """
        初始化 Planner-Worker 服务
        
        Args:
            session_service: 会话服务
        """
        self.session_service = session_service
        
        # 初始化组件
        self.router = Router()
        self.workers = {
            "info": InfoWorker(),
            "experience": ExperienceWorker(),
            "skill": SkillWorker(),
            "education": EducationWorker()
        }
        self.inference_worker = InferenceWorker()
        self.aggregator = Aggregator()
        self.executor = Executor()
    
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
        # #region agent log
        _write_debug_log({
            "hypothesisId": "B",
            "location": "planner_worker_service.py:62",
            "message": "Before add_message",
            "data": {"session_id": session_id, "user_input_len": len(user_input)}
        })
        # #endregion
        
        # 1. 保存用户消息到历史
        try:
            await self.session_service.add_message(
                session_id, "user", user_input, "planner_worker"
            )
            # #region agent log
            _write_debug_log({
                "hypothesisId": "B",
                "location": "planner_worker_service.py:68",
                "message": "After add_message success",
                "data": {}
            })
            # #endregion
        except Exception as e:
            # #region agent log
            import traceback
            _write_debug_log({
                "hypothesisId": "B",
                "location": "planner_worker_service.py:72",
                "message": "add_message failed",
                "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
            })
            # #endregion
            raise
        
        # #region agent log
        _write_debug_log({
            "hypothesisId": "A",
            "location": "planner_worker_service.py:77",
            "message": "Before get_session",
            "data": {"session_id": session_id}
        })
        # #endregion
        
        # 2. 获取会话数据
        try:
            session_data = await self.session_service.get_session(session_id)
            # #region agent log
            _write_debug_log({
                "hypothesisId": "A",
                "location": "planner_worker_service.py:82",
                "message": "After get_session success",
                "data": {
                    "has_resume_data": "resume_data" in session_data,
                    "resume_data_keys": list(session_data.get("resume_data", {}).keys()) if isinstance(session_data.get("resume_data"), dict) else "not_dict"
                }
            })
            # #endregion
        except Exception as e:
            # #region agent log
            import traceback
            _write_debug_log({
                "hypothesisId": "A",
                "location": "planner_worker_service.py:88",
                "message": "get_session failed",
                "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
            })
            # #endregion
            raise
        
        # #region agent log
        _write_debug_log({
            "hypothesisId": "C",
            "location": "planner_worker_service.py:95",
            "message": "Before router.route",
            "data": {"session_data_keys": list(session_data.keys()), "has_resume_data": "resume_data" in session_data}
        })
        # #endregion
        
        # 3. 路由请求
        last_question = session_data.get("last_question")
        try:
            route_result = await self.router.route(
                user_input, session_data, last_question=last_question, session_id=session_id, on_sse_event=on_sse_event
            )
            intents = route_result.get("intents", ["chat"])
            # #region agent log
            _write_debug_log({
                "hypothesisId": "C",
                "location": "planner_worker_service.py:102",
                "message": "After router.route success",
                "data": {"intents": intents, "has_slots": "slots_to_fill" in route_result}
            })
            # #endregion
        except Exception as e:
            # #region agent log
            import traceback
            _write_debug_log({
                "hypothesisId": "C",
                "location": "planner_worker_service.py:108",
                "message": "router.route failed",
                "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
            })
            # #endregion
            raise
        
        # 4. 更新槽位
        self._update_slots(route_result, session_data)
        
        # 5. 处理消息
        # 获取对话历史（用于首次对话判断）
        conversation_history = []
        if session_id:
            try:
                conversation_history = await self.session_service.get_history(session_id, limit=5)
            except Exception as e:
                logger.warning(f"获取对话历史失败: {e}")
        
        if len(intents) == 1 and intents[0] == "chat":
            response_text = await self.aggregator.aggregate(
                session_data, ", ".join(intents),
                pending_questions=session_data.get("pending_questions", []),
                session_id=session_id,
                user_input=user_input,
                conversation_history=conversation_history,
                on_sse_event=on_sse_event
            )
        else:
            # #region agent log
            _write_debug_log({
                "hypothesisId": "D",
                "location": "planner_worker_service.py:115",
                "message": "Before _run_workers",
                "data": {
                    "intents": intents,
                    "resume_data_type": type(session_data.get("resume_data")).__name__,
                    "resume_data_keys": list(session_data.get("resume_data", {}).keys()) if isinstance(session_data.get("resume_data"), dict) else "not_dict"
                }
            })
            # #endregion
            
            # 执行 Worker
            try:
                await self._run_workers(intents, user_input, session_data, on_tool_call, session_id, on_sse_event=on_sse_event)
                # #region agent log
                _write_debug_log({
                    "hypothesisId": "D",
                    "location": "planner_worker_service.py:121",
                    "message": "After _run_workers success",
                    "data": {}
                })
                # #endregion
            except Exception as e:
                # #region agent log
                import traceback
                _write_debug_log({
                    "hypothesisId": "D",
                    "location": "planner_worker_service.py:126",
                    "message": "_run_workers failed",
                    "data": {"error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()[:500]}
                })
                # #endregion
                raise
            
            # 推理（如果需要）
            should_infer = any(word in user_input for word in ["建议", "检查", "优化", "评价"])
            await self._run_inference(session_data, force=should_infer, session_id=session_id)
            
            response_text = await self.aggregator.aggregate(
                session_data, ", ".join(intents),
                pending_questions=session_data.get("pending_questions", []),
                session_id=session_id,
                user_input=user_input,
                conversation_history=conversation_history,
                on_sse_event=on_sse_event
            )
        
        # 6. 保存 AI 响应到历史
        await self.session_service.add_message(
            session_id, "assistant", response_text, "planner_worker"
        )
        
        # 7. 保存会话
        session_data["last_question"] = response_text
        session_data["agent_type"] = "planner_worker"
        await self.session_service.save_session(session_id, session_data)
        
        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
            "pending_questions": session_data.get("pending_questions", []),
            "agent_type": "planner_worker",
            "debug": {
                "intents": intents,
                "duration": self._calculate_total_duration(intents)
            }
        }
    
    def _update_slots(self, route_result: Dict[str, Any], session_data: Dict[str, Any]):
        """更新槽位状态"""
        slots = route_result.get("slots_to_fill", [])
        if not slots:
            return
        
        pending = session_data.setdefault("pending_questions", [])
        priority = {"name": 1, "phone": 2, "email": 3, "school": 4, "major": 5, "degree": 6}
        
        for s in slots:
            if s not in pending:
                pending.append(s)
        
        pending.sort(key=lambda x: priority.get(x.lower(), 99))
    
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
                    user_input, session_data["resume_data"], on_tool_call=worker_callback, session_id=session_id, on_sse_event=on_sse_event
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
                missing = res.get("missing_fields", [])
                if missing:
                    all_missing_fields.extend(missing)
            else:
                logger.warning(f"Worker 返回了非字典类型: {type(res)}, 跳过合并")
        
        # 传递给 Aggregator（简单数组格式，去重）
        session_data["worker_missing_fields"] = list(set(all_missing_fields))
        
        return results
    
    async def _run_inference(self, session_data: Dict[str, Any], force: bool = False, session_id: str = None) -> Dict[str, Any]:
        """职业推理"""
        if not force and not has_data_changed(session_data):
            return {"insights": session_data.get("inference_insights", [])}
        
        result = await self.inference_worker.analyze(session_data["resume_data"], session_id=session_id)
        session_data["inference_insights"] = result.get("insights", [])
        
        # 将 inference 提取的技能合并到 resume_data 中
        skills = result.get("skills", [])
        if skills:
            skills_data = {"skills": skills}
            deep_merge(session_data["resume_data"], skills_data)
            logger.info(f"Inference agent 提取了 {len(skills)} 个技能类别")
        
        return result
    
    def _calculate_total_duration(self, active_intents: List[str]) -> float:
        """统计总耗时"""
        total = self.router.last_duration + self.aggregator.last_duration + self.inference_worker.last_duration
        for intent in active_intents:
            if intent in self.workers:
                total += self.workers[intent].last_duration
        return total
    
    async def generate_final_resume(self, session_id: str) -> Dict[str, Any]:
        """生成最终结构化简历"""
        session_data = await self.session_service.get_session(session_id)
        resume_slots = session_data.get("resume_data", {})
        
        result = await self.executor.generate_full_resume(resume_slots)
        validation = self.executor.validate(result)
        
        session_data["full_resume"] = result
        session_data["full_resume_validation"] = validation
        await self.session_service.save_session(session_id, session_data)
        
        return {
            "result": result,
            "validation": validation
        }

