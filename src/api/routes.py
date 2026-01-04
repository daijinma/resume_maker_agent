"""
统一的 API 路由 - 所有接口统一为 SSE 流式输出
"""
import json
import asyncio
import logging
import time
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.schema import StreamRequest, AgentType
from src.service.planner_worker_service import PlannerWorkerService
from src.service.dual_track_service import DualTrackService
from src.service.simple_chat_service import SimpleChatService
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
_simple_chat_service = None
_token_statistics_service = None


def get_session_service() -> SessionService:
    """获取会话服务实例（懒加载）"""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
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
        _dual_track_service = DualTrackService(session_service)
        # 初始化数据库连接
        asyncio.create_task(session_service.initialize())
    return _dual_track_service


def get_simple_chat_service() -> SimpleChatService:
    """获取 Simple Chat 服务实例（懒加载）"""
    global _simple_chat_service
    if _simple_chat_service is None:
        session_service = get_session_service()
        _simple_chat_service = SimpleChatService(session_service)
    return _simple_chat_service


def get_token_statistics_service() -> TokenStatisticsService:
    """获取 Token 统计服务实例（懒加载）"""
    global _token_statistics_service
    if _token_statistics_service is None:
        _token_statistics_service = TokenStatisticsService()
    return _token_statistics_service


def _yield_event(event_type: str, data: dict):
    """生成 SSE 事件"""
    event_data = {"type": event_type, **data}
    sse_data = json.dumps(event_data, ensure_ascii=False)
    content_preview = str(data.get('content', ''))[:100] if data.get('content') else ''
    accumulated_preview = str(data.get('accumulated', ''))[:100] if data.get('accumulated') else ''
    logger.info(f"[SSE] 📤 生成事件: type={event_type}, data_length={len(sse_data)}")
    logger.info(f"[SSE]   内容预览: content={content_preview}, accumulated={accumulated_preview}")
    logger.info(f"[SSE]   完整数据: {sse_data[:500]}...")  # 只记录前500字符
    return {"data": sse_data}


