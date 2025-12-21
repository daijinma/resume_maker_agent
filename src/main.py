import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from agent import Planner, Executor, Tooling
from agent.session import SessionManager
from agent.planner import PlannerState
import uvicorn

# 配置日志格式，方便追踪 Agent 的决策流转
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("resume-agent")

app = FastAPI(title="Resume Agent API")

# 核心组件实例化
session_manager = SessionManager()
executor = Executor()
tooling = Tooling()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    reply: str
    status: str
    data: Optional[Dict[str, Any]] = None

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Agent 对话主入口：
    1. 加载/初始化 Session
    2. Planner 识别意图与缺失信息
    3. 如果信息不足，引导用户补充
    4. 如果信息足够，Executor 调用 LLM 生成结构化 JSON
    """
    logger.info(f"收到用户消息: {request.message} (Session: {request.session_id})")
    
    # --- 阶段 1: 加载会话状态 ---
    session_data = session_manager.get_session(request.session_id)
    if session_data:
        # 简单处理，将字典转回 PlannerState
        state = PlannerState(
            slots=session_data.get("slots", {}),
            pending_questions=session_data.get("pending_questions", [])
        )
        planner = Planner(state=state)
    else:
        planner = Planner()
    
    # --- 阶段 2: 意图识别与状态更新 ---
    planner.ingest_user_message(request.message)
    
    # 保存当前状态
    session_manager.save_session(request.session_id, planner.state)
    
    # --- 阶段 3: 决策下一步行动 ---
    action = planner.next_action()
    logger.info(f"Planner 决策行动: {action}")
    
    if action.startswith("需要用户补充"):
        return ChatResponse(
            reply=action, 
            status="collecting",
            data={"slots": planner.state.slots}
        )
    
    # --- 阶段 4: 执行生成任务 ---
    logger.info("信息已足够，开始调用 Executor 生成结构化简历...")
    
    # 调用 Executor 生成完整 JSON
    structured_result = await executor.generate_full_resume(planner.state.slots)
    
    # 校验
    validation = executor.validate(structured_result)
    logger.info(f"内容生成完成，校验结果: {validation}")
    
    return ChatResponse(
        reply="简历内容已生成！",
        status="completed",
        data=structured_result
    )

if __name__ == "__main__":
    # 启动服务
    logger.info("正在启动简历生成 Agent 服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
