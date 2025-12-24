# TODO 列表

1. 初始化项目仓库 (`git init`、创建 `README.md`) — 已完成。
2. 添加 `note` 目录用于对话压缩记录、TODO 管理、辅助素材 — 已完成。
3. 创建 `md` 目录用于后续知识点沉淀 — 已完成。
4. 搭建 `src` 目录结构与基础 Agent 模块 — 已完成。
5. 使用 OpenRouter (Gemini 免费模型) 和 FastAPI 封装 Demo — 已完成。
6. 创建 Makefile 简化安装与开发流程 (已升级为使用 uv 和 venv) — 已完成。
7. 引入 session_id 关联的 JSON 持久化存储 — 已完成。
8. 实现结构化 JSON 输出与完整简历文本生成 — 已完成。
9. 架构重构：引入 Orchestrator 模式，拆分 API、Workers 与工厂模块 — 已完成。
10. 槽位闭环：实现 Router 缺失信息识别与 Aggregator 自动追问 — 已完成。
11. 后续：接入 Pydantic 进行严格模型校验、实现 PDF 导出功能、引入对话历史上下文。

## 模型选型与性能优化记录 (2025-12-23)
- **Router:** `meta-llama/llama-3.2-3b-instruct:free` (极速响应，兼容性好)
- **Workers:** `mistralai/mistral-small-3.1-24b-instruct:free` (平衡速度与提取能力)
- **Inference:** `google/gemini-2.0-flash-exp:free` (高智能，仅在必要时异步调用)
- **Aggregator:** `meta-llama/llama-3.3-70b-instruct:free` (保证最终输出质量)

**优化目标：**
- [x] 实现“意图快车道”：闲聊意图直接跳过 Worker。
- [x] 实现“延迟推理”：Inference 不再阻塞主流程。
- [x] 实现“状态反馈”：前端立即显示当前 Agent 进度。
- [x] 优化 Aggregator 提示词：口语化、简练、HR 风格，提升响应速度。
