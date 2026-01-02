import time
import logging
import functools
import os
import re
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from src.config.models import ModelConfig
from src.utils.token_tracker import get_token_tracker

logger = logging.getLogger("resume-agent.base")

# 尝试导入 RateLimitError
try:
    from openai import RateLimitError
except ImportError:
    RateLimitError = None

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
    def __init__(
        self, 
        models: Union[str, List[str]], 
        temperature: float = 0.3, 
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        tools: List = None,
        initial_model_index: Optional[int] = None
    ):
        """
        初始化 BaseAgent
        
        Args:
            models: 模型名称（字符串）或模型列表（支持多个备选模型）
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间（秒）
            tools: 工具列表
            initial_model_index: 初始模型索引（用于轮询分配，避免并发agent使用同一模型）
        """
        # 确保 models 是列表格式
        if isinstance(models, str):
            self.models = [models]
        elif isinstance(models, list):
            self.models = models if models else ["meta-llama/llama-3.2-3b-instruct:free"]
        else:
            self.models = ["meta-llama/llama-3.2-3b-instruct:free"]
        
        # 确保模型列表不为空
        if not self.models:
            self.models = ["meta-llama/llama-3.2-3b-instruct:free"]
        
        # 设置初始模型索引（用于轮询分配）
        if initial_model_index is not None:
            # 确保索引在有效范围内
            self.current_model_index = initial_model_index % len(self.models)
        else:
            self.current_model_index = 0
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.tools = tools or []
        
        # 获取 OpenRouter 配置
        openrouter_config = ModelConfig.get_openrouter_config()
        
        # 创建第一个模型的 LLM 客户端
        self.llm = self._create_llm_client(
            self.models[self.current_model_index],
            openrouter_config
        )
        self.model_name = self.models[self.current_model_index]
        self.last_duration = 0.0
        self.last_model = self.model_name
        
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    def _create_llm_client(self, model: str, openrouter_config: Dict[str, Any]) -> ChatOpenAI:
        """创建指定模型的 LLM 客户端"""
        client_kwargs = {
            "model": model,
            "openai_api_key": openrouter_config.get("api_key"),
            "openai_api_base": openrouter_config.get("base_url"),
            "default_headers": openrouter_config.get("default_headers", {}),
            "temperature": self.temperature
        }
        
        # 添加可选参数
        if self.max_tokens is not None:
            client_kwargs["max_tokens"] = self.max_tokens
        
        if self.timeout is not None:
            client_kwargs["timeout"] = self.timeout
        
        return ChatOpenAI(**client_kwargs)
    
    def _switch_to_next_model(self, on_sse_event=None, reason: str = "rate_limit_error") -> bool:
        """
        切换到下一个模型
        
        Args:
            on_sse_event: SSE事件回调函数
            reason: 切换原因
        
        Returns:
            bool: 是否成功切换到下一个模型
        """
        if self.current_model_index + 1 >= len(self.models):
            logger.warning(f"所有模型都已尝试，无法切换到下一个模型")
            return False
        
        old_model = self.model_name
        self.current_model_index += 1
        new_model = self.models[self.current_model_index]
        
        logger.info(f"切换到下一个模型: {new_model} (索引: {self.current_model_index})")
        
        # 获取 OpenRouter 配置
        openrouter_config = ModelConfig.get_openrouter_config()
        
        # 创建新的 LLM 客户端
        self.llm = self._create_llm_client(new_model, openrouter_config)
        self.model_name = new_model
        
        # 重新绑定工具（如果有）
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # 注意：模型切换事件的发送在 _invoke_with_retry 中处理（异步上下文）
        return True
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        检测是否为 429 限流错误
        
        Args:
            error: 异常对象
        
        Returns:
            bool: 是否为限流错误
        """
        # 检查是否为 RateLimitError
        if RateLimitError and isinstance(error, RateLimitError):
            return True
        
        # 检查错误消息中是否包含 429 或 rate limit
        error_str = str(error).lower()
        if "429" in error_str or "rate limit" in error_str or "rate-limited" in error_str:
            return True
        
        # 检查错误代码
        if hasattr(error, "status_code") and error.status_code == 429:
            return True
        
        if hasattr(error, "code") and error.code == 429:
            return True
        
        # 检查响应中的错误信息
        if hasattr(error, "response"):
            try:
                if hasattr(error.response, "json"):
                    error_data = error.response.json()
                    if isinstance(error_data, dict):
                        error_info = error_data.get("error", {})
                        if isinstance(error_info, dict):
                            code = error_info.get("code")
                            if code == 429:
                                return True
            except:
                pass
        
        return False

    async def _invoke_with_retry(self, invoke_func, context: str = "", on_sse_event=None):
        """
        执行 LLM 调用，支持 429 错误自动切换模型
        
        Args:
            invoke_func: 调用函数（lambda 表达式）
            context: 上下文描述（用于日志）
            on_sse_event: SSE事件回调函数
        
        Returns:
            LLM 响应对象
        
        Raises:
            最后一个异常（如果所有模型都失败）
        """
        last_error = None
        initial_model_index = self.current_model_index
        
        while True:
            try:
                result = await invoke_func()
                # 如果成功，记录使用的模型
                if self.current_model_index != initial_model_index:
                    logger.info(f"成功使用备用模型 [{self.model_name}] (上下文: {context})")
                return result
            except Exception as e:
                # 检查是否为 429 错误
                if self._is_rate_limit_error(e):
                    logger.warning(
                        f"检测到 429 限流错误 (模型: {self.model_name}, 上下文: {context}): {str(e)[:200]}"
                    )
                    
                    # 尝试切换到下一个模型
                    old_model_before_switch = self.model_name
                    if self._switch_to_next_model(on_sse_event=on_sse_event, reason="rate_limit_error"):
                        logger.info(f"已切换到模型 [{self.model_name}]，重新尝试 (上下文: {context})")
                        # 发送模型切换事件
                        if on_sse_event:
                            agent_type = self._get_agent_type()
                            try:
                                if asyncio.iscoroutinefunction(on_sse_event):
                                    await on_sse_event("model_switch", {
                                        "agent_type": agent_type,
                                        "agent_class": self.__class__.__name__,
                                        "old_model": old_model_before_switch,
                                        "new_model": self.model_name,
                                        "reason": "rate_limit_error"
                                    })
                                else:
                                    on_sse_event("model_switch", {
                                        "agent_type": agent_type,
                                        "agent_class": self.__class__.__name__,
                                        "old_model": old_model_before_switch,
                                        "new_model": self.model_name,
                                        "reason": "rate_limit_error"
                                    })
                            except Exception as evt_error:
                                logger.warning(f"发送模型切换事件失败: {evt_error}")
                        last_error = e
                        continue  # 继续尝试
                    else:
                        # 所有模型都已尝试
                        logger.error(f"所有模型都已尝试，无法继续 (上下文: {context})")
                        raise e
                else:
                    # 非 429 错误，直接抛出
                    raise e
        
        # 理论上不会到达这里
        if last_error:
            raise last_error
        raise Exception("未知错误")
    
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
    
    def _stream_with_retry(self, stream_func, context: str = "", on_sse_event=None):
        """
        流式调用 LLM，支持 429 错误自动切换模型
        
        Args:
            stream_func: 返回异步迭代器的函数（可能是普通函数或异步函数）
            context: 上下文描述（用于日志）
            on_sse_event: SSE事件回调函数
            
        Returns:
            异步迭代器
        """
        async def _stream_generator():
            last_error = None
            initial_model_index = self.current_model_index
            
            while True:
                try:
                    # 调用流式函数获取迭代器
                    # 检查 stream_func 是否是协程函数
                    if asyncio.iscoroutinefunction(stream_func):
                        stream_iterable = await stream_func()
                    else:
                        stream_iterable = stream_func()
                    
                    # 检查 stream_iterable 是否是协程（需要 await）
                    if asyncio.iscoroutine(stream_iterable):
                        stream_iterable = await stream_iterable
                    
                    # 迭代流式响应
                    import time
                    stream_chunk_count = 0
                    first_stream_chunk_time = None
                    
                    # #region agent log
                    _write_debug_log_stream = lambda d: None
                    try:
                        import json
                        def _write_debug_log_stream(data: dict):
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
                            except: pass
                    except: pass
                    # #endregion
                    
                    async for chunk in stream_iterable:
                        stream_chunk_count += 1
                        stream_chunk_time = time.time()
                        if first_stream_chunk_time is None:
                            first_stream_chunk_time = stream_chunk_time
                        
                        # #region agent log
                        _write_debug_log_stream({
                            "hypothesisId": "A",
                            "location": "base.py:307",
                            "message": "Chunk yielded from stream_iterable",
                            "data": {
                                "stream_chunk_count": stream_chunk_count,
                                "time_since_first_stream_chunk": stream_chunk_time - first_stream_chunk_time if first_stream_chunk_time else 0
                            }
                        })
                        # #endregion
                        
                        yield chunk
                    
                    # 如果成功迭代完成，退出循环
                    return
                    
                except Exception as e:
                    # 检查是否为 429 错误
                    if self._is_rate_limit_error(e):
                        logger.warning(
                            f"检测到 429 限流错误 (模型: {self.model_name}, 上下文: {context}): {str(e)[:200]}"
                        )
                        
                        # 尝试切换到下一个模型
                        old_model_before_switch = self.model_name
                        if self._switch_to_next_model(on_sse_event=on_sse_event, reason="rate_limit_error"):
                            logger.info(f"已切换到模型 [{self.model_name}]，重新尝试流式调用 (上下文: {context})")
                            # 发送模型切换事件
                            if on_sse_event:
                                agent_type = self._get_agent_type()
                                try:
                                    if asyncio.iscoroutinefunction(on_sse_event):
                                        await on_sse_event("model_switch", {
                                            "agent_type": agent_type,
                                            "agent_class": self.__class__.__name__,
                                            "old_model": old_model_before_switch,
                                            "new_model": self.model_name,
                                            "reason": "rate_limit_error"
                                        })
                                    else:
                                        on_sse_event("model_switch", {
                                            "agent_type": agent_type,
                                            "agent_class": self.__class__.__name__,
                                            "old_model": old_model_before_switch,
                                            "new_model": self.model_name,
                                            "reason": "rate_limit_error"
                                        })
                                except Exception as evt_error:
                                    logger.warning(f"发送模型切换事件失败: {evt_error}")
                            last_error = e
                            continue  # 继续尝试
                        else:
                            # 所有模型都已尝试
                            logger.error(f"所有模型都已尝试，无法继续流式调用 (上下文: {context})")
                            raise e
                    else:
                        # 非 429 错误，直接抛出
                        raise e
        
        return _stream_generator()
    
    async def _stream_llm_response(self, stream_iterable, on_sse_event=None):
        """
        流式调用 LLM 并累积响应
        
        Args:
            stream_iterable: 异步迭代器（来自 astream()）
            on_sse_event: SSE事件回调函数
            
        Returns:
            完整的响应对象（AIMessage）
        """
        accumulated_content = ""
        full_response = None
        last_chunk = None
        import time
        
        # #region agent log
        chunk_count = 0
        first_chunk_time = None
        _write_debug_log = lambda d: None
        try:
            import json
            def _write_debug_log(data: dict):
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
                except: pass
        except: pass
        # #endregion
        
        try:
            async for chunk in stream_iterable:
                chunk_count += 1
                chunk_arrival_time = time.time()
                if first_chunk_time is None:
                    first_chunk_time = chunk_arrival_time
                
                # #region agent log
                _write_debug_log({
                    "hypothesisId": "A",
                    "location": "base.py:374",
                    "message": "Chunk arrived from LLM",
                    "data": {
                        "chunk_count": chunk_count,
                        "chunk_size": len(str(chunk.content if hasattr(chunk, 'content') else chunk)),
                        "time_since_first": chunk_arrival_time - first_chunk_time if first_chunk_time else 0
                    }
                })
                # #endregion
                
                last_chunk = chunk
                
                # 累积内容
                if hasattr(chunk, 'content'):
                    # 如果是 AIMessage 对象（或 AIMessageChunk）
                    chunk_content = chunk.content
                    if isinstance(chunk_content, str):
                        # 累积增量内容
                        accumulated_content += chunk_content
                        # 保存最后一个 chunk 作为基础（但最终会更新 content）
                        full_response = chunk
                        
                        # 发送 partial 事件
                        if on_sse_event and chunk_content:
                            callback_start = time.time()
                            try:
                                # #region agent log
                                _write_debug_log({
                                    "hypothesisId": "B",
                                    "location": "base.py:391",
                                    "message": "Before calling on_sse_event callback",
                                    "data": {
                                        "chunk_content_len": len(chunk_content),
                                        "accumulated_len": len(accumulated_content)
                                    }
                                })
                                # #endregion
                                
                                if asyncio.iscoroutinefunction(on_sse_event):
                                    await on_sse_event("partial", {
                                        "content": chunk_content,
                                        "accumulated": accumulated_content
                                    })
                                else:
                                    on_sse_event("partial", {
                                        "content": chunk_content,
                                        "accumulated": accumulated_content
                                    })
                                
                                # #region agent log
                                callback_duration = time.time() - callback_start
                                _write_debug_log({
                                    "hypothesisId": "B",
                                    "location": "base.py:400",
                                    "message": "After calling on_sse_event callback",
                                    "data": {
                                        "callback_duration_ms": callback_duration * 1000
                                    }
                                })
                                # #endregion
                            except Exception as e:
                                logger.warning(f"发送 partial 事件失败: {e}")
                elif isinstance(chunk, str):
                    # 如果是字符串
                    accumulated_content += chunk
                    
                    # 发送 partial 事件
                    if on_sse_event and chunk:
                        try:
                            if asyncio.iscoroutinefunction(on_sse_event):
                                await on_sse_event("partial", {
                                    "content": chunk,
                                    "accumulated": accumulated_content
                                })
                            else:
                                on_sse_event("partial", {
                                    "content": chunk,
                                    "accumulated": accumulated_content
                                })
                        except Exception as e:
                            logger.warning(f"发送 partial 事件失败: {e}")
                else:
                    # 其他类型，尝试转换为字符串
                    chunk_str = str(chunk)
                    accumulated_content += chunk_str
                    
                    if on_sse_event and chunk_str:
                        try:
                            if asyncio.iscoroutinefunction(on_sse_event):
                                await on_sse_event("partial", {
                                    "content": chunk_str,
                                    "accumulated": accumulated_content
                                })
                            else:
                                on_sse_event("partial", {
                                    "content": chunk_str,
                                    "accumulated": accumulated_content
                                })
                        except Exception as e:
                            logger.warning(f"发送 partial 事件失败: {e}")
            
            # 构建完整的响应对象，确保包含所有累积的内容
            from langchain_core.messages import AIMessage
            
            # 确保使用累积的完整内容
            final_content = accumulated_content if accumulated_content else ""
            
            if full_response is None:
                # 如果没有 full_response，创建新的 AIMessage
                if last_chunk and hasattr(last_chunk, 'content'):
                    # 使用最后一个 chunk 的元数据，但使用累积的完整内容
                    full_response = AIMessage(
                        content=final_content,
                        response_metadata=getattr(last_chunk, 'response_metadata', None),
                        id_=getattr(last_chunk, 'id_', None),
                        tool_calls=getattr(last_chunk, 'tool_calls', None)
                    )
                else:
                    full_response = AIMessage(content=final_content)
            else:
                # 如果已有 full_response，创建新的 AIMessage 确保 content 是完整的累积内容
                # 注意：即使 full_response.content 看起来正确，也要使用累积内容以确保完整性
                full_response = AIMessage(
                    content=final_content,
                    response_metadata=getattr(full_response, 'response_metadata', None),
                    id_=getattr(full_response, 'id_', None),
                    tool_calls=getattr(full_response, 'tool_calls', None)
                )
            
            # 记录日志以便调试
            if not final_content:
                logger.warning(f"流式响应累积内容为空，last_chunk: {last_chunk}, full_response: {full_response}")
            
            return full_response
        except Exception as e:
            logger.error(f"流式调用失败: {e}", exc_info=True)
            # 如果流式调用失败，尝试创建一个包含累积内容的响应对象
            if accumulated_content:
                from langchain_core.messages import AIMessage
                return AIMessage(content=accumulated_content)
            raise

    async def run_chain(
        self, 
        system_prompt: str, 
        user_input: str, 
        json_mode: bool = True, 
        on_tool_call=None,
        session_id: Optional[str] = None,
        on_sse_event=None,
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
            on_sse_event: SSE事件回调函数，签名: async def on_sse_event(event_type: str, data: dict)
            **kwargs: 其他参数
        """
        logger.info(f"--- Agent [{self.__class__.__name__}] 开始调用 LLM ---")
        logger.info(f"模型: {self.model_name}")
        logger.info(f"输入内容: {user_input[:200]}..." if len(user_input) > 200 else f"输入内容: {user_input}")
        
        # 发送模型请求开始事件
        if on_sse_event:
            agent_type = self._get_agent_type()
            input_preview = user_input[:200] + "..." if len(user_input) > 200 else user_input
            try:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("model_request", {
                        "agent_type": agent_type,
                        "agent_class": self.__class__.__name__,
                        "model_name": self.model_name,
                        "input_preview": input_preview
                    })
                else:
                    on_sse_event("model_request", {
                        "agent_type": agent_type,
                        "agent_class": self.__class__.__name__,
                        "model_name": self.model_name,
                        "input_preview": input_preview
                    })
            except Exception as e:
                logger.warning(f"发送模型请求事件失败: {e}")
        
        # 记录模型调用开始时间
        start_time = time.time()
        
        # 将提示词中的 {% var %} 转换为 jinja2 的 {{ var }}，但不转换控制语句如 {% if %}, {% endif %}
        # 匹配变量模式：{% variable_name %}，其中 variable_name 不包含空格且不是控制关键字
        control_keywords = {'if', 'endif', 'for', 'endfor', 'else', 'elif', 'macro', 'endmacro', 'set', 'block', 'endblock'}
        def convert_var_to_jinja(match):
            var_content = match.group(1).strip()
            # 如果是控制关键字，保持原样
            if var_content.split()[0] in control_keywords:
                return match.group(0)  # 保持原样
            # 否则转换为 {{ }} 语法
            return f"{{{{ {var_content} }}}}"
        
        system_prompt_jinja = re.sub(r'\{\%\s*([^%]+?)\s*\%\}', convert_var_to_jinja, system_prompt)
        
        total_input_tokens = 0
        total_output_tokens = 0
        last_response = None
        
        if not self.tools:
            user_template_jinja = "{{input}}"
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_jinja),
                ("user", user_template_jinja)
            ], template_format="jinja2")
            
            # 合并输入变量
            # 将 user_input 位置参数映射到 input 变量（用于用户消息模板）
            # 如果 kwargs 中有 latest_user_input，将其映射到 user_input 变量（用于系统提示模板）
            # 这样模板可以同时使用 {{input}} 和 {{user_input}}
            invoke_vars = {"input": user_input}
            if "latest_user_input" in kwargs:
                invoke_vars["user_input"] = kwargs.pop("latest_user_input")
            else:
                # 如果没有 latest_user_input，使用 user_input 位置参数的值
                invoke_vars["user_input"] = user_input
            invoke_vars.update(kwargs)
            
            # 使用流式调用 LLM，支持 429 错误自动切换模型
            def get_stream():
                return (prompt | self.llm).astream(invoke_vars)
            
            # 流式调用并累积响应
            stream_iterable = self._stream_with_retry(
                get_stream,
                "无工具调用流式",
                on_sse_event=on_sse_event
            )
            llm_response = await self._stream_llm_response(
                stream_iterable,
                on_sse_event=on_sse_event
            )
            
            last_response = llm_response
            
            if json_mode:
                parser = JsonOutputParser()
                result = parser.parse(llm_response.content)
            else:
                parser = StrOutputParser()
                result = parser.parse(llm_response.content)
        else:
            # 带工具调用的逻辑
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_jinja),
                ("user", "{{input}}")
            ], template_format="jinja2")
            
            # 处理输入变量
            # 将 user_input 位置参数映射到 input 变量（用于用户消息模板）
            # 如果 kwargs 中有 latest_user_input，将其映射到 user_input 变量（用于系统提示模板）
            invoke_vars = {"input": user_input}
            if "latest_user_input" in kwargs:
                invoke_vars["user_input"] = kwargs.pop("latest_user_input")
            else:
                # 如果没有 latest_user_input，使用 user_input 位置参数的值
                invoke_vars["user_input"] = user_input
            invoke_vars.update(kwargs)
            messages = prompt.format_messages(**invoke_vars)
            
            # 使用流式调用 LLM（带工具调用），支持 429 错误自动切换模型
            def get_stream_with_tools():
                return self.llm_with_tools.astream(messages)
            
            # 流式调用并累积响应
            stream_iterable = self._stream_with_retry(
                get_stream_with_tools,
                "工具调用初始流式",
                on_sse_event=on_sse_event
            )
            response = await self._stream_llm_response(
                stream_iterable,
                on_sse_event=on_sse_event
            )
            last_response = response
            
            # 累计所有响应的 token（带工具调用时可能有多次 LLM 调用）
            all_responses = [response]
            
            while response.tool_calls:
                messages.append(response)
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"].lower()
                    selected_tool = next((t for t in self.tools if t.name.lower() == tool_name), None)
                    if selected_tool:
                        # 记录工具调用开始时间
                        tool_start_time = time.time()
                        
                        # 触发回调，用于 SSE 输出（先不传耗时，因为还没执行完）
                        if on_tool_call:
                            await on_tool_call(tool_name, tool_call["args"])
                        
                        # 执行工具调用
                        tool_output = await selected_tool.ainvoke(tool_call["args"])
                        
                        # 计算工具调用耗时
                        tool_duration = time.time() - tool_start_time
                        
                        # 工具调用完成后，通过回调传递耗时信息（如果回调支持）
                        if on_tool_call:
                            try:
                                # 尝试传递耗时信息（如果回调支持额外的 duration 参数）
                                import inspect
                                sig = inspect.signature(on_tool_call)
                                # 检查回调是否支持 duration 参数
                                if 'duration' in sig.parameters or len(sig.parameters) >= 3:
                                    # 如果支持，传递耗时
                                    await on_tool_call(tool_name, tool_call["args"], tool_duration)
                            except (TypeError, ValueError):
                                # 如果不支持，忽略（不影响主流程）
                                pass
                        
                        messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"]))
                
                # 使用流式调用 LLM（工具调用循环），支持 429 错误自动切换模型
                def get_stream_with_tools_loop():
                    return self.llm_with_tools.astream(messages)
                
                stream_iterable = self._stream_with_retry(
                    get_stream_with_tools_loop,
                    "工具调用循环流式",
                    on_sse_event=on_sse_event
                )
                response = await self._stream_llm_response(
                    stream_iterable,
                    on_sse_event=on_sse_event
                )
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
        
        # 计算模型调用耗时
        duration = time.time() - start_time
        self.last_duration = duration
        
        # 发送模型响应完成事件
        if on_sse_event:
            agent_type = self._get_agent_type()
            try:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("model_response", {
                        "agent_type": agent_type,
                        "agent_class": self.__class__.__name__,
                        "model_name": self.model_name,
                        "duration": duration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens
                    })
                else:
                    on_sse_event("model_response", {
                        "agent_type": agent_type,
                        "agent_class": self.__class__.__name__,
                        "model_name": self.model_name,
                        "duration": duration,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens
                    })
            except Exception as e:
                logger.warning(f"发送模型响应事件失败: {e}")
        
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
