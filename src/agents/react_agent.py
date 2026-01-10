"""
ReAct Agent - 实现 Think-Act-Observe 循环
"""
import time
import logging
import json
import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from src.agents.base import BaseAgent
from src.config.models import ModelConfig

logger = logging.getLogger("resume-agent.react_agent")


class ReActAgent(BaseAgent):
    """ReAct 模式的 Agent"""
    
    def __init__(
        self,
        models: List[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 8192,
        timeout: Optional[float] = 60.0,
        max_iterations: int = 5,
        tools: List = None
    ):
        """
        初始化 ReAct Agent
        
        Args:
            models: 模型列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间
            max_iterations: 最大迭代次数（默认 5）
            tools: 工具列表
        """
        # 如果没有提供模型，使用配置
        if models is None:
            config = ModelConfig.get_model_config("react_agent")
            models = config.get("models", ["meta-llama/llama-3.3-70b-instruct:free"])
            temperature = config.get("temperature", temperature)
            max_tokens = config.get("max_tokens", max_tokens)
            timeout = config.get("timeout", timeout)
        
        super().__init__(
            models=models,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tools=tools or []
        )
        self.max_iterations = max_iterations
    
    def _get_agent_type(self) -> str:
        """返回 agent 类型"""
        return "react_agent"
    
    async def _send_step_event(
        self,
        on_sse_event: Optional[Callable],
        iteration: int,
        step: str,
        description: str,
        model: str = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration: float = 0.0,
        content: str = None,
        tool_calls: List[Dict[str, Any]] = None
    ):
        """发送循环步骤事件"""
        if on_sse_event:
            try:
                event_data = {
                    "iteration": iteration,
                    "step": step,  # "think", "act", "observe"
                    "description": description,
                    "model": model or self.model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "duration": duration,
                }
                if content:
                    # 限制内容长度
                    if step in ["think", "act", "observe"]:
                        event_data["content"] = content[:50] + "..." if len(content) > 50 else content
                    else:
                        event_data["content"] = content[:200] + "..." if len(content) > 200 else content
                if tool_calls:
                    # 确保 tool_calls 中的 tool_output 可以被 JSON 序列化
                    serializable_tool_calls = []
                    for tool_call in tool_calls:
                        serializable_call = {
                            "tool_name": tool_call.get("tool_name"),
                            "tool_args": tool_call.get("tool_args"),
                            "duration": tool_call.get("duration"),
                            "tool_output": tool_call.get("tool_output")
                        }
                        serializable_tool_calls.append(serializable_call)
                    event_data["tool_calls"] = serializable_tool_calls
                
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("react_step", event_data)
                else:
                    on_sse_event("react_step", event_data)
            except Exception as e:
                logger.warning(f"发送 react_step 事件失败: {e}")
    
    async def _send_log_event(
        self,
        on_sse_event: Optional[Callable],
        iteration: int,
        step: str,
        log_type: str,
        message: str,
        data: Dict[str, Any]
    ):
        """发送 react_log 事件"""
        if on_sse_event:
            try:
                event_data = {
                    "iteration": iteration,
                    "step": step,
                    "log_type": log_type,
                    "message": message,
                    "data": data
                }
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("react_log", event_data)
                else:
                    on_sse_event("react_log", event_data)
            except Exception as e:
                logger.warning(f"发送 react_log 事件失败: {e}")
    
    def _parse_json_from_output(self, output: str) -> Optional[Dict[str, Any]]:
        """从模型输出中解析 JSON
        
        支持以下格式：
        1. JSON 代码块：```json ... ```
        2. 直接 JSON 对象：{...}
        """
        if not output:
            return None
        
        # 尝试提取 JSON 代码块
        json_block_pattern = r'```json\s*(.*?)\s*```'
        match = re.search(json_block_pattern, output, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
        else:
            # 尝试直接查找 JSON 对象
            json_start = output.find('{')
            json_end = output.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = output[json_start:json_end]
            else:
                json_str = output.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}, 原始输出: {json_str[:200]}")
            # 尝试容错处理：提取关键字段
            try:
                # 使用正则表达式提取关键字段
                result = {}
                for field in ["reasoning", "needs_tool", "tool_name", "is_complete", "observation", "has_enough_info", "needs_more"]:
                    pattern = f'"{field}"\\s*:\\s*"([^"]*)"'
                    match = re.search(pattern, json_str)
                    if match:
                        result[field] = match.group(1)
                    else:
                        # 尝试布尔值
                        bool_pattern = f'"{field}"\\s*:\\s*(true|false)'
                        match = re.search(bool_pattern, json_str, re.IGNORECASE)
                        if match:
                            result[field] = match.group(1).lower() == "true"
                
                # 提取 tool_params
                tool_params_pattern = r'"tool_params"\s*:\s*(\{[^}]*\})'
                match = re.search(tool_params_pattern, json_str, re.DOTALL)
                if match:
                    try:
                        result["tool_params"] = json.loads(match.group(1))
                    except:
                        pass
                
                if result:
                    logger.info(f"容错解析成功，提取到字段: {list(result.keys())}")
                    return result
            except Exception as e2:
                logger.warning(f"容错解析也失败: {e2}")
        
        return None
    
    async def _think_stage(
        self,
        iteration: int,
        user_question: str,
        accumulated_context: List[str],
        observe_json: Optional[Dict[str, Any]],
        system_prompt: str,
        session_id: Optional[str],
        on_sse_event: Optional[Callable],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """Think 阶段：分析问题，输出 JSON"""
        think_start = time.time()
        
        # 发送 Think 开始事件
        await self._send_step_event(
            on_sse_event, iteration, "think", 
            f"第 {iteration} 次迭代 - 思考阶段",
            model=self.model_name
        )
        
        # 构建 Think 提示词
        context_parts = [f"用户问题: {user_question}"]
        
        # 添加之前的思考过程（最近 2 轮）
        if accumulated_context:
            recent_context = accumulated_context[-2:] if len(accumulated_context) >= 2 else accumulated_context
            context_parts.append("\n之前的思考过程（最近 2 轮）:")
            for ctx in recent_context:
                context_parts.append(f"- {ctx}")
        
        # 添加观察结果（如果有）
        if observe_json:
            context_parts.append(f"\n上一轮观察结果: {observe_json.get('observation', '')}")
        
        context = "\n".join(context_parts)
        
        think_prompt = f"""{context}

请按照以下 JSON 格式输出你的思考：

{{
  "reasoning": "思考内容（1-2句话，简洁明了）",
  "needs_tool": true,
  "tool_name": "web_search",
  "tool_params": {{
    "query": "搜索查询内容",
    "max_results": 5
  }},
  "is_complete": false,
  "next_action": "需要搜索相关信息"
}}

**重要：**
1. 必须输出有效的 JSON 格式
2. reasoning 要简洁（1-2句话）
3. 如果 needs_tool 为 false，tool_name 必须为 null
4. 如果 needs_tool 为 true，tool_name 不能为 null
5. is_complete 为 true 时表示答案完整，可以停止循环
"""
        
        # 包装 on_sse_event，为 partial 事件添加步骤标识
        async def think_sse_wrapper(event_type: str, data: dict):
            if event_type == "partial" and on_sse_event:
                data["react_iteration"] = iteration
                data["react_step"] = "think"
            if on_sse_event:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event(event_type, data)
                else:
                    on_sse_event(event_type, data)
        
        # 调用模型
        think_response = await self.run_chain(
            system_prompt=system_prompt,
            user_input=think_prompt,
            json_mode=False,
            session_id=session_id,
            on_sse_event=think_sse_wrapper,
            conversation_history=conversation_history
        )
        
        think_duration = time.time() - think_start
        think_content = str(think_response).strip()
        
        # 解析 JSON
        think_json = self._parse_json_from_output(think_content)
        
        # 如果解析失败，使用默认值
        if not think_json:
            logger.warning(f"Think 阶段 JSON 解析失败，使用默认值")
            think_json = {
                "reasoning": think_content[:100] if think_content else "思考中...",
                "needs_tool": False,
                "tool_name": None,
                "tool_params": {},
                "is_complete": False,
                "next_action": "继续处理"
            }
        
        # 发送 Think log 事件
        await self._send_log_event(
            on_sse_event,
            iteration,
            "think",
            "think",
            f"思考：{think_json.get('reasoning', '')}",
            think_json
        )
        
        # 判断是否应该停止
        should_stop = think_json.get("is_complete", False)
        
        # 如果 observe_json 中 has_enough_info 为 true 且 is_complete 为 true，则停止
        if observe_json and observe_json.get("has_enough_info", False) and think_json.get("is_complete", False):
            should_stop = True
        
        # 发送 Think 完成事件
        think_display = think_json.get("reasoning", "")[:50]
        await self._send_step_event(
            on_sse_event, iteration, "think",
            f"第 {iteration} 次迭代 - 思考完成",
            model=self.model_name,
            input_tokens=0,  # 将从 model_response 事件中获取
            output_tokens=0,
            duration=think_duration,
            content=think_display
        )
        
        logger.info(f"[ReAct] Think 阶段完成: reasoning={think_json.get('reasoning', '')[:50]}, needs_tool={think_json.get('needs_tool')}, is_complete={should_stop}")
        
        return {
            "think_json": think_json,
            "content": think_content,
            "tokens": {"input": 0, "output": 0},
            "duration": think_duration,
            "should_stop": should_stop
        }
    
    async def _act_stage(
        self,
        think_json: Dict[str, Any],
        iteration: int,
        user_question: str,
        system_prompt: str,
        session_id: Optional[str],
        on_sse_event: Optional[Callable],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """Act 阶段：根据 Think JSON 调用工具"""
        act_start = time.time()
        
        # 发送 Act 开始事件
        await self._send_step_event(
            on_sse_event, iteration, "act",
            f"第 {iteration} 次迭代 - 执行阶段",
            model=self.model_name
        )
        
        needs_tool = think_json.get("needs_tool", False)
        tool_name = think_json.get("tool_name")
        tool_params = think_json.get("tool_params", {})
        
        tool_results = []
        tool_calls_info = []
        
        if needs_tool and tool_name and self.tools:
            # 发送工具调用前 log
            await self._send_log_event(
                on_sse_event,
                iteration,
                "act",
                "tool_call",
                f"调用工具：{tool_name}",
                {
                    "tool_name": tool_name,
                    "tool_params": tool_params
                }
            )
            
            # 调用工具
            tool_start_time = time.time()
            tool_result = None
            tool_error = None
            success = False
            
            try:
                # 查找工具函数
                tool_func = None
                for tool in self.tools:
                    # 检查 LangChain tool 对象
                    if hasattr(tool, 'name') and tool.name == tool_name:
                        tool_func = tool
                        break
                    # 检查函数名
                    elif callable(tool) and hasattr(tool, '__name__') and tool.__name__ == tool_name:
                        tool_func = tool
                        break
                    # 检查是否有 func 属性（LangChain tool 包装的函数）
                    elif hasattr(tool, 'func') and hasattr(tool.func, '__name__') and tool.func.__name__ == tool_name:
                        tool_func = tool.func
                        break
                
                if tool_func:
                    # 调用工具
                    # 对于 LangChain tool，使用 invoke 或 ainvoke
                    if hasattr(tool_func, 'invoke') or hasattr(tool_func, 'ainvoke'):
                        if asyncio.iscoroutinefunction(tool_func.ainvoke):
                            tool_result = await tool_func.ainvoke(tool_params)
                        elif hasattr(tool_func, 'ainvoke'):
                            tool_result = await tool_func.ainvoke(tool_params)
                        else:
                            tool_result = tool_func.invoke(tool_params)
                    elif asyncio.iscoroutinefunction(tool_func):
                        tool_result = await tool_func(**tool_params)
                    else:
                        tool_result = tool_func(**tool_params)
                    success = True
                    tool_results.append(tool_result)
                    logger.info(f"[ReAct] 工具 {tool_name} 调用成功，参数: {tool_params}")
                else:
                    tool_error = f"未找到工具: {tool_name}，可用工具: {[getattr(t, 'name', getattr(t, '__name__', '未知')) for t in self.tools]}"
                    logger.warning(f"[ReAct] {tool_error}")
            except Exception as e:
                tool_error = str(e)
                logger.error(f"[ReAct] 工具 {tool_name} 调用失败: {e}")
            
            tool_duration = time.time() - tool_start_time
            
            # 发送工具调用后 log
            await self._send_log_event(
                on_sse_event,
                iteration,
                "act",
                "tool_result",
                f"工具返回结果：{tool_name}",
                {
                    "tool_name": tool_name,
                    "tool_params": tool_params,
                    "result": {
                        "success": success,
                        "data": tool_result if success else None,
                        "duration": tool_duration
                    },
                    "error": tool_error
                }
            )
            
            # 记录工具调用信息
            tool_calls_info.append({
                "tool_name": tool_name,
                "tool_args": tool_params,
                "duration": tool_duration,
                "tool_output": tool_result if success else None
            })
            
            act_content = f"调用工具 {tool_name}，参数: {tool_params}"
        else:
            # 不需要工具
            await self._send_log_event(
                on_sse_event,
                iteration,
                "act",
                "act",
                "执行：不需要工具调用",
                {
                    "needs_tool": False
                }
            )
            act_content = "不需要工具调用"
        
        act_duration = time.time() - act_start
        
        # 发送 Act 完成事件
        await self._send_step_event(
            on_sse_event, iteration, "act",
            f"第 {iteration} 次迭代 - 执行完成",
            model=self.model_name,
            input_tokens=0,
            output_tokens=0,
            duration=act_duration,
            content=act_content[:200],
            tool_calls=tool_calls_info if tool_calls_info else None
        )
        
        logger.info(f"[ReAct] Act 阶段完成: needs_tool={needs_tool}, tool_name={tool_name}, tool_calls={len(tool_calls_info)}")
        
        return {
            "tool_results": tool_results,
            "tool_calls": tool_calls_info,
            "content": act_content,
            "tokens": {"input": 0, "output": 0},
            "duration": act_duration
        }
    
    async def _observe_stage(
        self,
        think_json: Dict[str, Any],
        tool_results: List[Any],
        iteration: int,
        user_question: str,
        system_prompt: str,
        session_id: Optional[str],
        on_sse_event: Optional[Callable],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """Observe 阶段：分析工具返回结果，输出 JSON"""
        observe_start = time.time()
        
        # 发送 Observe 开始事件
        await self._send_step_event(
            on_sse_event, iteration, "observe",
            f"第 {iteration} 次迭代 - 观察阶段",
            model=self.model_name
        )
        
        # 构建工具调用结果文本
        tool_results_text = ""
        if tool_results:
            tool_results_text = "\n\n工具调用结果:\n"
            for idx, result in enumerate(tool_results):
                if isinstance(result, (list, dict)):
                    result_str = json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    result_str = str(result)
                tool_results_text += f"- 结果 {idx + 1}: {result_str}\n"
        
        # 构建 Observe 提示词
        observe_prompt = f"""用户问题: {user_question}

思考结果: {think_json.get('reasoning', '')}
执行结果: {think_json.get('next_action', '')}{tool_results_text}

请按照以下 JSON 格式输出你的观察：

{{
  "observation": "观察到的结果分析",
  "has_enough_info": true,
  "needs_more": false
}}

**重要：**
1. 必须输出有效的 JSON 格式
2. observation 要分析工具返回的信息
3. has_enough_info 表示是否已有足够信息
4. needs_more 表示是否需要更多信息
"""
        
        # 包装 on_sse_event，为 partial 事件添加步骤标识
        async def observe_sse_wrapper(event_type: str, data: dict):
            if event_type == "partial" and on_sse_event:
                data["react_iteration"] = iteration
                data["react_step"] = "observe"
            if on_sse_event:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event(event_type, data)
                else:
                    on_sse_event(event_type, data)
        
        # 调用模型
        observe_response = await self.run_chain(
            system_prompt=system_prompt,
            user_input=observe_prompt,
            json_mode=False,
            session_id=session_id,
            on_sse_event=observe_sse_wrapper,
            conversation_history=conversation_history
        )
        
        observe_duration = time.time() - observe_start
        observe_content = str(observe_response).strip()
        
        # 解析 JSON
        observe_json = self._parse_json_from_output(observe_content)
        
        # 如果解析失败，使用默认值
        if not observe_json:
            logger.warning(f"Observe 阶段 JSON 解析失败，使用默认值")
            observe_json = {
                "observation": observe_content[:100] if observe_content else "观察中...",
                "has_enough_info": False,
                "needs_more": True
            }
        
        # 发送 Observe log 事件
        await self._send_log_event(
            on_sse_event,
            iteration,
            "observe",
            "observe",
            f"观察：{observe_json.get('observation', '')}",
            observe_json
        )
        
        # 发送 Observe 完成事件
        observe_display = observe_json.get("observation", "")[:50]
        await self._send_step_event(
            on_sse_event, iteration, "observe",
            f"第 {iteration} 次迭代 - 观察完成",
            model=self.model_name,
            input_tokens=0,
            output_tokens=0,
            duration=observe_duration,
            content=observe_display
        )
        
        logger.info(f"[ReAct] Observe 阶段完成: observation={observe_json.get('observation', '')[:50]}, has_enough_info={observe_json.get('has_enough_info')}")
        
        return {
            "observe_json": observe_json,
            "content": observe_content,
            "has_enough_info": observe_json.get("has_enough_info", False),
            "tokens": {"input": 0, "output": 0},
            "duration": observe_duration
        }
    
    def _build_final_answer_prompt(
        self,
        user_question: str,
        all_iterations: List[Dict[str, Any]]
    ) -> str:
        """构建最终答案提示词，包含所有迭代的完整上下文"""
        prompt_parts = [f"用户问题: {user_question}\n"]
        prompt_parts.append("\n=== 所有迭代的完整过程 ===\n")
        
        for idx, iter_info in enumerate(all_iterations, 1):
            prompt_parts.append(f"\n--- 第 {idx} 轮迭代 ---\n")
            
            # Think 结果
            think = iter_info.get("think", {})
            prompt_parts.append(f"思考: {think.get('reasoning', '')}\n")
            
            # 工具调用结果
            tool_calls = iter_info.get("tool_calls", [])
            tool_results = iter_info.get("tool_results", [])
            if tool_calls:
                prompt_parts.append("工具调用:\n")
                for tool_idx, tool_call in enumerate(tool_calls):
                    tool_name = tool_call.get("tool_name", "未知")
                    tool_args = tool_call.get("tool_args", {})
                    prompt_parts.append(f"- {tool_name}({json.dumps(tool_args, ensure_ascii=False)})\n")
                    # 获取对应的工具结果
                    if tool_idx < len(tool_results) and tool_results[tool_idx] is not None:
                        result = tool_results[tool_idx]
                        if isinstance(result, (list, dict)):
                            result_str = json.dumps(result, ensure_ascii=False, indent=2)
                        else:
                            result_str = str(result)
                        # 限制结果长度，避免提示词过长
                        if len(result_str) > 1000:
                            result_str = result_str[:1000] + "...（结果已截断）"
                        prompt_parts.append(f"  结果: {result_str}\n")
            
            # Observe 结果
            observe = iter_info.get("observe", {})
            prompt_parts.append(f"观察: {observe.get('observation', '')}\n")
        
        prompt_parts.append("\n=== 请生成最终答案 ===\n")
        prompt_parts.append("""请基于以上所有迭代的完整过程，生成最终答案。

**重要要求：**
1. 必须输出纯文本答案，不要输出 JSON 格式
2. 完整回答用户的问题
3. 如果使用了网络搜索（web_search），必须列出参考来源（包括标题和URL）
4. 答案要简洁明了，重点突出
5. 直接输出答案内容，不要包含"【最终答案】"、"最终答案："等标记
6. 不要输出任何 JSON 格式的内容

最终答案：""")
        
        return "".join(prompt_parts)
    
    async def run_react_loop(
        self,
        user_question: str,
        session_id: Optional[str] = None,
        on_sse_event: Optional[Callable] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        执行 ReAct 循环
        
        Args:
            user_question: 用户问题
            session_id: 会话 ID
            on_sse_event: SSE 事件回调
            conversation_history: 对话历史
        
        Returns:
            Dict: 包含最终答案和统计信息
        """
        logger.info(f"开始 ReAct 循环，问题: {user_question[:100]}...")
        
        # 加载提示词
        system_prompt = self.load_prompt("react_agent")
        if not system_prompt:
            system_prompt = "你是一个使用 ReAct 模式的 AI 助手。通过思考->执行->观察的循环来回答问题。"
        
        # 初始化循环状态
        iteration = 0
        accumulated_context = []
        total_duration = 0.0
        all_steps = []
        observe_json = None
        all_iterations = []  # 存储每轮迭代的完整信息
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"--- ReAct 循环第 {iteration} 次迭代 ---")
            
            # Think 阶段
            think_result = await self._think_stage(
                iteration=iteration,
                user_question=user_question,
                accumulated_context=accumulated_context,
                observe_json=observe_json,
                system_prompt=system_prompt,
                session_id=session_id,
                on_sse_event=on_sse_event,
                conversation_history=conversation_history
            )
            
            think_json = think_result["think_json"]
            should_stop = think_result["should_stop"]
            
            # 更新上下文
            accumulated_context.append(f"思考: {think_json.get('reasoning', '')}")
            
            # Act 阶段
            act_result = await self._act_stage(
                think_json=think_json,
                iteration=iteration,
                user_question=user_question,
                system_prompt=system_prompt,
                session_id=session_id,
                on_sse_event=on_sse_event,
                conversation_history=conversation_history
            )
            
            tool_results = act_result["tool_results"]
            tool_calls_info = act_result["tool_calls"]
            
            # 更新上下文
            if tool_calls_info:
                accumulated_context.append(f"执行: 调用工具 {tool_calls_info[0].get('tool_name', '未知')}")
            else:
                accumulated_context.append("执行: 不需要工具")
            
            # Observe 阶段
            observe_result = await self._observe_stage(
                think_json=think_json,
                tool_results=tool_results,
                iteration=iteration,
                user_question=user_question,
                system_prompt=system_prompt,
                session_id=session_id,
                on_sse_event=on_sse_event,
                conversation_history=conversation_history
            )
            
            observe_json = observe_result["observe_json"]
            has_enough_info = observe_result["has_enough_info"]
            
            # 更新上下文
            accumulated_context.append(f"观察: {observe_json.get('observation', '')}")
            
            # 收集当前迭代的完整信息
            iteration_info = {
                "think": think_json,
                "tool_calls": tool_calls_info,
                "tool_results": tool_results,
                "observe": observe_json
            }
            all_iterations.append(iteration_info)
            
            # 检查停止条件：只有当 is_complete 为 true 时才停止
            if think_json.get("is_complete", False):
                logger.info(f"第 {iteration} 次迭代后决定停止循环（is_complete=True）")
                break
            
            # 记录步骤
            all_steps.append({
                "iteration": iteration,
                "step": "think",
                "content": think_result["content"],
                "model": self.model_name,
                "tokens": think_result["tokens"],
                "duration": think_result["duration"]
            })
            all_steps.append({
                "iteration": iteration,
                "step": "act",
                "content": act_result["content"],
                "model": self.model_name,
                "tokens": act_result["tokens"],
                "duration": act_result["duration"]
            })
            all_steps.append({
                "iteration": iteration,
                "step": "observe",
                "content": observe_result["content"],
                "model": self.model_name,
                "tokens": observe_result["tokens"],
                "duration": observe_result["duration"]
            })
            
            total_duration += think_result["duration"] + act_result["duration"] + observe_result["duration"]
        
        # 生成最终答案：使用包含完整上下文的提示词
        final_prompt = self._build_final_answer_prompt(
            user_question=user_question,
            all_iterations=all_iterations
        )
        
        final_start = time.time()
        
        # 包装 on_sse_event，为 partial 事件添加步骤标识
        async def final_sse_wrapper(event_type: str, data: dict):
            if event_type == "partial" and on_sse_event:
                data["react_iteration"] = iteration
                data["react_step"] = "final"
            if on_sse_event:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event(event_type, data)
                else:
                    on_sse_event(event_type, data)
        
        final_response = await self.run_chain(
            system_prompt=system_prompt,
            user_input=final_prompt,
            json_mode=False,
            session_id=session_id,
            on_sse_event=final_sse_wrapper,
            conversation_history=conversation_history
        )
        
        final_duration = time.time() - final_start
        final_answer = str(final_response).strip()
        
        # 确保最终答案不为空
        if not final_answer or final_answer.strip() == "":
            logger.warning("最终答案为空，使用默认提示")
            final_answer = "抱歉，未能生成完整的答案。请重试或提供更多信息。"
        
        # 发送最终答案的 partial 事件
        if on_sse_event:
            try:
                if asyncio.iscoroutinefunction(on_sse_event):
                    await on_sse_event("partial", {
                        "content": final_answer,
                        "accumulated": final_answer,
                        "react_iteration": iteration,
                        "react_step": "final"
                    })
                else:
                    on_sse_event("partial", {
                        "content": final_answer,
                        "accumulated": final_answer,
                        "react_iteration": iteration,
                        "react_step": "final"
                    })
            except Exception as e:
                logger.warning(f"发送最终答案 partial 事件失败: {e}")
        
        total_duration += final_duration
        
        logger.info(f"ReAct 循环完成，共 {iteration}/{self.max_iterations} 次迭代，总耗时: {total_duration:.2f}s")
        logger.info(f"最终答案长度: {len(final_answer)} 字符")
        
        return {
            "answer": final_answer,
            "iterations": iteration,
            "max_iterations": self.max_iterations,
            "total_tokens": {
                "input": 0,  # 将从 model_response 事件中获取
                "output": 0,
                "total": 0
            },
            "total_duration": total_duration,
            "model": self.model_name,
            "steps": all_steps
        }