@api_router.get("/stream")
async def stream_get(
    action: str,
    session_id: str = "default",
    agent_type: str = None,
    message: str = None,
    limit: int = None,
    token_agent_type: str = None,
    token_model: str = None,
    start_date: str = None,
    end_date: str = None,
    group_by: str = None
):
    """
    GET 方式的流式接口（用于 EventSource API）
    支持所有操作类型，参数通过查询字符串传递
    """
    # 构建 StreamRequest 对象
    from src.schema.request import StreamRequest, AgentType
    
    try:
        agent_type_enum = AgentType(agent_type) if agent_type else AgentType.PLANNER_WORKER
    except:
        agent_type_enum = AgentType.PLANNER_WORKER
    
    request = StreamRequest(
        action=action,
        session_id=session_id,
        agent_type=agent_type_enum,
        message=message,
        limit=limit,
        token_agent_type=token_agent_type,
        token_model=token_model,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by
    )
    
    logger.info(f"[SSE] GET 请求: action={action}, session_id={session_id}, agent_type={agent_type}")
    return await stream(request)


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
            logger.info(f"[SSE] 🚀 开始处理流式请求: action={action}, session_id={session_id}")
            yield _yield_event("status", {"content": f"开始处理 {action} 操作..."})
            logger.info(f"[SSE] ✅ 开始事件已发送")
            
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
                    elif selected_agent == AgentType.SIMPLE_CHAT:
                        service = get_simple_chat_service()
                    else:
                        service = get_planner_worker_service()
                    
                    # 使用队列收集工具调用事件和SSE事件
                    tool_events_queue = asyncio.Queue()
                    sse_events_queue = asyncio.Queue()
                    
                    # 工具调用回调 - 支持多种调用方式
                    # 存储工具调用耗时（key: (intent, tool_name) 或 tool_name, value: duration）
                    tool_durations = {}
                    
                    async def tool_callback(*args):
                        """工具调用回调，支持多种调用方式：
                        1. tool_callback(intent, tool_name, tool_args) - 三个参数（调用前）
                        2. tool_callback(tool_name, tool_args) - 两个参数（调用前）
                        3. tool_callback(tool_name, tool_args, duration) - 三个参数（调用后，带耗时）
                        4. tool_callback(intent, tool_name, tool_args, duration) - 四个参数（调用后，带耗时）
                        """
                        if len(args) == 4:
                            # 四个参数的情况：intent, tool_name, tool_args, duration（调用后，带耗时）
                            intent, tool_name, tool_args, duration = args
                            tool_durations[(intent, tool_name)] = duration
                            await tool_events_queue.put({
                                "type": "status",
                                "content": f"[{intent}] 正在调用工具: {tool_name}",
                                "debug": {"agent": intent, "model": "Tool", "duration": f"{duration:.2f}s"}
                            })
                        elif len(args) == 3:
                            # 三个参数的情况：可能是 intent, tool_name, tool_args（调用前）或 tool_name, tool_args, duration（调用后）
                            # 判断第三个参数是否为数字（duration）
                            if isinstance(args[2], (int, float)):
                                # tool_name, tool_args, duration（调用后，带耗时）
                                tool_name, tool_args, duration = args
                                tool_durations[tool_name] = duration
                                await tool_events_queue.put({
                                    "type": "status",
                                    "content": f"正在调用工具: {tool_name}",
                                    "debug": {"model": "Tool", "duration": f"{duration:.2f}s"}
                                })
                            else:
                                # intent, tool_name, tool_args（调用前）
                                intent, tool_name, tool_args = args
                                # 检查是否有已存储的耗时
                                duration = tool_durations.get((intent, tool_name), "N/A")
                                if duration != "N/A":
                                    duration = f"{duration:.2f}s"
                                await tool_events_queue.put({
                                    "type": "status",
                                    "content": f"[{intent}] 正在调用工具: {tool_name}",
                                    "debug": {"agent": intent, "model": "Tool", "duration": duration}
                                })
                        elif len(args) == 2:
                            # 两个参数的情况：tool_name, tool_args（调用前）
                            tool_name, tool_args = args
                            # 检查是否有已存储的耗时
                            duration = tool_durations.get(tool_name, "N/A")
                            if duration != "N/A":
                                duration = f"{duration:.2f}s"
                            await tool_events_queue.put({
                                "type": "status",
                                "content": f"正在调用工具: {tool_name}",
                                "debug": {"model": "Tool", "duration": duration}
                            })
                        else:
                            # 其他情况，记录但不处理
                            logger.warning(f"工具调用回调收到意外的参数数量: {len(args)}")
                    
                    # SSE事件回调
                    async def sse_event_callback(event_type: str, data: dict):
                        """SSE事件回调
                        Args:
                            event_type: 事件类型 ("model_request", "model_switch", "model_response", "partial")
                            data: 事件数据字典
                        """
                        import time
                        queue_put_start = time.time()
                        
                        # #region agent log
                        _write_debug_log({
                            "hypothesisId": "C",
                            "location": "routes.py:209",
                            "message": "sse_event_callback called",
                            "data": {
                                "event_type": event_type,
                                "content_len": len(str(data.get("content", "")))
                            }
                        })
                        # #endregion
                        
                        # partial 事件直接传递，不进行格式化
                        if event_type == "partial":
                            partial_content = data.get("content", "")
                            partial_accumulated = data.get("accumulated", "")
                            logger.info(f"[SSE] 📝 Partial 事件: content_len={len(partial_content)}, accumulated_len={len(partial_accumulated) if partial_accumulated else 0}")
                            logger.info(f"[SSE]   内容预览: content={partial_content[:50]}, accumulated={partial_accumulated[:50] if partial_accumulated else ''}")
                            
                            await sse_events_queue.put({
                                "type": "partial",
                                "content": partial_content,
                                "accumulated": partial_accumulated,
                                "debug": data
                            })
                            
                            # #region agent log
                            queue_put_duration = time.time() - queue_put_start
                            _write_debug_log({
                                "hypothesisId": "C",
                                "location": "routes.py:220",
                                "message": "Event put into sse_events_queue",
                                "data": {
                                    "queue_put_duration_ms": queue_put_duration * 1000,
                                    "queue_size": sse_events_queue.qsize()
                                }
                            })
                            # #endregion
                            logger.info(f"[SSE] ✅ Partial 事件已放入队列，队列大小: {sse_events_queue.qsize()}")
                            return
                        
                        # 格式化事件内容
                        agent_name = data.get("agent_class", data.get("agent_type", "Unknown"))
                        model_name = data.get("model_name", "Unknown")
                        
                        if event_type == "model_request":
                            content = f"🤖 [{agent_name}] 正在使用模型 {model_name} 处理请求..."
                        elif event_type == "model_switch":
                            old_model = data.get("old_model", "Unknown")
                            new_model = data.get("new_model", "Unknown")
                            reason = data.get("reason", "unknown")
                            content = f"🔄 [{agent_name}] 模型切换: {old_model} → {new_model} (原因: {reason})"
                        elif event_type == "model_response":
                            duration = data.get("duration", 0.0)
                            input_tokens = data.get("input_tokens", 0)
                            output_tokens = data.get("output_tokens", 0)
                            content = f"✅ [{agent_name}] 处理完成 (耗时: {duration:.2f}s, tokens: {input_tokens}/{output_tokens})"
                        else:
                            content = f"[{agent_name}] {event_type}"
                        
                        await sse_events_queue.put({
                            "type": "status",
                            "content": content,
                            "debug": {
                                "event": event_type,
                                **data
                            }
                        })
                    
                    logger.info(f"[SSE] 🔍 发送分析意图状态")
                    yield _yield_event("status", {"content": "🔍 正在分析您的意图..."})
                    logger.info(f"[SSE] ✅ 分析意图状态已发送")
                    
                    # 启动处理任务
                    process_task = asyncio.create_task(
                        service.process_message(
                            session_id, request.message, on_tool_call=tool_callback, on_sse_event=sse_event_callback
                        )
                    )
                    
                    # 处理工具调用事件和SSE事件（在后台任务运行期间）
                    import time
                    loop_start_time = time.time()
                    events_yielded = 0
                    
                    # #region agent log
                    _write_debug_log({
                        "hypothesisId": "D",
                        "location": "routes.py:290",
                        "message": "Event processing loop started",
                        "data": {
                            "loop_start_time": loop_start_time,
                            "process_task_done": process_task.done()
                        }
                    })
                    # #endregion
                    
                    # 持续处理队列中的事件，直到process_task完成
                    # 使用连续处理模式，尽可能快地处理所有队列中的事件
                    while not process_task.done():
                        try:
                            processed_any = False
                            
                            # 批量处理SSE事件队列中的所有事件
                            while True:
                                try:
                                    event = sse_events_queue.get_nowait()
                                    processed_any = True
                                    
                                    # #region agent log
                                    _write_debug_log({
                                        "hypothesisId": "D",
                                        "location": "routes.py:267",
                                        "message": "Event retrieved from queue, before yield",
                                        "data": {
                                            "event_type": event.get("type"),
                                            "queue_get_duration_ms": 0,
                                            "time_since_loop_start": time.time() - loop_start_time,
                                            "events_yielded_so_far": events_yielded,
                                            "queue_size_after_get": sse_events_queue.qsize()
                                        }
                                    })
                                    # #endregion
                                    
                                    yield_start = time.time()
                                    logger.info(f"[SSE] 准备 yield SSE 事件: type={event['type']}, content_length={len(event.get('content', ''))}")
                                    sse_event = _yield_event(event["type"], {
                                        "content": event["content"],
                                        "debug": event.get("debug", {})
                                    })
                                    yield sse_event
                                    yield_duration = time.time() - yield_start
                                    events_yielded += 1
                                    logger.info(f"[SSE] ✅ SSE 事件已 yield: type={event['type']}, yield_duration={yield_duration*1000:.2f}ms, total_events={events_yielded}")
                                    
                                    # #region agent log
                                    _write_debug_log({
                                        "hypothesisId": "D",
                                        "location": "routes.py:275",
                                        "message": "Event yielded to SSE stream",
                                        "data": {
                                            "yield_duration_ms": yield_duration * 1000,
                                            "total_events_yielded": events_yielded
                                        }
                                    })
                                    # #endregion
                                except asyncio.QueueEmpty:
                                    break
                            
                            # 批量处理工具调用事件队列中的所有事件
                            while True:
                                try:
                                    event = tool_events_queue.get_nowait()
                                    processed_any = True
                                    logger.info(f"[SSE] 处理工具调用事件: type={event['type']}, content={event.get('content', '')[:50]}")
                                    sse_event = _yield_event(event["type"], {
                                        "content": event["content"],
                                        "debug": event.get("debug", {})
                                    })
                                    yield sse_event
                                    logger.info(f"[SSE] ✅ 工具调用事件已 yield: type={event['type']}")
                                except asyncio.QueueEmpty:
                                    break
                            
                            # 如果处理了任何事件，立即继续循环，不等待
                            if processed_any:
                                continue
                            
                            # 如果两个队列都为空，短暂让出控制权
                            # 使用 asyncio.sleep(0) 让出控制权，立即检查下一个事件
                            await asyncio.sleep(0)  # 立即让出控制权，不等待
                                
                        except Exception as e:
                            logger.warning(f"处理事件队列时出错: {e}")
                            await asyncio.sleep(0.001)  # 1ms，避免CPU空转
                            continue
                    
                    # 处理剩余的工具调用事件
                    remaining_tool_events = 0
                    while not tool_events_queue.empty():
                        try:
                            event = tool_events_queue.get_nowait()
                            remaining_tool_events += 1
                            logger.info(f"[SSE] 处理剩余工具调用事件 #{remaining_tool_events}: type={event['type']}")
                            sse_event = _yield_event(event["type"], {
                                "content": event["content"],
                                "debug": event.get("debug", {})
                            })
                            yield sse_event
                        except asyncio.QueueEmpty:
                            break
                    if remaining_tool_events > 0:
                        logger.info(f"[SSE] ✅ 已处理 {remaining_tool_events} 个剩余工具调用事件")
                    
                    # 处理剩余的SSE事件
                    remaining_sse_events = 0
                    while not sse_events_queue.empty():
                        try:
                            event = sse_events_queue.get_nowait()
                            remaining_sse_events += 1
                            logger.info(f"[SSE] 处理剩余SSE事件 #{remaining_sse_events}: type={event['type']}")
                            sse_event = _yield_event(event["type"], {
                                "content": event["content"],
                                "debug": event.get("debug", {})
                            })
                            yield sse_event
                        except asyncio.QueueEmpty:
                            break
                    if remaining_sse_events > 0:
                        logger.info(f"[SSE] ✅ 已处理 {remaining_sse_events} 个剩余SSE事件")
                    
                    # 获取处理结果
                    try:
                        result = await process_task
                    except Exception as task_error:
                        logger.error(f"处理任务失败: {task_error}", exc_info=True)
                        yield _yield_event("error", {"content": f"处理失败: {str(task_error)}"})
                        return
                    
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
                    if result and "response" in result:
                        final_content = result["response"]
                        logger.info(f"[SSE] 准备发送 final 事件，内容长度: {len(final_content) if final_content else 0}")
                        sse_event = _yield_event("final", {
                            "content": final_content,
                            "session_id": session_id,
                            "agent_type": result.get("agent_type", selected_agent.value),
                            "pending_questions": result.get("pending_questions", []),
                            "resume_data": result.get("resume_data", {}),  # 添加 resume_data
                            "debug": result.get("debug", {})
                        })
                        yield sse_event
                        logger.info(f"[SSE] ✅ final 事件已发送")
                    else:
                        logger.warning(f"处理结果格式不正确: {result}")
                        sse_event = _yield_event("error", {"content": "处理结果格式不正确"})
                        yield sse_event
                    
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
                    
                    # 如果提供了session_id且没有其他过滤参数，返回该会话的统计
                    has_filter_params = any([
                        request.group_by,
                        request.token_agent_type,
                        request.token_model,
                        request.start_date,
                        request.end_date
                    ])
                    
                    if session_id and not has_filter_params:
                        # 获取单个会话的统计
                        result = await service.get_session_statistics(session_id)
                        # 同时获取会话的 agent_type
                        session_service = get_session_service()
                        session_data = await session_service.get_session(session_id)
                        if session_data and session_data.get("agent_type"):
                            result["agent_type"] = session_data["agent_type"]
                        yield _yield_event("final", result)
                    else:
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
            
            elif action == "list_sessions":
                # 获取所有会话列表
                try:
                    session_service = get_session_service()
                    limit = request.limit or 100
                    
                    yield _yield_event("status", {"content": f"📋 正在获取会话列表（最多 {limit} 个）..."})
                    
                    sessions_list = await session_service.list_sessions(limit=limit)
                    
                    yield _yield_event("final", {
                        "sessions": sessions_list,
                        "count": len(sessions_list)
                    })
                    
                except Exception as e:
                    logger.error(f"获取会话列表失败: {e}", exc_info=True)
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
            try:
                yield _yield_event("error", {"content": str(e)})
            except Exception as yield_error:
                logger.error(f"发送错误事件失败: {yield_error}", exc_info=True)
        finally:
            # 确保生成器正常完成
            pass
    
    # 添加响应头禁用缓冲，确保实时流式传输
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        "Connection": "keep-alive",
    }
    response = EventSourceResponse(event_generator())
    # 设置响应头
    for key, value in headers.items():
        response.headers[key] = value
    return response


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


