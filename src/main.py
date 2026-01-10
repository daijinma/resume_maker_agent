import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import api_router
from src.utils.logger import setup_logger

# 初始化日志
# 配置根 logger，确保所有子 logger 都能输出
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if not root_logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

# 配置特定的 logger
setup_logger("resume-api", logging.INFO)
setup_logger("resume-agent", logging.INFO)  # 配置 resume-agent 父 logger
setup_logger("api", logging.INFO)  # 配置 api 父 logger
setup_logger("service", logging.INFO)  # 配置 service 父 logger

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
