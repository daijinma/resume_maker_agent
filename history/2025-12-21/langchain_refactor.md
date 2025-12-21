# Chat-to-Resume Agent 架构文档 (2025-12-21 存档 - LangChain 版)

本项目已重构为基于 **LangChain** 的多 Agent 协作模式。

## 1. 核心架构：LangChain 链式编排

系统利用 LangChain 的表达式语言 (LCEL) 重新构建了 Agent 逻辑。

### 1.1 基础 Agent (`BaseAgent`)
- 使用 `ChatOpenAI` 适配 OpenRouter。
- 封装了 `run_chain` 方法，通过 `ChatPromptTemplate | LLM | OutputParser` 自动处理提示词填充和结果解析。

### 1.2 路由中心 (Router)
- **职责**: 意图识别。
- **实现**: `router_prompt | llm | JsonOutputParser()`。

### 1.3 专业 Worker
- **实现**: 针对不同模块（Info, Experience, Skill）构建独立的处理链。
- **特点**: 强制 JSON 输出，确保数据合并的稳定性。

---

## 2. 技术栈更新
- **LangChain**: 核心编排框架。
- **langchain-openai**: 用于调用 OpenRouter 兼容接口。
- **FastAPI + SSE**: 实时可视化调试。

---

## 3. 优势
- **代码更简洁**: 减少了手动处理 JSON 解析和 Prompt 拼接的逻辑。
- **扩展性强**: 方便后续引入 LangGraph 进行更复杂的循环对话管理。
- **标准化**: 遵循社区主流的 Agent 开发模式。
