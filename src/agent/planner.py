import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger("resume-agent.planner")

@dataclass
class PlannerState:
    """
    Agent 的“短期记忆”：
    - slots: 槽位填充，记录已识别的关键信息
    - pending_questions: 待追问的问题队列
    """
    slots: Dict[str, Any] = field(default_factory=lambda: {
        "personal_info": {},
        "education": [],
        "work_experience": [],
        "skills": [],
        "project_experience": [],
        "honors_awards": [],
        "self_evaluation": [],
        "target_job": ""
    })
    pending_questions: List[str] = field(default_factory=list)


class Planner:
    """
    计划层 (Planner)：
    负责“听懂”用户在说什么，并决定“下一步该做什么”。
    它是 Agent 的大脑，负责意图识别和对话状态管理。
    """

    def __init__(self, state: Optional[PlannerState] = None) -> None:
        self.state = state or PlannerState()

    def ingest_user_message(self, text: str) -> None:
        """
        解析用户输入，提取槽位信息。
        """
        logger.info(f"正在解析用户输入: {text}")
        # 记录原始消息用于上下文参考
        self.state.slots["last_raw_message"] = text
        
        # --- 模拟更复杂的意图识别与槽位提取 ---
        
        # 1. 识别岗位意图
        if any(kw in text for kw in ["分析师", "投研", "金融"]):
            self.state.slots["target_job"] = "金融分析师"
            logger.info("识别到意向岗位: 金融分析师")
        elif any(kw in text for kw in ["开发", "程序员", "后端", "代码"]):
            self.state.slots["target_job"] = "软件开发工程师"
            logger.info("识别到意向岗位: 软件开发工程师")

        # 2. 简单的信息提取模拟 (实际应由 LLM 完成)
        if "姓名" in text or "叫" in text:
            # 模拟提取姓名
            self.state.slots["personal_info"]["name"] = "待提取" 
            
        # 3. 检查关键模块缺失
        if not self.state.slots["target_job"]:
            self._add_question("请问您的意向岗位是什么？")
        
        if "项目" in text and not any(kw in text for kw in ["成果", "收益", "提升", "实现"]):
            self._add_question("请补充该项目的量化成果（如增长率、收益或具体解决的问题）。")

    def _add_question(self, question: str) -> None:
        if question not in self.state.pending_questions:
            self.state.pending_questions.append(question)
            logger.info(f"发现信息缺失，已加入追问队列: {question}")

    def next_action(self) -> str:
        """
        基于当前状态决策下一步行动。
        逻辑：优先解决追问队列 -> 队列为空则进入生成阶段。
        """
        if self.state.pending_questions:
            next_q = self.state.pending_questions.pop(0)
            logger.info(f"决策：继续追问 -> {next_q}")
            return f"需要用户补充：{next_q}"
        
        logger.info("决策：信息已完备，准备进入生成流程")
        return "准备生成简历"
