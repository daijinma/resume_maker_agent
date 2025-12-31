"""
统一的 API 路由 - 所有接口统一为 SSE 流式输出
"""
import json
import asyncio
import logging
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.schema import StreamRequest, AgentType
from src.service.planner_worker_service import PlannerWorkerService
from src.service.dual_track_service import DualTrackService
from src.service.session_service import SessionService
from src.service.token_statistics_service import TokenStatisticsService
from src.config.settings import Settings
from datetime import datetime

logger = logging.getLogger("api.routes")

# 创建路由器
api_router = APIRouter()

# #region agent log helper
def _write_debug_log(data: dict):
    """安全地写入调试日志"""
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
        # 同时记录到标准logger（INFO级别，方便查看）
        logger.info(f"[DEBUG] {log_data['location']}: {log_data['message']} - {json.dumps(log_data['data'], ensure_ascii=False)}")
    except Exception as e:
        logger.debug(f"Debug log write failed: {e}")
# #endregion

# 全局服务实例（懒加载）
_session_service = None
_planner_worker_service = None
_dual_track_service = None
_token_statistics_service = None


def get_session_service() -> SessionService:
    """获取会话服务实例（懒加载）"""
    global _session_service
    if _session_service is None:
        _session_service = SessionService(use_database=Settings.USE_DATABASE)
    return _session_service


def get_planner_worker_service() -> PlannerWorkerService:
    """获取 Planner-Worker 服务实例（懒加载）"""
    global _planner_worker_service
    if _planner_worker_service is None:
        session_service = get_session_service()
        _planner_worker_service = PlannerWorkerService(session_service)
    return _planner_worker_service


def get_dual_track_service() -> DualTrackService:
    """获取 Dual-Track 服务实例（懒加载）"""
    global _dual_track_service
    if _dual_track_service is None:
        session_service = get_session_service()
        if not session_service.use_database:
            raise ValueError("Dual-Track 服务需要数据库支持，请设置 USE_DATABASE=true")
        _dual_track_service = DualTrackService(session_service)
        # 初始化数据库连接
        asyncio.create_task(session_service.initialize())
    return _dual_track_service


def get_token_statistics_service() -> TokenStatisticsService:
    """获取 Token 统计服务实例（懒加载）"""
    global _token_statistics_service
    if _token_statistics_service is None:
        _token_statistics_service = TokenStatisticsService()
    return _token_statistics_service


def _yield_event(event_type: str, data: dict):
    """生成 SSE 事件"""
    return {"data": json.dumps({"type": event_type, **data})}


