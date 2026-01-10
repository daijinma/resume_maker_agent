# ReAct Agent 模式实现文档

## 概述

ReAct（Reasoning and Acting）模式是一种结合推理和行动的 AI Agent 架构。该模式通过 **思考(Think) -> 执行(Act) -> 观察(Observe) -> 评估(Evaluate)** 的循环迭代，逐步完善答案，直到满足停止条件。

本实现将 ReAct 模式集成到现有的 Agent 服务框架中，支持流式输出（SSE）、工具调用、会话管理等完整功能。


## 核心特性

### 1. Think-Act-Observe-Evaluate 循环

- **Think（思考）**：分析用户问题，确定需要的信息和工具
- **Act（执行）**：调用相应工具获取信息或执行计算
- **Observe（观察）**：分析工具返回的结果
- **Evaluate（评估）**：判断答案是否完整，决定是否继续迭代

### 2. 工具集成

支持以下工具：

- **web_search**：网络搜索工具（使用博查 API）
  - 参数：`query`（搜索查询）、`max_results`（最大结果数，默认5）
  - 返回：包含 `title`、`url`、`snippet`、`source` 的搜索结果列表
  
- **calculate**：数学表达式计算工具
  - 支持操作符：`+`、`-`、`*`、`/`、`//`、`%`、`**`、`^`
  - 支持括号和基本数学运算
  
- **date_calculator**：日期计算工具
  - 支持日期差值计算、日期加减运算
  - 支持格式：`YYYY-MM-DD` 或 `YYYY.MM`

### 3. 流式输出（SSE）

实时推送以下事件：

- **react_step**：每次循环步骤的详细信息
  - `iteration`：当前迭代轮次
  - `step`：步骤类型（think/act/observe/evaluate）
  - `description`：步骤描述
  - `model`：使用的模型
  - `input_tokens`、`output_tokens`、`total_tokens`：Token 使用情况
  - `duration`：耗时
  - `content`：步骤内容预览

- **partial**：流式输出内容片段
- **final**：最终答案
- **model_request**：模型请求开始
- **model_response**：模型响应完成（包含总 Token 和迭代次数）

### 4. 前端可视化

前端界面支持：

- 不同阶段用颜色区分（Think/Act/Observe/Evaluate）
- 显示轮次信息和阶段标识
- 混合显示日志信息和输出内容
- 实时展示模型、Token、耗时等信息

## 架构设计

### 文件结构

```
src/
├── agents/
│   ├── react_agent.py          # ReAct Agent 核心实现
│   └── react_tools.py          # ReAct 工具集合
├── service/
│   └── react_service.py        # ReAct 服务层
├── prompts/
│   └── react_agent.md          # ReAct 系统提示词
├── api/
│   └── routes.py               # API 路由（集成 ReAct）
└── config/
    └── models.json             # 模型配置（包含 react_agent）
```

### 核心类

#### ReActAgent

继承自 `BaseAgent`，实现 ReAct 循环逻辑。

**主要方法：**

- `run_react_loop()`：执行完整的 ReAct 循环
  - 参数：
    - `user_question`：用户问题
    - `session_id`：会话 ID
    - `on_sse_event`：SSE 事件回调
    - `conversation_history`：对话历史
  - 返回：
    - `answer`：最终答案
    - `iterations`：迭代次数
    - `total_tokens`：Token 统计
    - `total_duration`：总耗时
    - `steps`：所有步骤详情

- `_send_step_event()`：发送步骤事件到前端

#### ReActService

服务层，处理消息和会话管理。

**主要方法：**

- `process_message()`：处理用户消息
  - 保存用户消息
  - 获取会话历史
  - 调用 `ReActAgent.run_react_loop()`
  - 保存 AI 响应
  - 发送 SSE 事件

### 配置

在 `src/config/models.json` 中配置：

```json
{
  "react_agent": {
    "models": ["gemini-2.0-flash-lite"],
    "temperature": 0.7,
    "max_tokens": 8192,
    "timeout": 60.0,
    "max_iterations": 5
  }
}
```

### API 集成

在 `src/api/routes.py` 中：

1. 添加 `AgentType.REACT` 枚举值
2. 在 `stream()` 函数中处理 `REACT` 类型
3. 调用 `get_react_service()` 获取服务实例
4. 处理 `react_step` 事件的 SSE 输出

## 工作流程

### 1. 用户请求流程

```
用户提问
  ↓
API 路由接收请求（agent_type=REACT）
  ↓
ReActService.process_message()
  ↓
保存用户消息到历史
  ↓
ReActAgent.run_react_loop()
  ↓
循环执行 Think-Act-Observe-Evaluate
  ↓
发送 SSE 事件（react_step, partial, final）
  ↓
生成最终答案
  ↓
保存 AI 响应到历史
  ↓
返回结果
```

### 2. ReAct 循环流程

```
开始
  ↓
[Think] 分析问题，确定需要的信息
  ↓
[Act] 调用工具（web_search/calculate/date_calculator）
  ↓
[Observe] 分析工具返回结果
  ↓
[Evaluate] 评估答案完整性
  ↓
答案完整？ → 是 → 生成最终答案 → 结束
  ↓ 否
达到最大迭代次数？ → 是 → 生成最终答案 → 结束
  ↓ 否
继续下一轮迭代
```

