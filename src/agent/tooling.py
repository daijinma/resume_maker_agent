import logging
from typing import Any, Dict

logger = logging.getLogger("resume-agent.tooling")

class Tooling:
    """
    工具层 (Tooling)：
    Agent 的“外部技能库”。
    负责提供非 LLM 的辅助功能，如：
    - 检索简历模板
    - 格式转换 (Markdown to PDF)
    - 敏感词过滤
    - 语言润色工具接入
    """

    def __init__(self) -> None:
        self.label = "简历辅助工具集"

    def fetch_template(self, role: str) -> Dict[str, str]:
        """
        根据识别到的岗位，获取对应的简历模板或参考范文。
        """
        logger.info(f"正在检索岗位【{role}】的参考模板...")
        templates = {
            "金融分析师": {
                "project": "重点突出量化模型、收益率和风险控制。",
                "skill": "CFA, Python (Pandas), SQL, 风险建模。"
            },
            "软件开发工程师": {
                "project": "重点突出技术栈、高并发处理、系统架构优化。",
                "skill": "Java/Python, Docker, Kubernetes, 微服务。"
            }
        }
        return templates.get(role, {"project": "通用项目描述模板", "skill": "通用技能模板"})

    def refine_language(self, content: str) -> str:
        """
        对生成的文本进行最后的格式化处理。
        """
        logger.info("正在进行最后的文本润色与格式化...")
        return content.strip()
