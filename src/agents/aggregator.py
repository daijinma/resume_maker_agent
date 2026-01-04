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
    
    def check_module_completeness(self, resume_data: Dict[str, Any], module: str) -> bool:
        """
        检查模块是否完全完成（所有必须字段都有）
        
        Args:
            resume_data: 简历数据
            module: 模块名称（info, education, experience, skill）
        
        Returns:
            bool: 模块是否完全完成
        """
        if module == "info":
            personal_info = resume_data.get("personal_info", {})
            # 所有字段均为必须
            return bool(personal_info.get("name") and 
                       personal_info.get("phone") and 
                       personal_info.get("email"))
        elif module == "education":
            education = resume_data.get("education", [])
            if not education or len(education) == 0:
                return False
            # 检查第一条教育经历是否完整（所有字段均为必须）
            first_edu = education[0]
            return bool(first_edu.get("school") and 
                       first_edu.get("major") and 
                       first_edu.get("degree"))
        elif module == "experience":
            # 前置：必须有完整的个人信息和教育背景
            has_complete_info = self.check_module_completeness(resume_data, "info")
            has_complete_education = self.check_module_completeness(resume_data, "education")
            if not (has_complete_info and has_complete_education):
                return False
            # 检查工作经历是否完整（所有字段均为必须）
            experience = resume_data.get("experience", [])
            if not experience or len(experience) == 0:
                return False
            first_exp = experience[0]
            return bool(first_exp.get("company") and 
                       first_exp.get("role") and 
                       first_exp.get("period"))
        elif module == "skill":
            # 技能模块没有前置要求，只要有数据即可
            skills = resume_data.get("skills", [])
            return bool(skills and len(skills) > 0)
        return True
    
    def check_info_in_user_input(self, user_input: str, field: str) -> bool:
        """
        检查用户输入中是否已包含字段相关信息
        
        Args:
            user_input: 用户输入
            field: 字段名
        
        Returns:
            bool: 是否已包含相关信息
        """
        if not user_input:
            return False
        
        user_input_lower = user_input.lower()
        
        # 字段关键词映射
        field_keywords = {
            "school": ["学校", "大学", "毕业", "北大", "清华", "复旦", "交大"],
            "major": ["专业", "计算机网络", "计算机", "软件", "信息"],
            "degree": ["本科", "硕士", "博士", "学历", "学士", "研究生"],
            "name": ["我是", "叫", "姓名", "名字"],
            "phone": ["电话", "手机", "联系方式", "手机号"],
            "email": ["邮箱", "邮件", "email", "e-mail"],
            "company": ["公司", "工作", "就职", "任职"],
            "role": ["职位", "岗位", "担任", "负责"],
            "period": ["时间", "期间", "从", "到", "年", "月"]
        }
        
        keywords = field_keywords.get(field.lower(), [])
        return any(kw in user_input_lower for kw in keywords)
    
    def filter_fields_by_completeness(
        self, 
        fields: List[str], 
        resume_data: Dict[str, Any], 
        user_input: Optional[str] = None
    ) -> List[str]:
        """
        过滤已提供信息的字段
        
        Args:
            fields: 字段列表
            resume_data: 简历数据
            user_input: 用户输入
        
        Returns:
            过滤后的字段列表
        """
        filtered = []
        
        for field in fields:
            field_lower = field.lower()
            
            # 检查 resume_data 中是否已有该字段
            has_in_resume = False
            if field_lower == "name":
                has_in_resume = bool(resume_data.get("personal_info", {}).get("name"))
            elif field_lower == "phone":
                has_in_resume = bool(resume_data.get("personal_info", {}).get("phone"))
            elif field_lower == "email":
                has_in_resume = bool(resume_data.get("personal_info", {}).get("email"))
            elif field_lower in ["school", "major", "degree"]:
                education = resume_data.get("education", [])
                if education and len(education) > 0:
                    first_edu = education[0]
                    if field_lower == "school":
                        has_in_resume = bool(first_edu.get("school"))
                    elif field_lower == "major":
                        has_in_resume = bool(first_edu.get("major"))
                    elif field_lower == "degree":
                        has_in_resume = bool(first_edu.get("degree"))
            elif field_lower in ["company", "role", "period"]:
                experience = resume_data.get("experience", [])
                if experience and len(experience) > 0:
                    first_exp = experience[0]
                    if field_lower == "company":
                        has_in_resume = bool(first_exp.get("company"))
                    elif field_lower == "role":
                        has_in_resume = bool(first_exp.get("role"))
                    elif field_lower == "period":
                        has_in_resume = bool(first_exp.get("period"))
            
            # 检查用户输入中是否已提到
            has_in_input = False
            if user_input:
                has_in_input = self.check_info_in_user_input(user_input, field_lower)
            
            # 如果 resume_data 中已有或用户输入中已提到，跳过该字段
            if has_in_resume or has_in_input:
                logger.info(f"字段 {field} 已在 resume_data 或 user_input 中提供，跳过")
                continue
            
            filtered.append(field)
        
        return filtered

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
        
        # 限制对话历史长度（最多最近5轮）
        limited_history = None
        if conversation_history:
            limited_history = conversation_history[-5:]  # 最多最近5轮
        
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
        
        # 获取 resume_data 用于检查模块完成度
        resume_data = session_data.get('resume_data', {})
        
        # 选择优先级最高的模块
        # 优先级规则：缺失字段问题（Worker 识别）> 逻辑推理问题（BackgroundReasoner 生成）
        selected_fields = []
        selected_module = None
        
        # 如果是首次对话，强制选择 info 模块
        if is_first_message:
            # 检查 info 模块的缺失字段
            info_fields = worker_module_fields.get("info", []) + pending_module_fields.get("info", [])
            if info_fields:
                selected_module = "info"
                selected_fields = list(set(info_fields))  # 去重
                selected_fields.sort(key=lambda f: FIELD_PRIORITY.get(f.lower(), 99))
                logger.info(f"首次对话，强制选择 info 模块，字段: {selected_fields}")
            else:
                # 即使没有缺失字段，也要检查是否完整
                if not self.check_module_completeness(resume_data, "info"):
                    # 根据 resume_data 检查缺失的字段
                    personal_info = resume_data.get("personal_info", {})
                    missing_info_fields = []
                    if not personal_info.get("name"):
                        missing_info_fields.append("name")
                    if not personal_info.get("phone"):
                        missing_info_fields.append("phone")
                    if not personal_info.get("email"):
                        missing_info_fields.append("email")
                    if missing_info_fields:
                        selected_module = "info"
                        selected_fields = missing_info_fields
                        logger.info(f"首次对话，info 模块未完成，补充缺失字段: {selected_fields}")
        
        # 如果不是首次对话或首次对话没有选择模块，按正常流程选择
        if not selected_module:
            # 检查模块完成度，确保按顺序收集
            # 1. 检查 info 模块是否完成
            if not self.check_module_completeness(resume_data, "info"):
                # info 模块未完成，强制选择 info 模块
                info_fields = worker_module_fields.get("info", []) + pending_module_fields.get("info", [])
                if info_fields:
                    selected_module = "info"
                    selected_fields = list(set(info_fields))
                    selected_fields.sort(key=lambda f: FIELD_PRIORITY.get(f.lower(), 99))
                    logger.info(f"info 模块未完成，强制选择 info 模块，字段: {selected_fields}")
                else:
                    # 根据 resume_data 检查缺失的字段
                    personal_info = resume_data.get("personal_info", {})
                    missing_info_fields = []
                    if not personal_info.get("name"):
                        missing_info_fields.append("name")
                    if not personal_info.get("phone"):
                        missing_info_fields.append("phone")
                    if not personal_info.get("email"):
                        missing_info_fields.append("email")
                    if missing_info_fields:
                        selected_module = "info"
                        selected_fields = missing_info_fields
                        logger.info(f"info 模块未完成，补充缺失字段: {selected_fields}")
            
            # 2. 如果 info 完成，检查 education 模块
            elif not self.check_module_completeness(resume_data, "education"):
                # education 模块未完成，强制选择 education 模块
                education_fields = worker_module_fields.get("education", []) + pending_module_fields.get("education", [])
                if education_fields:
                    selected_module = "education"
                    selected_fields = list(set(education_fields))
                    selected_fields.sort(key=lambda f: FIELD_PRIORITY.get(f.lower(), 99))
                    logger.info(f"education 模块未完成，强制选择 education 模块，字段: {selected_fields}")
                else:
                    # 根据 resume_data 检查缺失的字段
                    education = resume_data.get("education", [])
                    missing_edu_fields = []
                    if not education or len(education) == 0:
                        missing_edu_fields = ["school", "major", "degree"]
                    else:
                        first_edu = education[0]
                        if not first_edu.get("school"):
                            missing_edu_fields.append("school")
                        if not first_edu.get("major"):
                            missing_edu_fields.append("major")
                        if not first_edu.get("degree"):
                            missing_edu_fields.append("degree")
                    if missing_edu_fields:
                        selected_module = "education"
                        selected_fields = missing_edu_fields
                        logger.info(f"education 模块未完成，补充缺失字段: {selected_fields}")
            
            # 3. 如果 info 和 education 都完成，检查 experience 模块
            elif not self.check_module_completeness(resume_data, "experience"):
                # experience 模块未完成，选择 experience 模块
                experience_fields = worker_module_fields.get("experience", []) + pending_module_fields.get("experience", [])
                if experience_fields:
                    selected_module = "experience"
                    selected_fields = list(set(experience_fields))
                    selected_fields.sort(key=lambda f: FIELD_PRIORITY.get(f.lower(), 99))
                    logger.info(f"experience 模块未完成，选择 experience 模块，字段: {selected_fields}")
                else:
                    # 根据 resume_data 检查缺失的字段
                    experience = resume_data.get("experience", [])
                    missing_exp_fields = []
                    if not experience or len(experience) == 0:
                        missing_exp_fields = ["company", "role", "period"]
                    else:
                        first_exp = experience[0]
                        if not first_exp.get("company"):
                            missing_exp_fields.append("company")
                        if not first_exp.get("role"):
                            missing_exp_fields.append("role")
                        if not first_exp.get("period"):
                            missing_exp_fields.append("period")
                    if missing_exp_fields:
                        selected_module = "experience"
                        selected_fields = missing_exp_fields
                        logger.info(f"experience 模块未完成，补充缺失字段: {selected_fields}")
            
            # 4. 如果所有前置模块都完成，按正常优先级选择
            else:
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
        
        # 过滤已提供信息的字段（检查 resume_data 和 user_input）
        if selected_fields:
            selected_fields = self.filter_fields_by_completeness(
                selected_fields, resume_data, user_input
            )
            logger.info(f"过滤后剩余字段: {selected_fields}")
        
        # 只传递一个模块的所有字段给 prompt
        all_missing_fields = selected_fields
        
        kwargs = {
            "resume_data": json.dumps(session_data.get('resume_data', {}), ensure_ascii=False),
            "inference_insights": json.dumps(session_data.get('inference_insights', []), ensure_ascii=False),
            "last_intent": last_intent,
            "missing_fields": json.dumps(all_missing_fields, ensure_ascii=False),  # 传递缺失字段数组（只包含一个模块的字段），由 LLM 生成问题
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
            conversation_history=limited_history,  # 作为消息历史传递，而不是放在 system prompt 中
            **kwargs
        )
