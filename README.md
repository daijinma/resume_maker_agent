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
   OHMYGPT_API_KEY=your_key_here
   ```
   
   注意：根据 `src/config/models.json` 中配置的供应方，设置对应的 API Key。

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

## 模型供应方配置

系统支持多个模型供应方，会根据模型名称自动选择供应方。

### 支持的供应方

1. **OpenRouter**
   - API 地址: `https://openrouter.ai/api/v1`
   - 环境变量: `OPENROUTER_API_KEY`
   - 使用规则：仅支持以 `:free` 结尾的模型

2. **OhMyGPT**
   - API 地址: `https://api.ohmygpt.com/v1`
   - 环境变量: `OHMYGPT_API_KEY`
   - 使用规则：所有不以 `:free` 结尾的模型

### 自动判断规则

系统会根据模型名称自动判断使用哪个供应方：

- **以 `:free` 结尾的模型** → 使用 OpenRouter
  - 例如：`meta-llama/llama-3.2-3b-instruct:free`
  - 例如：`qwen/qwen3-4b:free`

- **其他模型** → 使用 OhMyGPT
  - 例如：`gemini-2.0-flash-lite`
  - 例如：`gpt-4`

### 配置方式

在 `src/config/models.json` 中：

1. **配置供应方信息**：
   ```json
   {
     "openrouter": {
       "api_key": "${OPENROUTER_API_KEY}",
       "base_url": "https://openrouter.ai/api/v1",
       "default_headers": {}
     },
     "ohmygpt": {
       "api_key": "${OHMYGPT_API_KEY}",
       "base_url": "https://api.ohmygpt.com/v1",
       "default_headers": {}
     }
   }
   ```

2. **配置 Agent 模型列表**（无需指定 provider）：
   ```json
   {
     "agents": {
       "planner": {
         "models": [
           "meta-llama/llama-3.2-3b-instruct:free",
           "gemini-2.0-flash-lite"
         ],
         "temperature": 0.3,
         ...
       }
     }
   }
   ```

   系统会根据模型名称自动选择对应的供应方。

### 环境变量

确保在 `.env` 文件中设置了对应供应方的 API Key：
- `OPENROUTER_API_KEY`: OpenRouter 的 API Key（用于 `:free` 模型）
- `OHMYGPT_API_KEY`: OhMyGPT 的 API Key（用于其他模型）

## Makefile 命令说明

- `make install`: 安装项目所需的所有依赖。
- `make dev`: 启动 FastAPI 开发服务器（默认端口 8000）。
- `make clean`: 清理项目中的 Python 缓存文件。
