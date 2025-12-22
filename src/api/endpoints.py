import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from src.models import ChatRequest, GenerateRequest
from src.agent.factory import orchestrator, session_manager, workers, router, inference_worker, aggregator

api_router = APIRouter()

@api_router.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id or "default_session"
    user_input = request.message
    
    logging.info(f"收到请求: session_id={session_id}, message={user_input}")
    session_data = session_manager.get_session(session_id)
    
    try:
        plan = await orchestrator.plan_and_route(user_input, session_data)
        intents = plan["intents"]
        await orchestrator.execute_workers(intents, user_input, session_data)
        await orchestrator.infer_and_verify(session_data)
        response_text = await orchestrator.summarize_response(session_data, intents)
        session_manager.save_session(session_id, session_data)
        
        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
            "pending_questions": session_data.get("pending_questions", []),
            "debug": {
                "intents": intents,
                "duration": f"{orchestrator.calculate_total_duration(intents):.2f}s"
            }
        }
    except Exception as e:
        logging.error(f"处理请求失败: {e}")
        return {"status": "error", "message": str(e)}

@api_router.get("/chat/stream")
async def chat_stream(message: str, session_id: str = "default_session"):
    async def event_generator():
        logging.info(f"=== 开始流式处理请求: session_id={session_id} ===")
        session_data = session_manager.get_session(session_id)
        event_queue = asyncio.Queue()
        
        async def tool_callback(intent, tool_name, tool_args):
            await event_queue.put({
                "type": "status",
                "content": f"[{intent}] 正在调用工具: {tool_name}",
                "debug": {"agent": intent, "model": "Tool", "duration": "N/A"}
            })

        try:
            yield {"data": json.dumps({"type": "status", "content": "正在分析您的意图..."})}
            plan = await orchestrator.plan_and_route(message, session_data)
            intents = plan["intents"]
            route_result = plan["route_result"]
            
            if session_data.get("pending_questions"):
                yield {"data": json.dumps({
                    "type": "status",
                    "content": "发现待补充信息，请确认/补充",
                    "pending_questions": session_data.get("pending_questions", [])
                })}
            
            yield {"data": json.dumps({
                "type": "status", 
                "content": f"识别到意图: {', '.join(intents)}",
                "debug": {
                    "agent": "Router",
                    "model": router.last_model,
                    "duration": f"{router.last_duration:.2f}s"
                }
            })}
            yield {"data": json.dumps({"type": "partial", "content": route_result})}
            
            yield {"data": json.dumps({"type": "status", "content": f"正在由 {', '.join(intents)} 专家并发处理..."})}
            workers_task = asyncio.create_task(orchestrator.execute_workers(intents, message, session_data, on_tool_call=tool_callback))
            
            while not workers_task.done():
                while not event_queue.empty():
                    msg = await event_queue.get()
                    yield {"data": json.dumps(msg)}
                await asyncio.sleep(0.1)
            
            while not event_queue.empty():
                msg = await event_queue.get()
                yield {"data": json.dumps(msg)}
            
            results = await workers_task
            
            for i, updated_section in enumerate(results):
                intent = [it for it in intents if it in workers][i]
                worker = workers[intent]
                yield {"data": json.dumps({
                    "type": "status",
                    "content": f"{intent} 专家处理完成",
                    "debug": {
                        "agent": worker.__class__.__name__,
                        "model": worker.last_model,
                        "duration": f"{worker.last_duration:.2f}s"
                    }
                })}
                yield {"data": json.dumps({
                    "type": "partial", 
                    "content": updated_section,
                    "debug": {"agent": worker.__class__.__name__}
                })}
            
            yield {"data": json.dumps({"type": "status", "content": "正在进行常识校验与职业推理..."})}
            await orchestrator.infer_and_verify(session_data)
            yield {"data": json.dumps({
                "type": "status",
                "content": "常识校验完成",
                "debug": {
                    "agent": "InferenceWorker",
                    "model": inference_worker.last_model,
                    "duration": f"{inference_worker.last_duration:.2f}s"
                }
            })}

            yield {"data": json.dumps({"type": "status", "content": "正在生成回复..."})}
            response_text = await orchestrator.summarize_response(session_data, intents)
            session_manager.save_session(session_id, session_data)
            
            yield {"data": json.dumps({
                "type": "final", 
                "content": response_text,
                "pending_questions": session_data.get("pending_questions", []),
                "debug": {
                    "agent": "Aggregator",
                    "model": aggregator.last_model,
                    "duration": f"{aggregator.last_duration:.2f}s"
                }
            })}
        except Exception as e:
            logging.error(f"流式处理失败: {e}")
            yield {"data": json.dumps({"type": "error", "content": str(e)})}

    return EventSourceResponse(event_generator())

@api_router.post("/resume/generate")
async def generate_full_resume(request: GenerateRequest):
    session_id = request.session_id or "default_session"
    session_data = session_manager.get_session(session_id)

    try:
        data = await orchestrator.generate_final_resume(session_id, session_data)
        return {
            "status": "success" if data["validation"].get("passed", False) else "warning",
            "result": data["result"],
            "validation": data["validation"],
            "session_id": session_id
        }
    except Exception as e:
        logging.error(f"生成整简历失败: {e}")
        return {"status": "error", "message": str(e)}
