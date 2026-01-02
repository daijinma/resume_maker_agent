import json
import logging
from typing import Dict, Any, List, Optional, Callable
from src.agents.base import BaseAgent, time_it
from src.config.models import ModelConfig

logger = logging.getLogger("resume-agent.aggregator")

# 字段到模块的映射
FIELD_TO_MODULE = {
    "name": "info",
    "phone": "info",
    "email": "info",
    "school": "education",
    "major": "education",
    "degree": "education",
    "company": "experience",
    "role": "experience",
    "period": "experience",
    "skills": "skill"
}

# 模块优先级（数字越小优先级越高）
MODULE_PRIORITY = {
    "info": 1,
    "education": 2,
    "experience": 3,
    "skill": 4
}

# 字段优先级（用于模块内排序，与 field_definitions.py 保持一致）
FIELD_PRIORITY = {
    "name": 1,
    "phone": 2,
    "email": 3,
    "school": 4,
    "major": 5,
    "degree": 6,
    "company": 7,
    "role": 8,
    "period": 9,
    "skills": 11
}

class Aggregator(BaseAgent):
    def __init__(self):
        config = ModelConfig.get_model_config("aggregator")
        super().__init__(
            models=config["models"],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens"),
            timeout=config.get("timeout"),
            initial_model_index=config.get("initial_model_index")
        )

    @time_it
    async def aggregate(
        self, 
        session_data: Dict[str, Any], 
        last_intent: str, 
        pending_questions: Any = None, 
        session_id: str = None,
        user_input: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        on_sse_event: Optional[Callable] = None
    ) -> str:
        """
        汇总所有信息，生成给用户的回复。
        
        Args:
            session_data: 会话数据
            last_intent: 最后意图
            pending_questions: 待处理问题
            session_id: 会话ID（用于 token 追踪）
            user_input: 用户最新输入
            conversation_history: 最近对话历史（可选，最近3-5轮）
            on_sse_event: SSE事件回调函数
        """
        system_prompt = self.load_prompt("aggregator")
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # 构建 user_prompt（作为位置参数传入，映射到模板的 input 变量）
        user_prompt_parts = [f"当前日期: {current_date}"]
        if user_input:
            user_prompt_parts.append(f"用户最新输入: {user_input}")
        user_prompt = "\n".join(user_prompt_parts)
        
        # 判断是否是首次对话
        # 首次对话的判断标准：历史记录中没有 assistant 消息
        is_first_message = False
        if conversation_history:
            # 检查是否有 assistant 消息
            has_assistant_message = any(
                msg.get("role") == "assistant" 
                for msg in conversation_history
            )
            # 如果没有 assistant 消息，说明是首次对话
            if not has_assistant_message:
                is_first_message = True
        else:
            # 如果没有历史记录，认为是首次
            is_first_message = True
        
        # 格式化对话历史
        history_text = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-5:]:  # 最多最近5轮
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    history_lines.append(f"用户: {content}")
                elif role == "assistant":
                    history_lines.append(f"助手: {content}")
            if history_lines:
                history_text = "\n".join(history_lines)
        
        # 调用 run_chain
        # user_prompt 作为位置参数传入，会被映射到模板的 input 变量
        # 原始的 user_input 通过 latest_user_input 传递，避免与位置参数冲突
        # base.py 会自动处理，将 user_input 参数的值同时添加到 input 和 user_input 变量
        # 但这里我们需要传递原始的 user_input，所以通过 latest_user_input 传递
        
        # 收集所有缺失字段（来自 Worker 和 pending_questions）
        worker_missing_fields = session_data.get('worker_missing_fields', [])
        
        # 如果 pending_questions 是字符串列表，直接使用
        # 如果是对象列表，提取 field 或 content
        if pending_questions is None:
            pending_questions = session_data.get('pending_questions', [])
        
        # 处理 pending_questions 格式，提取字段名（这些是逻辑推理问题）
        pending_fields = []
        if isinstance(pending_questions, list) and len(pending_questions) > 0:
            if isinstance(pending_questions[0], dict):
                # 如果是对象列表，提取 field（如果存在）或 content（作为字段名）
                for q in pending_questions:
                    if isinstance(q, dict):
                        field = q.get('field') or q.get('content', '')
                        if field:
                            pending_fields.append(field)
            else:
                # 如果是字符串列表，直接作为字段名
                pending_fields = [str(q) for q in pending_questions]
        
        # 按模块分组缺失字段
        def group_by_module(fields: List[str]) -> Dict[str, List[str]]:
            """按模块分组字段"""
            module_fields = {}
            for field in fields:
                module = FIELD_TO_MODULE.get(field.lower(), "unknown")
                if module not in module_fields:
                    module_fields[module] = []
                module_fields[module].append(field)
            return module_fields
        
        # 分离缺失字段问题（Worker 识别）和逻辑推理问题（BackgroundReasoner 生成）
        worker_module_fields = group_by_module(worker_missing_fields)
        pending_module_fields = group_by_module(pending_fields)
        
        # 选择优先级最高的模块
        # 优先级规则：缺失字段问题（Worker 识别）> 逻辑推理问题（BackgroundReasoner 生成）
        selected_fields = []
        selected_module = None
        
        if worker_module_fields:
            # 优先处理缺失字段问题的模块
            selected_module = min(worker_module_fields.keys(), 
                                 key=lambda m: MODULE_PRIORITY.get(m, 99))
            selected_fields = worker_module_fields[selected_module]
            # 模块内按字段优先级排序
            selected_fields.sort(key=lambda f: FIELD_PRIORITY.get(f.lower(), 99))
            logger.info(f"选择缺失字段问题的模块: {selected_module}, 字段: {selected_fields}")
        elif pending_module_fields:
            # 如果没有缺失字段问题，处理逻辑推理问题
            selected_module = min(pending_module_fields.keys(),
                                 key=lambda m: MODULE_PRIORITY.get(m, 99))
            selected_fields = pending_module_fields[selected_module]
            selected_fields.sort(key=lambda f: FIELD_PRIORITY.get(f.lower(), 99))
            logger.info(f"选择逻辑推理问题的模块: {selected_module}, 字段: {selected_fields}")
        
        # 只传递一个模块的所有字段给 prompt
        all_missing_fields = selected_fields
        
        kwargs = {
            "resume_data": json.dumps(session_data.get('resume_data', {}), ensure_ascii=False),
            "inference_insights": json.dumps(session_data.get('inference_insights', []), ensure_ascii=False),
            "last_intent": last_intent,
            "missing_fields": json.dumps(all_missing_fields, ensure_ascii=False),  # 传递缺失字段数组（只包含一个模块的字段），由 LLM 生成问题
            "conversation_history": history_text if history_text else "",
            "is_first_message": is_first_message  # 传递首次对话标志
        }
        
        # 如果提供了原始用户输入，通过 latest_user_input 传递，base.py 会将其映射到 user_input
        if user_input:
            kwargs["latest_user_input"] = user_input
        
        return await self.run_chain(
            system_prompt, 
            user_prompt,  # 作为位置参数，映射到 input 变量
            json_mode=False,
            session_id=session_id,
            on_sse_event=on_sse_event,
            **kwargs
        )
