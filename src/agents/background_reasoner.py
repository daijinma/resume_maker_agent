"""
背景推理服务 (BackgroundReasoner)

在背景异步执行深度推理，分析数据完整性并生成问题。
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
from src.agents.base import BaseAgent, time_it
from src.config.models import ModelConfig
from src.agents.question_queue import QuestionQueue

logger = logging.getLogger("dual-track.background_reasoner")


class BackgroundReasoner(BaseAgent):
    """背景推理服务"""
    
    def __init__(self, model: Optional[Union[str, List[str]]] = None):
        """
        初始化背景推理服务
        
        Args:
            model: 使用的模型（字符串或列表，默认使用推理模型配置）
        """
        if model is None:
            config = ModelConfig.get_model_config("inference")
            models = config["models"]
            temperature = config.get("temperature", 0.3)
            max_tokens = config.get("max_tokens")
            timeout = config.get("timeout")
            initial_model_index = config.get("initial_model_index")
        else:
            # 如果指定了模型，使用指定的模型，其他参数使用默认配置
            models = model if isinstance(model, list) else [model]
            config = ModelConfig.get_model_config("inference")
            temperature = config.get("temperature", 0.3)
            max_tokens = config.get("max_tokens")
            timeout = config.get("timeout")
            initial_model_index = config.get("initial_model_index")
        
        super().__init__(
            models=models,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            initial_model_index=initial_model_index
        )
    
    @time_it
    async def analyze_and_generate_questions(
        self, 
        resume_data: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """
        分析简历数据并生成问题
        
        Args:
            resume_data: 简历数据
            session_id: 会话 ID
        
        Returns:
            Dict: 包含 insights 和 questions 的结果
        """
        system_prompt = self.load_prompt("inference_worker")
        if not system_prompt:
            # 如果加载失败，使用默认提示词
            system_prompt = """你是一个专业的简历分析助手。请分析简历数据的完整性和逻辑性，识别缺失的关键信息，并生成需要追问的问题。

分析要点：
1. 基本信息是否完整（姓名、联系方式、教育背景）
2. 工作经历是否详细（时间、职位、职责、成果）
3. 技能和证书是否齐全
4. 数据逻辑是否合理（时间顺序、职位晋升等）

问题生成规则：
- 优先级 1-3：基本信息（name, phone, email）
- 优先级 4-6：教育背景（school, major, degree）
- 优先级 7-10：工作经历
- 优先级 11+：技能和证书

返回 JSON 格式，包含 insights（分析结果列表）、summary（总结）和 questions（问题列表）。"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        user_prompt = f"""當前日期: {current_date}
当前简历数据: {json.dumps(resume_data, ensure_ascii=False)}

请分析：
1. 数据完整性和逻辑性
2. 缺失的关键信息
3. 需要追问的问题

返回格式：
{{
    "insights": ["分析結果1", "分析結果2"],
    "summary": "總結",
    "questions": [
        {{
            "id": "q_001",
            "content": "問題內容",
            "field": "字段名",
            "reason": "提問原因",
            "priority": 1
        }}
    ]
}}
"""
        
        try:
            result = await self.run_chain(system_prompt, user_prompt, json_mode=True, session_id=session_id)
            
            # 確保返回格式正確
            if not isinstance(result, dict):
                result = {"insights": [], "summary": "分析失败", "questions": []}
            
            # 验证问题格式
            questions = result.get("questions", [])
            validated_questions = []
            for q in questions:
                if isinstance(q, dict) and "id" in q and "content" in q:
                    validated_questions.append(q)
            
            result["questions"] = validated_questions
            logger.info(f"生成了 {len(validated_questions)} 个问题")
            
            return result
            
        except Exception as e:
            logger.error(f"背景推理失败: {e}")
            return {
                "insights": [],
                "summary": f"分析失败: {str(e)}",
                "questions": []
            }
    


class AsyncBackgroundReasoner:
    """异步背景推理协调器"""
    
    def __init__(self, reasoner: BackgroundReasoner, session_service):
        """
        初始化异步背景推理协调器
        
        Args:
            reasoner: BackgroundReasoner 实例
            session_service: 会话服务
        """
        self.reasoner = reasoner
        self.session_service = session_service
        self.running_tasks: Dict[str, asyncio.Task] = {}
    
    async def trigger_reasoning(
        self,
        session_id: str,
        resume_data: Dict[str, Any],
        delay: float = 0.5
    ) -> None:
        """
        异步触发背景推理
        
        Args:
            session_id: 会话 ID
            resume_data: 简历数据
            delay: 延迟时间（秒），避免阻塞主流程
        """
        # 如果已有任务在运行，取消它
        if session_id in self.running_tasks:
            task = self.running_tasks[session_id]
            if not task.done():
                task.cancel()
                logger.info(f"已取消会话 {session_id} 的旧推理任务")
        
        async def _run_reasoning():
            try:
                # 延遲執行
                if delay > 0:
                    await asyncio.sleep(delay)
                
                # 更新状态为进行中
                session_data = await self.session_service.get_session(session_id)
                session_data["background_reasoning_status"] = "running"
                await self.session_service.save_session(session_id, session_data)
                
                # 执行推理
                result = await self.reasoner.analyze_and_generate_questions(
                    resume_data, session_id
                )
                
                # 更新问题队列
                question_queue_data = session_data.get("question_queue", {})
                question_queue = QuestionQueue.from_dict(session_id, question_queue_data)
                
                # 添加新问题
                for q in result.get("questions", []):
                    question_queue.add_question(
                        question_id=q.get("id", f"q_{len(question_queue.questions)}"),
                        content=q.get("content", ""),
                        field=q.get("field"),
                        reason=q.get("reason"),
                        priority=q.get("priority")
                    )
                
                # 去重
                question_queue.deduplicate()
                
                # 保存问题队列
                await self.session_service.save_question_queue(
                    session_id, question_queue.to_dict()
                )
                
                # 保存推理结果
                session_data = await self.session_service.get_session(session_id)
                session_data["background_reasoning_status"] = "completed"
                session_data["last_reasoning_time"] = datetime.now().isoformat()
                session_data["inference_insights"] = result.get("insights", [])
                session_data["question_queue"] = question_queue.to_dict()
                await self.session_service.save_session(session_id, session_data)
                
                logger.info(f"会话 {session_id} 的背景推理完成，生成了 {len(result.get('questions', []))} 个问题")
                
            except asyncio.CancelledError:
                logger.info(f"会话 {session_id} 的背景推理已取消")
            except Exception as e:
                logger.error(f"会话 {session_id} 的背景推理失败: {e}")
                # 更新状态为错误
                try:
                    session_data = await self.session_service.get_session(session_id)
                    session_data["background_reasoning_status"] = "error"
                    await self.session_service.save_session(session_id, session_data)
                except:
                    pass
            finally:
                # 清理任务
                if session_id in self.running_tasks:
                    del self.running_tasks[session_id]
        
        # 创建并运行任务
        task = asyncio.create_task(_run_reasoning())
        self.running_tasks[session_id] = task