@api_router.post("/stream")
async def stream(request: StreamRequest):
    """
    统一的流式接口，支持所有操作类型
    
    支持的 action:
    - chat: 聊天对话
    - generate: 生成完整简历
    - history: 获取对话历史
    - reasoning_status: 获取背景推理状态（仅 Dual-Track）
    - token_stats: 获取 token 统计
    - token_summary: 获取 token 摘要
    """
    async def event_generator():
        try:
            session_id = request.session_id or "default_session"
            action = request.action
            
            logger.info(f"收到流式请求: action={action}, session_id={session_id}, agent_type={request.agent_type}")
            
            # 发送开始事件
            yield _yield_event("status", {"content": f"开始处理 {action} 操作..."})
            
            if action == "chat":
                # 聊天对话
                if not request.message:
                    yield _yield_event("error", {"content": "chat 操作需要提供 message 参数"})
                    return
                
                selected_agent = request.agent_type or AgentType.PLANNER_WORKER
                
                # #region agent log
                _write_debug_log({
                    "hypothesisId": "E",
                    "location": "routes.py:107",
                    "message": "API chat entry",
                    "data": {
                        "session_id": session_id,
                        "message": request.message[:50] if request.message else "",
                        "agent_type": str(selected_agent)
                    }
                })
                # #endregion
                
                try:
                    if selected_agent == AgentType.DUAL_TRACK:
                        service = get_dual_track_service()
                    else:
                        service = get_planner_worker_service()
                    
                    # 使用队列收集工具调用事件
                    tool_events_queue = asyncio.Queue()
                    
                    # 工具调用回调 - 支持两种调用方式
                    async def tool_callback(*args):
                        """工具调用回调，支持两种调用方式：
                        1. tool_callback(intent, tool_name, tool_args) - 三个参数
                        2. tool_callback(tool_name, tool_args) - 两个参数
                        """
                        if len(args) == 3:
                            # 三个参数的情况：intent, tool_name, tool_args
                            intent, tool_name, tool_args = args
                            await tool_events_queue.put({
                                "type": "status",
                                "content": f"[{intent}] 正在调用工具: {tool_name}",
                                "debug": {"agent": intent, "model": "Tool", "duration": "N/A"}
                            })
                        elif len(args) == 2:
                            # 两个参数的情况：tool_name, tool_args
                            tool_name, tool_args = args
                            await tool_events_queue.put({
                                "type": "status",
                                "content": f"正在调用工具: {tool_name}",
                                "debug": {"model": "Tool", "duration": "N/A"}
                            })
                        else:
                            # 其他情况，记录但不处理
                            logger.warning(f"工具调用回调收到意外的参数数量: {len(args)}")
                    
                    yield _yield_event("status", {"content": "🔍 正在分析您的意图..."})
                    
                    # 启动处理任务
                    process_task = asyncio.create_task(
                        service.process_message(
                            session_id, request.message, on_tool_call=tool_callback
                        )
                    )
                    
                    # 处理工具调用事件（在后台任务运行期间）
                    while not process_task.done():
                        try:
                            # 非阻塞检查队列
                            event = await asyncio.wait_for(tool_events_queue.get(), timeout=0.1)
                            yield _yield_event(event["type"], {
                                "content": event["content"],
                                "debug": event.get("debug", {})
                            })
                        except asyncio.TimeoutError:
                            # 队列为空，继续等待
                            await asyncio.sleep(0.05)
                            continue
                    
                    # 处理剩余的工具调用事件
                    while not tool_events_queue.empty():
                        try:
                            event = tool_events_queue.get_nowait()
                            yield _yield_event(event["type"], {
                                "content": event["content"],
                                "debug": event.get("debug", {})
                            })
                        except asyncio.QueueEmpty:
                            break
                    
                    # 获取处理结果
                    result = await process_task
                    
                    # #region agent log
                    _write_debug_log({
                        "hypothesisId": "E",
                        "location": "routes.py:186",
                        "message": "Process task completed",
                        "data": {
                            "has_result": result is not None,
                            "has_response": "response" in result if result else False
                        }
                    })
                    # #endregion
                    
                    # 输出最终结果
                    yield _yield_event("final", {
                        "content": result["response"],
                        "session_id": session_id,
                        "agent_type": result.get("agent_type", selected_agent.value),
                        "pending_questions": result.get("pending_questions", []),
                        "debug": result.get("debug", {})
                    })
                    
                except Exception as e:
                    # #region agent log
                    import traceback
                    _write_debug_log({
                        "hypothesisId": "E",
                        "location": "routes.py:203",
                        "message": "Exception caught in chat handler",
                        "data": {
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "traceback": traceback.format_exc()[:500]
                        }
                    })
                    # #endregion
                    logger.error(f"聊天处理失败: {e}", exc_info=True)
                    yield _yield_event("error", {"content": str(e)})
            
            elif action == "generate":
                # 生成完整简历
                try:
                    service = get_planner_worker_service()
                    yield _yield_event("status", {"content": "📝 正在生成完整简历..."})
                    
                    data = await service.generate_final_resume(session_id)
                    
                    yield _yield_event("final", {
                        "status": "success" if data["validation"].get("passed", False) else "warning",
                        "result": data["result"],
                        "validation": data["validation"],
                        "session_id": session_id
                    })
                    
                except Exception as e:
                    logger.error(f"生成简历失败: {e}", exc_info=True)
                    yield _yield_event("error", {"content": str(e)})
            
            elif action == "history":
                # 获取对话历史
                try:
                    session_service = get_session_service()
                    limit = request.limit or 50
                    
                    yield _yield_event("status", {"content": f"📚 正在获取对话历史（最多 {limit} 条）..."})
                    
                    history = await session_service.get_history(session_id, limit=limit)
                    
                    yield _yield_event("final", {
                        "session_id": session_id,
                        "history": history,
                        "count": len(history)
                    })
                    
                except Exception as e:
                    logger.error(f"获取对话历史失败: {e}", exc_info=True)
                    yield _yield_event("error", {"content": str(e)})
            
            elif action == "reasoning_status":
                # 获取背景推理状态（仅 Dual-Track）
                try:
                    service = get_dual_track_service()
                    yield _yield_event("status", {"content": "🧠 正在获取背景推理状态..."})
                    
                    result = await service.get_reasoning_status(session_id)
                    
                    yield _yield_event("final", result)
                    
                except Exception as e:
                    logger.error(f"获取推理状态失败: {e}", exc_info=True)
                    yield _yield_event("error", {"content": str(e)})
            
            elif action == "token_stats":
                # 获取 token 统计
                try:
                    service = get_token_statistics_service()
                    yield _yield_event("status", {"content": "📊 正在获取 token 统计..."})
                    
                    # 解析时间参数
                    start_dt = None
                    end_dt = None
                    if request.start_date:
                        try:
                            start_dt = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                        except:
                            yield _yield_event("error", {"content": f"无效的开始时间格式: {request.start_date}"})
                            return
                    if request.end_date:
                        try:
                            end_dt = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                        except:
                            yield _yield_event("error", {"content": f"无效的结束时间格式: {request.end_date}"})
                            return
                    
                    # 根据参数选择查询方式
                    if request.group_by in ["day", "week", "month"]:
                        result = await service.get_time_statistics(
                            time_range=request.group_by,
                            start_date=start_dt,
                            end_date=end_dt
                        )
                    elif request.token_agent_type:
                        result = await service.get_agent_statistics(
                            agent_type=request.token_agent_type,
                            start_date=start_dt,
                            end_date=end_dt
                        )
                    elif request.token_model:
                        result = await service.get_model_statistics(
                            model_name=request.token_model,
                            start_date=start_dt,
                            end_date=end_dt
                        )
                    elif request.group_by == "agent_type":
                        result = await service.get_agent_statistics(
                            start_date=start_dt,
                            end_date=end_dt
                        )
                    elif request.group_by == "model_name":
                        result = await service.get_model_statistics(
                            start_date=start_dt,
                            end_date=end_dt
                        )
                    else:
                        # 默认返回综合统计
                        result = await service.get_all_statistics(
                            start_date=start_dt,
                            end_date=end_dt
                        )
                    
                    yield _yield_event("final", result)
                    
                except Exception as e:
                    logger.error(f"获取 token 统计失败: {e}", exc_info=True)
                    yield _yield_event("error", {"content": str(e)})
            
            elif action == "token_summary":
                # 获取 token 摘要
                try:
                    service = get_token_statistics_service()
                    yield _yield_event("status", {"content": "📈 正在获取 token 摘要..."})
                    
                    # 解析时间参数
                    start_dt = None
                    end_dt = None
                    if request.start_date:
                        try:
                            start_dt = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                        except:
                            yield _yield_event("error", {"content": f"无效的开始时间格式: {request.start_date}"})
                            return
                    if request.end_date:
                        try:
                            end_dt = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                        except:
                            yield _yield_event("error", {"content": f"无效的结束时间格式: {request.end_date}"})
                            return
                    
                    result = await service.get_all_statistics(
                        start_date=start_dt,
                        end_date=end_dt
                    )
                    
                    yield _yield_event("final", result)
                    
                except Exception as e:
                    logger.error(f"获取 token 摘要失败: {e}", exc_info=True)
                    yield _yield_event("error", {"content": str(e)})
            
            else:
                yield _yield_event("error", {"content": f"不支持的操作类型: {action}"})
                
        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            yield _yield_event("error", {"content": str(e)})
    
    return EventSourceResponse(event_generator())


