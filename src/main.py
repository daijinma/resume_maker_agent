import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.endpoints import api_router

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("resume-api")

app = FastAPI(title="Chat-to-Resume Multi-Agent API")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 包含业务路由
app.include_router(api_router)

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
