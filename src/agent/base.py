import time
import logging
import functools
import os
from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from src.config import Config

logger = logging.getLogger("resume-agent.base")

def time_it(func):
    """装饰器：记录 Agent 执行耗时"""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = await func(self, *args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Agent [{self.__class__.__name__}] 使用模型 [{self.model_name}] 执行耗时: {duration:.2f}s")
        # 将耗时和模型存入实例，方便后续统计
        self.last_duration = duration
        self.last_model = self.model_name
        return result
    return wrapper

class BaseAgent:
    def __init__(self, model: str, temperature: float = 0.3, tools: List = None):
        self.llm = ChatOpenAI(
            model=model,
            openai_api_key=Config.OPENROUTER_API_KEY,
            openai_api_base=Config.BASE_URL,
            default_headers=Config.DEFAULT_HEADERS,
            temperature=temperature
        )
        self.model_name = model
        self.last_duration = 0.0
        self.last_model = model
        self.tools = tools or []
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)

    def load_prompt(self, prompt_name: str) -> str:
        """从 src/prompts 目录加载提示词文件"""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            prompt_path = os.path.join(base_dir, "prompts", f"{prompt_name}.md")
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"加载提示词失败 [{prompt_name}]: {e}")
            return ""

    async def run_chain(self, system_prompt: str, user_input: str, json_mode: bool = True, on_tool_call=None, **kwargs):
        """构建并运行 LangChain 链"""
        logger.info(f"--- Agent [{self.__class__.__name__}] 开始调用 LLM ---")
        logger.info(f"模型: {self.model_name}")
        logger.info(f"输入内容: {user_input[:200]}..." if len(user_input) > 200 else f"输入内容: {user_input}")
        
        # 将提示词中的 {% var %} 转换为 jinja2 的 {{ var }}
        system_prompt_jinja = system_prompt.replace("{%", "{{").replace("%}", "}}")
        
        if not self.tools:
            user_template_jinja = "{%input%}".replace("{%", "{{").replace("%}", "}}")
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_jinja),
                ("user", user_template_jinja)
            ], template_format="jinja2")
            
            if json_mode:
                chain = prompt | self.llm | JsonOutputParser()
            else:
                chain = prompt | self.llm | StrOutputParser()
            
            # 合并输入变量
            invoke_vars = {"input": user_input}
            invoke_vars.update(kwargs)
            result = await chain.ainvoke(invoke_vars)
        else:
            # 带工具调用的逻辑
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_jinja),
                ("user", "{%input%}".replace("{%", "{{").replace("%}", "}}"))
            ], template_format="jinja2")
            
            invoke_vars = {"input": user_input}
            invoke_vars.update(kwargs)
            messages = prompt.format_messages(**invoke_vars)
            
            response = await self.llm_with_tools.ainvoke(messages)
            
            while response.tool_calls:
                messages.append(response)
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"].lower()
                    selected_tool = next((t for t in self.tools if t.name.lower() == tool_name), None)
                    if selected_tool:
                        # 触发回调，用于 SSE 输出
                        if on_tool_call:
                            await on_tool_call(tool_name, tool_call["args"])
                        
                        tool_output = await selected_tool.ainvoke(tool_call["args"])
                        messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
                
                response = await self.llm_with_tools.ainvoke(messages)
            
            result = response.content
            if json_mode:
                try:
                    # 尝试直接解析
                    import json
                    result = json.loads(result)
                except:
                    # 如果解析失败，尝试从文本中提取 JSON
                    import re
                    json_match = re.search(r'\{.*\}', result, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                        except:
                            result = {"error": "JSON 解析失败", "raw": result}
                    else:
                        result = {"error": "未找到 JSON", "raw": result}
        
        logger.info(f"输出结果: {str(result)[:200]}..." if len(str(result)) > 200 else f"输出结果: {result}")
        logger.info(f"--- Agent [{self.__class__.__name__}] 调用结束 ---")
        return result