# 保留旧接口以向后兼容（已废弃，建议使用 /stream）
@api_router.post("/chat")
async def chat_deprecated(request: dict):
    """已废弃：请使用 POST /stream 接口，action=chat"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=chat",
        "example": {
            "action": "chat",
            "message": request.get("message", ""),
            "session_id": request.get("session_id", "default"),
            "agent_type": request.get("agent_type", "planner_worker")
        }
    }


@api_router.get("/chat/stream")
async def chat_stream_deprecated():
    """已废弃：请使用 POST /stream 接口，action=chat"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=chat"
    }


@api_router.post("/resume/generate")
async def generate_deprecated(request: dict):
    """已废弃：请使用 POST /stream 接口，action=generate"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=generate",
        "example": {
            "action": "generate",
            "session_id": request.get("session_id", "default")
        }
    }


@api_router.get("/reasoning-status/{session_id}")
async def reasoning_status_deprecated(session_id: str):
    """已废弃：请使用 POST /stream 接口，action=reasoning_status"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=reasoning_status",
        "example": {
            "action": "reasoning_status",
            "session_id": session_id
        }
    }


@api_router.get("/history/{session_id}")
async def history_deprecated(session_id: str):
    """已废弃：请使用 POST /stream 接口，action=history"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=history",
        "example": {
            "action": "history",
            "session_id": session_id,
            "limit": 50
        }
    }


@api_router.get("/token/session/{session_id}")
async def token_session_deprecated(session_id: str):
    """已废弃：请使用 POST /stream 接口，action=token_stats"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=token_stats",
        "example": {
            "action": "token_stats",
            "session_id": session_id
        }
    }


@api_router.get("/token/statistics")
async def token_statistics_deprecated():
    """已废弃：请使用 POST /stream 接口，action=token_stats"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=token_stats"
    }


@api_router.get("/token/summary")
async def token_summary_deprecated():
    """已废弃：请使用 POST /stream 接口，action=token_summary"""
    return {
        "status": "deprecated",
        "message": "此接口已废弃，请使用 POST /stream 接口，设置 action=token_summary"
    }
