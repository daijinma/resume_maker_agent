import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("resume-agent.orchestrator")

class Orchestrator:
    def __init__(self, router, workers, inference_worker, aggregator, executor, session_manager):
        self.router = router
        self.workers = workers
        self.inference_worker = inference_worker
        self.aggregator = aggregator
        self.executor = executor
        self.session_manager = session_manager

    async def plan_and_route(self, user_input: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """步骤 1: 路由决策与槽位检查"""
        route_result = await self.router.route(user_input, session_data)
        intents = route_result.get("intents", [])
        if not intents:
            intents = ["chat"]
        
        # 更新待补充问题
        slots_to_fill = route_result.get("slots_to_fill", [])
        if slots_to_fill:
            pending = session_data.setdefault("pending_questions", [])
            for q in slots_to_fill:
                if q not in pending:
                    pending.append(q)
        
        return {
            "intents": intents,
            "route_result": route_result
        }

    async def execute_workers(self, intents: List[str], user_input: str, session_data: Dict[str, Any], on_tool_call: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """步骤 2: 并发执行 Worker"""
        worker_tasks = []
        active_intents = []
        
        for intent in intents:
            if intent in self.workers:
                active_intents.append(intent)
                worker_tasks.append(self.workers[intent].process(
                    user_input, 
                    session_data["resume_data"], 
                    on_tool_call=on_tool_call
                ))
        
        if not worker_tasks:
            return []
            
        results = await asyncio.gather(*worker_tasks)
        
        # 更新简历数据
        for updated_section in results:
            session_data["resume_data"].update(updated_section)
            
        return results

    async def infer_and_verify(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """步骤 3: 常识校验与推理"""
        inference_result = await self.inference_worker.analyze(session_data["resume_data"])
        session_data["inference_insights"] = inference_result.get("insights", [])
        return inference_result

    async def summarize_response(self, session_data: Dict[str, Any], intents: List[str]) -> str:
        """步骤 4: 汇总生成回复"""
        response_text = await self.aggregator.aggregate(
            session_data, 
            ", ".join(intents), 
            pending_questions=session_data.get("pending_questions", [])
        )
        return response_text

    async def generate_final_resume(self, session_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """步骤 5: 生成最终结构化简历并校验"""
        resume_slots = session_data.get("resume_data", {})
        result = await self.executor.generate_full_resume(resume_slots)
        validation = self.executor.validate(result)

        # 保存生成结果与校验
        session_data["full_resume"] = result
        session_data["full_resume_validation"] = validation
        self.session_manager.save_session(session_id, session_data)
        
        return {
            "result": result,
            "validation": validation
        }

    def calculate_total_duration(self, active_intents: List[str]) -> float:
        """统计总耗时"""
        total = self.router.last_duration + self.aggregator.last_duration + self.inference_worker.last_duration
        for intent in active_intents:
            if intent in self.workers:
                total += self.workers[intent].last_duration
        return total
