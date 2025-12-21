import os
import logging
import json
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger("resume-agent.executor")

class Executor:
    """
    执行层 (Executor)：
    负责具体的“干活”任务。
    主要职责是调用 LLM 生成结构化的简历 JSON 数据。
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/copilot",
                "X-Title": "Resume Agent Demo",
            }
        )
        self.model = "meta-llama/llama-3.3-70b-instruct:free"

    async def generate_full_resume(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 LLM 生成完整的结构化简历。
        """
        logger.info("正在生成完整结构化简历...")
        
prompt = (
            f"你是一个专业的简历撰写专家。请根据以下收集到的原始信息，生成一份完整的结构化简历。\n"
            f"要求：\n"
            f"1. 严格遵守提供的 JSON 格式。\n"
            f"2. 润色所有描述，使其专业、精炼，突出成果。\n"
            f"3. 如果某些信息缺失，请根据上下文合理推断或留空，不要编造虚假事实。\n"
            f"4. 'txt' 字段应包含清洗后的、适合直接阅读的完整 Markdown 格式简历文本。\n\n"
            f"原始信息：{json.dumps(slots, ensure_ascii=False)}\n\n"
            f"必须返回以下 JSON 格式，不要包含任何其他解释文字：\n"
            "{\n"
            "  \"result\": {\n"
            "    \"personal_info\": {\"name\": \"\", \"gender\": \"\", \"age\": \"\", \"phone\": \"\", \"email\": \"\", \"target_job\": \"\"},\n"
            "    \"education\": [{\"period\": \"\", \"school\": \"\", \"major\": \"\"}],\n"
            "    \"work_experience\": [{\"period\": \"\", \"company\": \"\", \"position\": \"\", \"responsibilities\": []}],\n"
            "    \"skills\": [],\n"
            "    \"project_experience\": [{\"name\": \"\", \"period\": \"\", \"project_description\": \"\", \"responsibilities\": []}],\n"
            "    \"honors_awards\": [],\n"
            "    \"self_evaluation\": []\n"
            "  },\n"
            "  \"txt\": \"<完整简历文本>\"\n"
            "}\n"
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个只输出 JSON 的简历专家。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" },
                temperature=0.3,
            )
            content = response.choices[0].message.content
            logger.info("LLM 结构化内容生成成功")
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM 生成失败: {str(e)}")
            return {"error": str(e), "status": "failed"}

    def validate(self, result: Dict[str, Any]) -> Dict[str, bool]:
        """
        后置校验：检查 JSON 结构是否完整。
        """
        if "result" not in result or "txt" not in result:
            return {"passed": False, "reason": "Missing core fields"}
        
        res = result["result"]
        has_name = bool(res.get("personal_info", {}).get("name"))
        has_experience = len(res.get("work_experience", [])) > 0 or len(res.get("project_experience", [])) > 0
        
        return {
            "has_name": has_name,
            "has_experience": has_experience,
            "passed": has_name and has_experience
        }
