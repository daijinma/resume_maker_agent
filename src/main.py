import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import api_router
from src.utils.logger import setup_logger

# 初始化日志
setup_logger("resume-api", logging.INFO)
logger = logging.getLogger("resume-api")

app = FastAPI(title="Chat-to-Resume Multi-Agent API")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 包含业务路由（不带前缀，用于 /stream 等）
app.include_router(api_router)
# 包含业务路由（带 /api 前缀，用于 REST API）
app.include_router(api_router, prefix="/api", tags=["api"])

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """主页入口"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Static UI not found. Please check static/index.html</h1>"

if __name__ == "__main__":
    # 启动服务
    logger.info("正在启动简历生成 Agent 服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
