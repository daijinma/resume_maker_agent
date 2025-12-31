import time
import logging
import functools
import os
from typing import Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from src.config.models import ModelConfig
from src.utils.token_tracker import get_token_tracker

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
            openai_api_key=ModelConfig.OPENROUTER_API_KEY,
            openai_api_base=ModelConfig.BASE_URL,
            default_headers=ModelConfig.DEFAULT_HEADERS,
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

    async def run_chain(
        self, 
        system_prompt: str, 
        user_input: str, 
        json_mode: bool = True, 
        on_tool_call=None,
        session_id: Optional[str] = None,
        **kwargs
    ):
        """
        构建并运行 LangChain 链
        
        Args:
            system_prompt: 系统提示词
            user_input: 用户输入
            json_mode: 是否使用 JSON 模式
            on_tool_call: 工具调用回调
            session_id: 会话ID（用于 token 追踪）
            **kwargs: 其他参数
        """
        logger.info(f"--- Agent [{self.__class__.__name__}] 开始调用 LLM ---")
        logger.info(f"模型: {self.model_name}")
        logger.info(f"输入内容: {user_input[:200]}..." if len(user_input) > 200 else f"输入内容: {user_input}")
        
        # 将提示词中的 {% var %} 转换为 jinja2 的 {{ var }}
        system_prompt_jinja = system_prompt.replace("{%", "{{").replace("%}", "}}")
        
        total_input_tokens = 0
        total_output_tokens = 0
        last_response = None
        
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
            
            # 对于链式调用，需要手动调用 LLM 来获取响应元数据
            if json_mode:
                # 先获取 LLM 响应
                llm_response = await (prompt | self.llm).ainvoke(invoke_vars)
                last_response = llm_response
                # 然后解析
                parser = JsonOutputParser()
                result = parser.parse(llm_response.content)
            else:
                # 先获取 LLM 响应
                llm_response = await (prompt | self.llm).ainvoke(invoke_vars)
                last_response = llm_response
                # 然后解析
                parser = StrOutputParser()
                result = parser.parse(llm_response.content)
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
            last_response = response
            
            # 累计所有响应的 token（带工具调用时可能有多次 LLM 调用）
            all_responses = [response]
            
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
                all_responses.append(response)
                last_response = response
            
            # 保存所有响应以便后续 token 统计
            self._all_responses = all_responses
            
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
        
        # 提取并记录 token 使用情况
        if last_response and session_id:
            try:
                # 对于带工具调用的情况，需要累计所有响应的 token
                if self.tools and hasattr(self, '_all_responses'):
                    responses_to_check = self._all_responses
                else:
                    responses_to_check = [last_response]
                
                total_input_tokens = 0
                total_output_tokens = 0
                
                for resp in responses_to_check:
                    # 尝试从 response_metadata 获取 token 使用信息
                    usage = None
                    if hasattr(resp, 'response_metadata'):
                        metadata = resp.response_metadata
                        if metadata:
                            # OpenRouter/OpenAI 格式
                            usage = metadata.get('token_usage') or metadata.get('usage')
                            # 如果还是 None，尝试其他可能的键
                            if not usage:
                                usage = metadata.get('openai_usage') or metadata.get('openrouter_usage')
                    
                    # 如果从 metadata 获取失败，尝试从响应对象直接获取
                    if not usage and hasattr(resp, 'usage'):
                        usage = resp.usage
                    
                    if usage:
                        if isinstance(usage, dict):
                            input_tokens = usage.get('prompt_tokens') or usage.get('input_tokens') or 0
                            output_tokens = usage.get('completion_tokens') or usage.get('output_tokens') or 0
                        else:
                            # 如果是对象，尝试属性访问
                            input_tokens = getattr(usage, 'prompt_tokens', None) or getattr(usage, 'input_tokens', 0) or 0
                            output_tokens = getattr(usage, 'completion_tokens', None) or getattr(usage, 'output_tokens', 0) or 0
                        
                        total_input_tokens += input_tokens
                        total_output_tokens += output_tokens
                
                # 如果无法从任何响应获取 token 信息，使用 tiktoken 估算（作为后备方案）
                if total_input_tokens == 0 and total_output_tokens == 0:
                    import tiktoken
                    try:
                        # 尝试获取编码器（根据模型选择）
                        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # 默认编码器
                        total_input_tokens = len(encoding.encode(system_prompt + user_input))
                        total_output_tokens = len(encoding.encode(str(result))) if result else 0
                        logger.warning(f"无法从响应获取 token 使用信息，使用 tiktoken 估算")
                    except:
                        total_input_tokens = 0
                        total_output_tokens = 0
                        logger.warning(f"无法获取或估算 token 使用信息")
                
                # 确定 agent_type
                agent_type = self._get_agent_type()
                
                # 记录 token 使用
                token_tracker = get_token_tracker()
                await token_tracker.record_usage(
                    session_id=session_id,
                    agent_type=agent_type,
                    agent_class=self.__class__.__name__,
                    model_name=self.model_name,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens
                )
                
                logger.info(f"Token 使用: 输入={total_input_tokens}, 输出={total_output_tokens}, 总计={total_input_tokens + total_output_tokens}")
            except Exception as e:
                # Token 记录失败不应影响主业务逻辑
                logger.error(f"记录 token 使用情况失败: {e}", exc_info=True)
        
        logger.info(f"输出结果: {str(result)[:200]}..." if len(str(result)) > 200 else f"输出结果: {result}")
        logger.info(f"--- Agent [{self.__class__.__name__}] 调用结束 ---")
        return result
    
    def _get_agent_type(self) -> str:
        """根据 Agent 类名确定 agent_type"""
        class_name = self.__class__.__name__.lower()
        
        if 'router' in class_name:
            return 'router'
        elif 'info' in class_name:
            return 'info_worker'
        elif 'experience' in class_name:
            return 'experience_worker'
        elif 'skill' in class_name:
            return 'skill_worker'
        elif 'inference' in class_name:
            return 'inference'
        elif 'aggregator' in class_name:
            return 'aggregator'
        else:
            return 'unknown'
