# 角色
你是经验丰富的agent工程师，现在我俩在一个公司，正遇到新的业务需求，通过确实的需求，帮助我成为合格的agent工程师， 本期宗旨是帮我理解LLM的模式设计。

# 公司和需求背景背景
公司：A教育公司，主做成人和应届生教育
业务：现在正在做一套app，我们正在研究‘聊天生成简历’ 的agent 服务。

# 关于获取知识和调用参考
可以通过 github、huggingface 等平台

# 输入
- 我可能说任何问题，先要理解我说话的中心，有疑问需要跟我确认

# 输出
- 可以考虑多方面的案例、可以考虑流程图等多种方式帮助我理解和表达你的言论
- 可以向我提问
- 中文回答
- 可以在当前项目用 python 和 uv 等技术手段表达
- 可以通过链接、代码段的形式表达

md 和 note 文件夹是给你用的，src 是我们整个代码的范围

---

# Agent 模式总览

本项目实现了多种 Agent 模式，用于不同的业务场景。

## 1. Planner-Worker 模式（简历生成）

**用途：** 聊天生成简历的核心模式

**特点：**
- 路由 Agent 分析用户意图，分配到不同的 Worker
- 多个 Worker 并行处理不同字段（信息、经历、技能、教育等）
- Aggregator 聚合所有结果
- 支持多轮对话和字段补全

**适用场景：** 结构化数据提取和简历生成

**相关文档：** `docs/updates_20250123.md`

## 2. Dual-Track 模式（双轨推理）

**用途：** 简历生成的增强模式

**特点：**
- 主轨道：正常对话流程
- 背景推理轨道：异步推理和问题生成
- 支持待处理问题队列
- 更智能的问题补全策略

**适用场景：** 需要深度推理和问题补全的简历生成

**相关文档：** `docs/dual_track_implementation_summary.md`

## 3. Simple Chat 模式（简单对话）

**用途：** 通用对话模式

**特点：**
- 简单的对话流程
- 无结构化数据提取
- 适合一般性问答

**适用场景：** 非简历相关的普通对话

## 4. ReAct 模式（推理与行动）⭐ 新增

**用途：** 回答用户的正常问题，通过思考-执行-观察循环迭代完善答案

**特点：**
- **Think（思考）**：分析问题，确定需要的信息和工具，判断答案是否完整，输出 JSON 格式
- **Act（执行）**：根据 Think JSON 中的工具参数调用工具（不再使用关键词匹配）
- **Observe（观察）**：分析工具返回结果，输出 JSON 格式
- **JSON 数据传递**：各阶段通过结构化 JSON 传递信息，确保准确解析
- **参数化工具触发**：通过 JSON 参数指定工具，而不是关键词匹配
- **独立 log 事件**：每个步骤都有独立的 log 事件传输到页面
- **工具调用详细日志**：工具调用前和调用后都有独立的 log 事件，包含工具名称、参数、返回结果、耗时、错误信息
- 支持多轮迭代，直到 `is_complete` 为 `true`
- 实时显示每轮步骤和 Token 使用情况

**工作流程：**
```
用户问题 → Think（输出 JSON）→ Act（根据 JSON 调用工具）→ Observe（输出 JSON）
→ 检查 is_complete → 如果为 true，生成最终答案（纯文本）→ 返回前端
```

**Think 阶段 JSON 格式：**
```json
{
  "reasoning": "思考内容（1-2句话）",
  "needs_tool": true,
  "tool_name": "web_search",
  "tool_params": {
    "query": "搜索查询内容",
    "max_results": 5
  },
  "is_complete": false,
  "next_action": "需要搜索相关信息"
}
```

**Observe 阶段 JSON 格式：**
```json
{
  "observation": "观察到的结果分析",
  "has_enough_info": true,
  "needs_more": false
}
```

**工具支持：**
- `web_search`：网络搜索（使用博查 API）
- `calculate`：数学表达式计算
- `date_calculator`：日期计算
- `get_current_time`：获取当前系统时间

**工具触发机制：**
- 不再使用关键词匹配
- 从 Think JSON 中读取 `tool_name` 和 `tool_params`
- Act 阶段根据 JSON 参数直接调用对应工具

**停止条件：**
- Think JSON 中的 `is_complete` 为 `true`
- 达到最大迭代次数（默认 5 次）
- 无法获取更多信息

**最终答案生成：**
- 当 `is_complete` 为 `true` 时，停止循环
- 使用包含所有迭代完整上下文的提示词生成最终答案
- **最终答案必须是纯文本格式，不能是 JSON**

**适用场景：**
- 需要查询最新信息的问题
- 需要多步骤推理的问题
- 需要工具辅助计算的问题
- 需要迭代完善答案的问题

**实现日期：** 2025-01-24

**最新更新：** 2025-01-24
- 添加 JSON 格式数据传递
- 添加参数化工具触发机制
- 添加独立的 log 事件传输
- 添加工具调用详细日志
- 优化最终答案生成逻辑

**相关文档：** 
- `ReAct_prompt.md`：完整实现提示词和架构设计
- `docs/react_agent_implementation.md`：实现文档

**配置位置：** `src/config/models.json` → `react_agent`

**前端使用：** 在 Agent 选择下拉框中选择 "ReAct 模式 (Think-Act-Observe)"

**环境变量：**
```bash
BOCHA_API_KEY=sk-xxxxxxxxxxxxx  # 用于 web_search 工具
```

## Agent 选择指南

| 场景 | 推荐模式 | 说明 |
|------|---------|------|
| 生成简历 | Planner-Worker 或 Dual-Track | 结构化数据提取 |
| 一般对话 | Simple Chat | 简单问答 |
| 需要查询信息 | ReAct | 网络搜索、多步推理 |
| 需要计算 | ReAct | 数学计算、日期计算 |
| 复杂推理问题 | ReAct | 迭代完善答案 |

## 技术架构

所有 Agent 模式都基于统一的架构：

- **BaseAgent**：基础 Agent 类，提供模型调用、工具支持等
- **Service 层**：业务逻辑处理，会话管理
- **API 层**：统一的 SSE 流式接口
- **前端**：统一的聊天界面，支持不同模式的特殊显示

## 相关文档

- `docs/react_agent_implementation.md`：ReAct 模式详细实现文档
- `docs/updates_20250123.md`：项目重构和架构说明
- `docs/dual_track_implementation_summary.md`：Dual-Track 模式说明
- `docs/agent_selection_guide.md`：Agent 选择指南

