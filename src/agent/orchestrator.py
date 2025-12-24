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

    async def route_request(self, user_input: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """1. 意图识别"""
        last_question = session_data.get("last_question")
        return await self.router.route(user_input, session_data, last_question=last_question)

    def update_slots(self, route_result: Dict[str, Any], session_data: Dict[str, Any]):
        """2. 槽位状态更新 (优先级排序)"""
        slots = route_result.get("slots_to_fill", [])
        if not slots:
            return
            
        pending = session_data.setdefault("pending_questions", [])
        priority = {"name": 1, "phone": 2, "email": 3, "school": 4, "major": 5, "degree": 6}
        
        for s in slots:
            if s not in pending:
                pending.append(s)
        
        pending.sort(key=lambda x: priority.get(x.lower(), 99))

    async def run_workers(self, intents: List[str], user_input: str, session_data: Dict[str, Any], on_tool_call=None) -> List[Dict[str, Any]]:
        """3. 并行执行专家 Worker"""
        tasks = [
            self.workers[i].process(user_input, session_data["resume_data"], on_tool_call=on_tool_call)
            for i in intents if i in self.workers
        ]
        if not tasks:
            return []
            
        results = await asyncio.gather(*tasks)
        for res in results:
            self._deep_merge(session_data["resume_data"], res)
        return results

    async def run_inference(self, session_data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """4. 职业推理 (智能触发)"""
        if not force and not self._has_data_changed(session_data):
            return {"insights": session_data.get("inference_insights", [])}

        result = await self.inference_worker.analyze(session_data["resume_data"])
        session_data["inference_insights"] = result.get("insights", [])
        return result

    async def get_response(self, session_data: Dict[str, Any], intents: List[str]) -> str:
        """5. 组织 HR 语言回复"""
        response = await self.aggregator.aggregate(
            session_data, ", ".join(intents), 
            pending_questions=session_data.get("pending_questions", [])
        )
        session_data["last_question"] = response
        return response

    # --- 内部辅助逻辑 (保持私有，减少主流程干扰) ---

    def _has_data_changed(self, session_data: Dict[str, Any]) -> bool:
        resume = session_data.get("resume_data", {})
        current_hash = hash(json.dumps({
            "edu": len(resume.get("education", [])),
            "exp": len(resume.get("experience", [])),
            "skills": resume.get("skills", [])
        }, sort_keys=True))
        
        changed = session_data.get("last_resume_hash") != current_hash
        session_data["last_resume_hash"] = current_hash
        return changed

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        for k, v in source.items():
            if k in target and isinstance(target[k], list) and isinstance(v, list):
                existing = [json.dumps(i, sort_keys=True) for i in target[k]]
                for item in v:
                    if json.dumps(item, sort_keys=True) not in existing:
                        target[k].append(item)
            elif k in target and isinstance(target[k], dict) and isinstance(v, dict):
                self._deep_merge(target[k], v)
            else:
                target[k] = v

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
