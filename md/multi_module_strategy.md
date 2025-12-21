# 简历多模块生成逻辑的设计策略

在构建复杂的简历生成 Agent 时，随着模块（教育、工作、项目、技能等）的增加，单一的 Prompt 会变得臃肿且难以维护。以下是推荐的进阶策略：

## 1. 模块化生成 (Modular Generation)
**策略**：不要试图一次性生成整份简历，而是按模块拆分任务。
- **优点**：降低 LLM 的推理压力，提高每个模块的精准度。
- **实现**：
  - `Planner` 识别当前对话涉及哪个模块。
  - `Executor` 针对不同模块调用不同的子 Prompt（如 `education_prompt`, `project_prompt`）。
  - 最后由一个 `Aggregator`（聚合器）将各模块 JSON 合并。

## 2. 动态槽位填充 (Dynamic Slot Filling)
**策略**：使用状态机或图结构（如 LangGraph）管理对话流。
- **实现**：
  - 定义每个模块的“必填项”和“选填项”。
  - `Planner` 检查 `slots` 的完整性，自动生成追问列表。
  - 只有当核心模块（如个人信息、至少一段经历）填充完毕后，才触发 `Executor`。

## 3. 结构化输出校验 (Pydantic Validation)
**策略**：使用 Pydantic 定义严格的数据模型。
- **实现**：
  - 在代码中定义 `ResumeSchema` 类。
  - 利用 LLM 的 `response_format={"type": "json_object"}` 功能。
  - 接收到 JSON 后立即进行 Pydantic 校验，如果失败则触发自动重试或修复逻辑。

## 4. 迭代式润色 (Iterative Refinement)
**策略**：先生成草稿，再根据用户反馈局部修改。
- **实现**：
  - 用户说“把项目经验写得更技术化一点”。
  - Agent 只针对 `project_experience` 模块重新调用 LLM，保持其他模块不变。

## 5. 知识库辅助 (RAG for Resume)
**策略**：引入行业词库和优秀范文。
- **实现**：
  - 当用户提到“Java 开发”时，从向量数据库检索相关的“高频技能词”和“项目描述范式”，作为 Context 喂给 LLM。
