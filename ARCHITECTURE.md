# Chat-to-Resume Agent 架构文档

本项目是一个基于 LLM 的“对话式简历生成助手”，旨在通过多 Agent 协作模式，将用户的碎片化输入转化为结构化的专业简历。

## 1. 核心架构：多 Agent 编排 (Multi-Agent Orchestration)

系统采用 **Planner -> Workers -> Aggregator** 的经典编排模式，实现职责分离和质量控制。

### 1.1 路由中心 (Router / Planner)
- **模型**: `google/gemini-2.0-flash-exp:free` (侧重速度与意图识别)
- **职责**: 
    - 分析用户输入的意图（基本信息、工作经历、技能、闲聊）。
    - 决定分发给哪个专门的 Worker。
    - 识别当前简历中缺失的关键字段（Slot Filling）。

### 1.2 专业 Worker (Specialized Workers)
针对简历的不同模块，使用不同的模型策略：
- **InfoWorker**: 提取姓名、联系方式、教育背景等静态信息。
- **ExperienceWorker**: 使用 **STAR 法则**（Situation, Task, Action, Result）对工作/项目经历进行深度润色。
    - **模型**: `meta-llama/llama-3.3-70b-instruct:free` (侧重逻辑与文案质量)
- **SkillWorker**: 提取技术栈、工具、证书，并进行专业分类。

### 1.3 汇总协调官 (Aggregator)
- **职责**: 
    - 整合 Worker 的处理结果。
    - 根据当前简历的完整度，给出友好的对话反馈。
    - 引导用户补充缺失信息或确认生成最终文档。

---

## 2. 技术栈与工程实践

### 2.1 核心框架
- **FastAPI**: 提供异步 API 接口。
- **LangChain**: 用于构建和编排 Agent 链，支持结构化输出和提示词管理。
- **OpenRouter**: 统一接入多种免费/高性能模型（Gemini, Llama 3.3 等）。
- **UV**: 高性能 Python 包管理工具，替代传统的 pip/venv。

### 2.2 关键特性
- **会话持久化**: 基于 `session_id` 的 JSON 文件存储，支持断点续聊。
- **提示词解耦**: 所有 Agent 的 System Prompt 均抽离至 `src/prompts/*.md`，支持无代码调整 AI 行为。
- **性能监控**: 引入 `@time_it` 装饰器，实时记录并返回每个 Agent 的执行耗时。
- **结构化输出**: 强制 Worker 输出 JSON 格式，确保数据处理的稳定性。

---

## 3. 项目结构

```text
.
├── src/
│   ├── agent/
│   │   ├── base.py        # Agent 基类，封装 LLM 调用与耗时统计
│   │   ├── router.py      # 意图识别与任务分发
│   │   ├── workers.py     # 专项处理（信息、经历、技能）
│   │   ├── aggregator.py  # 结果汇总与对话生成
│   │   └── session.py     # 会话存储管理
│   ├── prompts/           # 提示词模板库 (.md)
│   ├── config.py          # 模型与 API 全局配置
│   └── main.py            # FastAPI 入口与业务编排
├── sessions/              # 会话数据存储目录
├── Makefile               # 自动化开发指令 (install, dev, sync)
└── pyproject.toml         # 依赖管理
```

---

## 4. 开发与运行

### 快速启动
```bash
make install  # 初始化环境
make dev      # 启动开发服务器 (localhost:8000)
```

### 接口测试
```bash
curl -X POST http://localhost:8000/chat \
-H "Content-Type: application/json" \
-d '{"message": "你好，我想写一份简历", "session_id": "user_001"}'
```

---

## 5. 后续规划
1. **Pydantic 校验**: 引入数据模型校验，确保简历 JSON 的严谨性。
2. **PDF 导出**: 集成模板引擎，支持一键生成 Markdown 或 PDF 简历。
3. **多轮追问**: 针对描述模糊的经历，Worker 能够主动发起追问。
