# 聊天生成简历 Agent 项目

A教育公司聊天简历生成 Agent 项目初始化仓库。

- 目标：探索基于 LLM 的“聊天生成简历”流程与 Agent 架构
- 技术：Python + UV（如需）
- 内容：逐步构建用例、流程图、知识积累、demo

## 技术栈与运行依赖

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - 超快的 Python 包管理工具
- `FastAPI` + `uvicorn` 用于暴露 API 接口
- `httpx` 用于异步调用 OpenRouter API
- `python-dotenv` 管理环境变量

## 快速开始

1. **安装 uv** (如果尚未安装):
   ```bash
   curl -LsSf https://astral-sh.uv.run/install.sh | sh
   ```

2. **配置环境**：
   在项目根目录创建 `.env` 文件并填入：
   ```env
   OPENROUTER_API_KEY=your_key_here
   ```

3. **安装依赖**：
   ```bash
   make install
   ```

4. **启动服务**：
   ```bash
   make dev
   ```

4. **测试接口**：
   使用 Postman 或 curl 访问 `POST http://localhost:8000/chat`，发送 JSON：
   ```json
   {
     "message": "我是一名金融分析师，负责过某基金的定量分析项目。"
   }
   ```

## Makefile 命令说明

- `make install`: 安装项目所需的所有依赖。
- `make dev`: 启动 FastAPI 开发服务器（默认端口 8000）。
- `make clean`: 清理项目中的 Python 缓存文件。
