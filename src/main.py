import logging
import json
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sse_starlette.sse import EventSourceResponse

from src.agent.session import SessionManager
from src.agent.router import Router
from src.agent.workers import InfoWorker, ExperienceWorker, SkillWorker
from src.agent.inference import InferenceWorker
from src.agent.aggregator import Aggregator
import uvicorn

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("resume-api")

app = FastAPI(title="Chat-to-Resume Multi-Agent API")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

# 初始化 Agents
session_manager = SessionManager()
router = Router()
workers = {
    "info": InfoWorker(),
    "experience": ExperienceWorker(),
    "skill": SkillWorker()
}
inference_worker = InferenceWorker()
aggregator = Aggregator()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    reply: str
    status: str
    data: Optional[Dict[str, Any]] = None

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id or "default_session"
    user_input = request.message
    
    logger.info(f"收到请求: session_id={session_id}, message={user_input}")
    
    # 1. 加载会话
    session_data = session_manager.get_session(session_id)
    
    try:
        # 2. 路由决策
        route_result = await router.route(user_input, session_data)
        intents = route_result.get("intents", [])
        if not intents: intents = ["chat"]
        
        print(f"\n[Intent Analysis] Intents: {intents}")
        print(f"[Intent Analysis] Reason: {route_result.get('reason')}")
        logger.info(f"路由结果: {intents} - {route_result.get('reason')}")
        
        # 3. 并发分发给 Worker
        worker_tasks = []
        active_workers = []
        for intent in intents:
            if intent in workers:
                worker_tasks.append(workers[intent].process(user_input, session_data["resume_data"]))
                active_workers.append(workers[intent])
        
        if worker_tasks:
            # POST 接口不需要实时工具回调，传 None 即可
            results = await asyncio.gather(*[workers[intent].process(user_input, session_data["resume_data"]) for intent in intents if intent in workers])
            for updated_section in results:
                session_data["resume_data"].update(updated_section)
        
        # 4. 常识校验与推理
        inference_result = await inference_worker.analyze(session_data["resume_data"])
        session_data["inference_insights"] = inference_result.get("insights", [])

        # 5. 汇总回复
        response_text = await aggregator.aggregate(session_data, ", ".join(intents))
        
        # 6. 保存会话
        session_manager.save_session(session_id, session_data)
        
        # 统计总耗时
        total_duration = router.last_duration + aggregator.last_duration + inference_worker.last_duration
        for w in active_workers:
            total_duration += w.last_duration
            
        return {
            "status": "success",
            "response": response_text,
            "session_id": session_id,
            "debug": {
                "intents": intents,
                "duration": f"{total_duration:.2f}s"
            }
        }
        
    except Exception as e:
        logger.error(f"处理请求失败: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/chat/stream")
async def chat_stream(message: str, session_id: str = "default_session"):
    async def event_generator():
        logger.info(f"=== 开始流式处理请求: session_id={session_id} ===")
        session_data = session_manager.get_session(session_id)
        event_queue = asyncio.Queue()
        
        async def tool_callback(intent, tool_name, tool_args):
            await event_queue.put({
                "type": "status",
                "content": f"[{intent}] 正在调用工具: {tool_name}",
                "debug": {"agent": intent, "model": "Tool", "duration": "N/A"}
            })

        try:
            # 2. 路由决策
            logger.info("步骤 1: 路由决策")
            yield {"data": json.dumps({"type": "status", "content": "正在分析您的意图..."})}
            route_result = await router.route(message, session_data)
            
            # 兼容旧版 intent 字段
            intents = route_result.get("intents", [])
            if not intents and "intent" in route_result:
                intents = [route_result["intent"]]
            if not intents: intents = ["chat"]
            
            print(f"\n[Intent Analysis] Intents: {intents}")
            print(f"[Intent Analysis] Reason: {route_result.get('reason')}")
            
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
            
            # 3. 并发分发给 Worker
            worker_tasks = []
            active_intents = []
            
            for intent in intents:
                if intent in workers:
                    active_intents.append(intent)
                    
                    async def wrapped_worker(intent_name):
                        # 创建一个闭包来捕获 intent_name
                        async def on_tool(name, args):
                            await tool_callback(intent_name, name, args)
                        
                        result = await workers[intent_name].process(
                            message, 
                            session_data["resume_data"], 
                            on_tool_call=on_tool
                        )
                        return result
                    
                    worker_tasks.append(wrapped_worker(intent))
            
            if worker_tasks:
                logger.info(f"步骤 2: 并发分发给 Worker {active_intents}")
                yield {"data": json.dumps({"type": "status", "content": f"正在由 {', '.join(active_intents)} 专家并发处理..."})}
                
                # asyncio.gather 返回的是 Future，不能直接传给 create_task
                # 我们直接使用 gather 即可，它会并发运行所有 task
                workers_future = asyncio.gather(*worker_tasks)
                
                # 监听队列直到所有 worker 完成
                while not workers_future.done():
                    while not event_queue.empty():
                        msg = await event_queue.get()
                        yield {"data": json.dumps(msg)}
                    await asyncio.sleep(0.1)
                
                # 再次清空队列
                while not event_queue.empty():
                    msg = await event_queue.get()
                    yield {"data": json.dumps(msg)}
                
                results = await workers_future
                
                for i, updated_section in enumerate(results):
                    intent = active_intents[i]
                    worker = workers[intent]
                    session_data["resume_data"].update(updated_section)
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
            
            # 4. 常识校验与推理
            logger.info("步骤 3: 常识校验与推理")
            yield {"data": json.dumps({"type": "status", "content": "正在进行常识校验与职业推理..."})}
            inference_result = await inference_worker.analyze(session_data["resume_data"])
            yield {"data": json.dumps({
                "type": "status",
                "content": "常识校验完成",
                "debug": {
                    "agent": "InferenceWorker",
                    "model": inference_worker.last_model,
                    "duration": f"{inference_worker.last_duration:.2f}s"
                }
            })}
            # 将推理结果存入 session，供 Aggregator 使用
            session_data["inference_insights"] = inference_result.get("insights", [])

            # 5. 汇总回复
            logger.info("步骤 4: 汇总回复")
            yield {"data": json.dumps({"type": "status", "content": "正在生成回复..."})}
            response_text = await aggregator.aggregate(session_data, ", ".join(intents))
            
            # 6. 保存会话
            session_manager.save_session(session_id, session_data)
            
            yield {"data": json.dumps({
                "type": "final", 
                "content": response_text,
                "debug": {
                    "agent": "Aggregator",
                    "model": aggregator.last_model,
                    "duration": f"{aggregator.last_duration:.2f}s"
                }
            })}
            logger.info(f"=== 流式处理请求完成: session_id={session_id} ===")
            
        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            yield {"data": json.dumps({"type": "error", "content": str(e)})}

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    # 启动服务
    logger.info("正在启动简历生成 Agent 服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