# ========== 正常的 REST API 端点（非 SSE）==========

@api_router.get("/sessions")
async def get_sessions(limit: int = 100):
    """获取所有会话列表"""
    try:
        session_service = get_session_service()
        sessions_list = await session_service.list_sessions(limit=limit)
        return {
            "sessions": sessions_list,
            "count": len(sessions_list)
        }
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 100):
    """获取会话历史记录"""
    try:
        session_service = get_session_service()
        history = await session_service.get_history(session_id, limit=limit)
        return {
            "session_id": session_id,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sessions/{session_id}/token-stats")
async def get_session_token_stats(session_id: str):
    """获取会话的 token 统计"""
    try:
        service = get_token_statistics_service()
        result = await service.get_session_statistics(session_id)
        
        # 同时获取会话的 agent_type
        session_service = get_session_service()
        session_data = await session_service.get_session(session_id)
        if session_data and session_data.get("agent_type"):
            result["agent_type"] = session_data["agent_type"]
        
        return result
    except Exception as e:
        logger.error(f"获取 token 统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sessions/{session_id}/pending-questions")
async def get_session_pending_questions(session_id: str):
    """获取会话的待办事项"""
    try:
        service = get_dual_track_service()
        result = await service.get_reasoning_status(session_id)
        return {
            "session_id": session_id,
            "pending_questions": result.get("pending_questions", []),
            "background_reasoning_status": result.get("background_reasoning_status", "pending")
        }
    except Exception as e:
        # 如果 dual_track 服务不支持，返回空列表
        logger.debug(f"获取待办事项失败（可能不支持）: {e}")
        return {
            "session_id": session_id,
            "pending_questions": [],
            "background_reasoning_status": "unknown"
        }


@api_router.put("/sessions/{session_id}/name")
async def update_session_name(session_id: str, name: str = Query(None)):
    """更新会话名称"""
    try:
        session_service = get_session_service()
        # 如果 name 为空字符串，设置为 None
        session_name = name if name and name.strip() else None
        await session_service.update_session_name(session_id, session_name)
        return {
            "session_id": session_id,
            "session_name": session_name,
            "success": True
        }
    except Exception as e:
        logger.error(f"更新会话名称失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