## 工具实现细节

### web_search 工具

**实现位置：** `src/agents/react_tools.py`

**API 集成：**
- 使用博查 API（`https://api.bocha.cn/v1/web-search`）
- 需要环境变量 `BOCHA_API_KEY`
- 支持异步调用

**返回格式：**
```python
[
    {
        "title": "网站标题",
        "url": "https://example.com",
        "snippet": "内容摘要",
        "source": "来源网站"
    },
    ...
]
```

### calculate 工具

**安全措施：**
- 限制可用的操作符（`SAFE_OPERATORS`）
- 验证表达式只包含数字、操作符和括号
- 使用受限的 `eval()` 环境

### date_calculator 工具

**支持的操作：**
- `diff`：计算两个日期的差值
- `add_days`：日期加天数
- `subtract_days`：日期减天数

## 前端集成

### HTML 更新

在 `static/index.html` 中添加：

- ReAct 模式选项到 Agent 选择下拉框
- CSS 样式类：
  - `.react-step`：步骤容器
  - `.react-step.think`：思考阶段（蓝色）
  - `.react-step.act`：执行阶段（绿色）
  - `.react-step.observe`：观察阶段（黄色）
  - `.react-step.evaluate`：评估阶段（紫色）
  - `.react-output`：输出内容

### JavaScript 更新

在 `static/js/chat.js` 中：

- 处理 `react_step` 事件
- 创建步骤显示元素
- 显示轮次、阶段、模型、Token、耗时等信息
- 混合显示日志和输出内容

## 环境配置

### 必需的环境变量

```bash
# 博查 API Key（用于 web_search 工具）
BOCHA_API_KEY=sk-xxxxxxxxxxxxx
```

### 依赖包

在 `pyproject.toml` 中已添加：

```toml
requests = "^2.31.0"  # 用于 web_search API 调用
```

## 使用示例

### API 调用

```bash
# POST 请求
curl -X POST "http://localhost:8000/api/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "chat",
    "session_id": "test-session",
    "agent_type": "react",
    "message": "Python 3.12 的新特性有哪些？"
  }'
```

### 前端使用

1. 在 Agent 选择下拉框中选择 "ReAct 模式"
2. 输入问题
3. 观察实时显示的步骤信息：
   - 轮次标识（第 X 轮）
   - 阶段标识（思考/执行/观察/评估）
   - 模型信息
   - Token 使用情况
   - 耗时统计
4. 查看最终答案

## 技术细节

### 流式模式与工具调用的兼容性

**问题：** 某些模型提供者不支持在流式模式下使用工具。

**解决方案：**
- 在 `BaseAgent.run_chain()` 中检测错误
- 当检测到 "Tools are not supported in streaming mode" 错误时
- 自动切换到非流式模式（`ainvoke`）进行工具调用
- 工具调用完成后继续流式输出

### Token 统计

- 每个步骤的 Token 使用情况单独统计
- 最终汇总所有步骤的 Token 使用
- 在 `model_response` 事件中返回总 Token 和迭代次数

### 停止条件

1. **答案完整**：Agent 评估认为答案已完整
2. **达到最大迭代次数**：默认 5 次，可在配置中调整
3. **无法获取更多信息**：工具调用无法提供有用信息

## 优化建议

### 已实现的优化

1. ✅ 工具检测逻辑优化：优先检测是否需要网络搜索
2. ✅ 提示词优化：强调优先使用 `web_search`，移除不存在的工具引用
3. ✅ SSE 事件优化：确保所有字段正确传递到前端
4. ✅ 前端样式优化：不同阶段用颜色区分，混合显示日志和输出

### 未来可能的优化

1. 支持更多工具（如代码执行、文件读取等）
2. 优化工具选择策略（基于问题类型自动选择）
3. 支持并行工具调用
4. 添加工具调用缓存机制
5. 支持自定义停止条件

## 问题排查

### 常见问题

1. **前端显示 "第 undefined 轮"**
   - 原因：SSE 事件中缺少 `iteration` 字段
   - 解决：确保 `react_step` 事件包含所有必需字段

2. **模型一直调用 get_current_time**
   - 原因：提示词中提到了不存在的工具
   - 解决：从提示词中移除 `get_current_time` 的提及

3. **工具调用失败**
   - 检查环境变量 `BOCHA_API_KEY` 是否设置
   - 检查网络连接
   - 查看日志中的错误信息

## 相关文件

- `src/agents/react_agent.py`：核心实现
- `src/agents/react_tools.py`：工具定义
- `src/service/react_service.py`：服务层
- `src/prompts/react_agent.md`：系统提示词
- `src/api/routes.py`：API 路由
- `static/index.html`：前端 HTML
- `static/js/chat.js`：前端 JavaScript
- `src/config/models.json`：模型配置

## 总结

ReAct 模式的实现成功地将推理和行动结合起来，通过迭代循环逐步完善答案。该实现：

- ✅ 完整支持 Think-Act-Observe-Evaluate 循环
- ✅ 集成网络搜索、计算、日期计算等工具
- ✅ 支持流式输出和实时反馈
- ✅ 提供友好的前端可视化
- ✅ 兼容现有的 Agent 服务框架

该模式特别适合需要查询最新信息、进行复杂推理或需要多步骤处理的问题。

