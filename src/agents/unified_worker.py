"""
统一 Worker 实现
通过配置驱动实现不同 Worker 的功能
"""
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from src.agents.base import BaseAgent, time_it
from src.utils.field_checker import check_missing_fields

logger = logging.getLogger("resume-agent.unified_worker")


class UnifiedWorker(BaseAgent):
    """统一 Worker 基类"""
    
    def __init__(
        self,
        worker_type: str,  # "info", "experience", "skill"
        models: List[str],
        prompt_name: str,
        field_definitions: Dict[str, Any],
        tools: List = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        initial_model_index: Optional[int] = None
    ):
        """
        初始化 UnifiedWorker
        
        Args:
            worker_type: Worker 类型
            models: 模型列表
            prompt_name: Prompt 文件名（不含 .md）
            field_definitions: 字段定义配置
            tools: 工具列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间
            initial_model_index: 初始模型索引
        """
        super().__init__(
            models=models,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            tools=tools or [],
            initial_model_index=initial_model_index
        )
        self.worker_type = worker_type
        self.prompt_name = prompt_name
        self.field_definitions = field_definitions
    
    @time_it
    async def process(
        self, 
        user_input: str, 
        current_data: Dict[str, Any], 
        on_tool_call=None, 
        session_id: str = None, 
        on_sse_event: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        处理用户输入，提取数据并检查缺失字段
        
        Args:
            user_input: 用户输入
            current_data: 当前简历数据
            on_tool_call: 工具调用回调
            session_id: 会话ID
            on_sse_event: SSE事件回调函数
        
        Returns:
            {
                "extracted_data": {...},  # Worker 提取的数据
                "missing_fields": ["phone", "email"]  # 缺失字段列表（简单数组）
            }
        """
        # 加载 prompt
        system_prompt = self.load_prompt(self.prompt_name)
        
        # 构建 user_prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        if self.worker_type == "skill":
            # SkillWorker 不需要日期
            user_prompt = f"用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        else:
            user_prompt = f"当前日期: {current_date}\n用户输入: {user_input}\n当前数据: {json.dumps(current_data, ensure_ascii=False)}"
        
        # 调用 LLM 提取数据
        extracted_data = await self.run_chain(
            system_prompt, 
            user_prompt, 
            on_tool_call=on_tool_call, 
            session_id=session_id, 
            on_sse_event=on_sse_event
        )
        
        # 后处理钩子（用于特殊逻辑，如 InfoWorker 的日期预测）
        extracted_data = await self.post_process(extracted_data, current_data)
        
        # 合并提取的数据到当前数据（用于检查缺失字段）
        from src.utils.helpers import deep_merge
        import copy
        merged_data = copy.deepcopy(current_data)
        if isinstance(extracted_data, dict):
            # 使用 deep_merge 进行深度合并（原地修改）
            deep_merge(merged_data, extracted_data)
        
        # 检查缺失字段
        missing_fields = check_missing_fields(merged_data, self.field_definitions)
        
        logger.info(
            f"UnifiedWorker [{self.worker_type}] 提取完成，"
            f"缺失字段: {missing_fields}"
        )
        
        return {
            "extracted_data": extracted_data,
            "missing_fields": missing_fields
        }
    
    async def post_process(
        self, 
        extracted_data: Dict[str, Any], 
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        后处理钩子，子类可以重写以实现特殊逻辑
        
        Args:
            extracted_data: 提取的数据
            current_data: 当前数据
        
        Returns:
            处理后的数据
        """
        return extracted_data

