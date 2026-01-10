# ReAct Agent 完整实现提示词

## 项目概述

实现一个 ReAct（Reasoning and Acting）模式的 AI Agent，通过 Think（思考）-> Act（执行）-> Observe（观察）循环迭代完善答案，支持工具调用、流式输出和前端可视化。Think 阶段负责分析问题、判断答案是否完整并确定下一步行动。

## 一、架构设计

### 1.1 核心组件

- **ReActAgent**：核心代理类，实现 ReAct 循环逻辑
- **ReActService**：服务层，处理消息和会话管理
- **react_tools**：工具集合（`web_search`、`calculate`、`date_calculator`、`get_current_time`）
- **react_agent.md**：系统提示词文件
- **API 路由**：集成到现有路由系统
- **前端界面**：可视化显示 ReAct 循环过程

### 1.2 数据流

```
用户问题 → API 路由 → ReActService → ReActAgent.run_react_loop() 
→ Think（分析问题、判断答案完整性、确定下一步，输出 JSON）→ Act（根据 JSON 参数调用工具）→ Observe（分析结果，输出 JSON）
→ 判断是否继续（从 Think JSON 中读取） → 生成最终答案 → 返回前端
```

### 1.3 JSON 数据传递格式

各阶段之间通过 JSON 格式传递结构化信息，确保信息传递的准确性和可解析性。

#### Think 阶段输出 JSON 格式

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

**字段说明：**
- `reasoning`：思考内容，简洁明了（1-2句话）
- `needs_tool`：是否需要调用工具（boolean）
- `tool_name`：工具名称，可选值：`"web_search"`、`"calculate"`、`"date_calculator"`、`"get_current_time"` 或 `null`
- `tool_params`：工具参数对象，根据工具类型不同而不同
  - `web_search`: `{"query": "搜索内容", "max_results": 5}`
  - `calculate`: `{"expression": "数学表达式"}`
  - `date_calculator`: `{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "operation": "diff"}`
  - `get_current_time`: `{}`
- `is_complete`：答案是否完整（boolean）
- `next_action`：下一步行动描述

#### Observe 阶段输出 JSON 格式

```json
{
  "observation": "观察到的结果分析",
  "has_enough_info": true,
  "needs_more": false
}
```

**字段说明：**
- `observation`：观察结果分析
- `has_enough_info`：是否已有足够信息（boolean）
- `needs_more`：是否需要更多信息（boolean）

#### 工具触发机制

- **不再使用关键词匹配**，改为从 Think 阶段的 JSON 中读取 `tool_name` 和 `tool_params`
- Act 阶段根据 Think JSON 中的 `tool_name` 和 `tool_params` 直接调用对应工具
- 如果 `needs_tool` 为 `false`，则跳过工具调用

### 1.4 SSE 事件流

- `model_request`：开始处理
- `react_step`：每个步骤的详细信息（`iteration`、`step`、`model`、`tokens`、`duration`、`content`、`tool_calls`）
- `react_log`：**每个步骤的独立日志事件**（`iteration`、`step`、`log_type`、`message`、`data`）
  - `log_type`：日志类型，可选值：`"think"`、`"act"`、`"observe"`、`"tool_call"`、`"tool_result"`
  - `message`：日志消息（人类可读的描述）
  - `data`：结构化数据（JSON 对象）
- `partial`：流式输出内容片段（需包含 `react_iteration` 和 `react_step`）
- `final`：最终答案
- `model_response`：处理完成（包含总 token 和迭代次数）

#### react_log 事件详细说明

**Think 阶段 log：**
```json
{
  "type": "react_log",
  "data": {
    "iteration": 1,
    "step": "think",
    "log_type": "think",
    "message": "思考：分析问题需要什么信息",
    "data": {
      "reasoning": "思考内容",
      "needs_tool": true,
      "tool_name": "web_search",
      "is_complete": false
    }
  }
}
```

**Act 阶段 log（工具调用前）：**
```json
{
  "type": "react_log",
  "data": {
    "iteration": 1,
    "step": "act",
    "log_type": "tool_call",
    "message": "调用工具：web_search",
    "data": {
      "tool_name": "web_search",
      "tool_params": {
        "query": "搜索内容",
        "max_results": 5
      }
    }
  }
}
```

**Act 阶段 log（工具调用后）：**
```json
{
  "type": "react_log",
  "data": {
    "iteration": 1,
    "step": "act",
    "log_type": "tool_result",
    "message": "工具返回结果：web_search",
    "data": {
      "tool_name": "web_search",
      "tool_params": {
        "query": "搜索内容",
        "max_results": 5
      },
      "result": {
        "success": true,
        "data": [...],
        "duration": 1.23
      },
      "error": null
    }
  }
}
```

**Observe 阶段 log：**
```json
{
  "type": "react_log",
  "data": {
    "iteration": 1,
    "step": "observe",
    "log_type": "observe",
    "message": "观察：分析工具返回结果",
    "data": {
      "observation": "观察结果分析",
      "has_enough_info": true,
      "needs_more": false
    }
  }
}
```

## 二、后端实现

### 2.1 AgentType 枚举

在 `src/schema/session.py` 的 `AgentType` 枚举中添加：

```python
REACT = "react"
```

### 2.2 工具定义（react_tools.py）

创建 `src/agents/react_tools.py`，定义以下工具：

#### `get_current_time`

- 返回当前系统日期时间（YYYY-MM-DD HH:MM:SS）
- 用于需要当前时间的场景

#### `calculate`

- 执行数学表达式（+、-、*、/、//、%、**、^）
- 使用安全的 eval 环境，限制可用操作符
- 验证表达式只包含数字、操作符和括号

#### `date_calculator`

- 计算日期差值或进行日期运算
- 支持格式：YYYY-MM-DD
- 操作类型：`diff`（差值）、`add`（加天数）、`sub`（减天数）

#### `web_search`

- 使用博查 API（https://api.bocha.cn/v1/web-search）
- 需要环境变量 `BOCHA_API_KEY`
- 参数：`query`（搜索查询）、`max_results`（最大结果数，默认 5）
- 返回格式：包含 `title`、`url`、`snippet`、`source` 的列表
- 错误处理：网络异常、API 错误、数据解析错误

工具列表：

```python
REACT_TOOLS = [get_current_time, calculate, date_calculator, web_search]
```

### 2.3 ReActAgent 类（react_agent.py）

继承自 `BaseAgent`，实现以下核心方法：

#### `__init__`

- 接收 `models`、`temperature`、`max_tokens`、`timeout`、`max_iterations`、`tools`
- 从 `models.json` 读取 `react_agent` 配置
- 调用父类初始化，传入 `tools`

#### `_get_agent_type`

- 返回 `"react_agent"`

#### `_send_step_event`

- 发送 `react_step` 类型的 SSE 事件
- 包含字段：`iteration`、`step`、`description`、`model`、`input_tokens`、`output_tokens`、`total_tokens`、`duration`、`content`（预览，think/act/observe 限制 50 字符，final 限制 200 字符）、`tool_calls`（工具调用信息列表）

#### `run_react_loop`

主循环方法

- **参数**：`user_question`、`session_id`、`on_sse_event`、`conversation_history`
- **返回**：`answer`、`iterations`、`total_tokens`、`total_duration`、`steps`

**流程：**

1. 加载系统提示词（`react_agent.md`）
2. 初始化状态：`iteration=0`、`accumulated_context=[]`、`total_tokens`、`total_duration`
3. 循环执行（最多 `max_iterations` 次）：
   - `iteration += 1`
   - **Think**：调用 `_think_stage(iteration, ...)`，分析问题，输出 JSON（包含 `reasoning`、`needs_tool`、`tool_name`、`tool_params`、`is_complete`、`next_action`），**发送 Think log 事件**
   - **Act**：调用 `_act_stage(think_json, iteration, ...)`，根据 Think JSON 中的 `tool_name` 和 `tool_params` 调用工具（如果 `needs_tool` 为 `true`），**发送工具调用 log 事件（调用前和调用后）**
   - **Observe**：调用 `_observe_stage(think_json, tool_results, iteration, ...)`，分析工具返回结果，输出 JSON（包含 `observation`、`has_enough_info`、`needs_more`），**发送 Observe log 事件**
   - 收集当前迭代的完整信息到 `all_iterations` 列表（包含 Think JSON、工具调用结果、Observe JSON）
   - 更新 `accumulated_context`（包含 Think JSON 和 Observe JSON）
   - **检查停止条件**：从 Think JSON 中读取 `is_complete`，**只有当 `is_complete` 为 `true` 时才停止循环并生成最终答案**
4. 生成最终答案
5. 返回结果

#### `_think_stage`

- **接收参数**：`iteration`（当前迭代次数）、`user_question`、`accumulated_context`、`observe_json`（上一轮的观察结果，如果有）
- 构建 Think 提示词：包含系统提示词、用户问题、之前的思考过程（最近 2 轮）、观察结果（如果有）
- 提示词要求：必须输出 JSON 格式，包含 `reasoning`、`needs_tool`、`tool_name`、`tool_params`、`is_complete`、`next_action` 字段
- 调用 `run_chain`，使用流式输出
- 包装 `on_sse_event`，为 `partial` 事件添加 `react_iteration` 和 `react_step="think"`
- 记录 Token 和耗时
- **解析 JSON 输出**：从模型输出中提取 JSON 对象
  - 如果输出包含 JSON 代码块（```json ... ```），提取其中的 JSON
  - 如果输出直接是 JSON，直接解析
  - 如果解析失败，记录错误并尝试从文本中提取关键信息
- **发送 Think log 事件**：
  ```python
  on_sse_event({
    "type": "react_log",
    "data": {
      "iteration": iteration,
      "step": "think",
      "log_type": "think",
      "message": f"思考：{think_json.get('reasoning', '')}",
      "data": think_json
    }
  })
  ```
- 从 JSON 中读取 `is_complete` 判断是否应该停止（`should_stop`）
- 如果 `observe_has_enough_info` 为 `true` 且 `is_complete` 为 `true`，则 `should_stop = True`
- 发送 `react_step` 事件（`step="think"`）
- **返回**：`think_json`（解析后的 JSON 对象）、`content`（原始输出）、`tokens`、`duration`、`should_stop`

#### `_act_stage`

- **接收参数**：`think_json`（从 `_think_stage` 返回的 JSON 对象）、`iteration`（当前迭代次数）
- **工具触发逻辑**：
  - 从 `think_json` 中读取 `needs_tool`、`tool_name`、`tool_params`
  - 如果 `needs_tool` 为 `true` 且 `tool_name` 不为 `null`，根据 `tool_name` 和 `tool_params` 调用对应工具
  - 如果 `needs_tool` 为 `false`，跳过工具调用

- **工具调用流程**：
  - **发送工具调用前 log**：
    ```python
    on_sse_event({
      "type": "react_log",
      "data": {
        "iteration": iteration,
        "step": "act",
        "log_type": "tool_call",
        "message": f"调用工具：{tool_name}",
        "data": {
          "tool_name": tool_name,
          "tool_params": tool_params
        }
      }
    })
    ```
  - 根据 `tool_name` 选择对应工具函数
  - 使用 `tool_params` 中的参数调用工具
  - 记录工具调用开始时间
  - 处理工具调用结果，记录工具名称、参数、输出、耗时
  - 如果工具调用失败，记录错误信息
  - **发送工具调用后 log**：
    ```python
    on_sse_event({
      "type": "react_log",
      "data": {
        "iteration": iteration,
        "step": "act",
        "log_type": "tool_result",
        "message": f"工具返回结果：{tool_name}",
        "data": {
          "tool_name": tool_name,
          "tool_params": tool_params,
          "result": {
            "success": success,
            "data": result_data if success else None,
            "duration": duration
          },
          "error": error_message if not success else None
        }
      }
    })
    ```

- **不需要工具时**：
  - **发送 Act log**（无工具调用）：
    ```python
    on_sse_event({
      "type": "react_log",
      "data": {
        "iteration": iteration,
        "step": "act",
        "log_type": "act",
        "message": "执行：不需要工具调用",
        "data": {
          "needs_tool": False
        }
      }
    })
    ```
  - 直接返回，不进行工具调用

- 包装 `on_sse_event`，为 `partial` 事件添加 `react_iteration` 和 `react_step="act"`
- 发送 `react_step` 事件（`step="act"`，包含 `tool_calls`）
- **返回**：`tool_results`（工具调用结果列表）、`tool_calls`（工具调用信息列表）

#### `_observe_stage`

- **接收参数**：`think_json`（思考结果 JSON）、`tool_results`（工具调用结果）、`iteration`（当前迭代次数）
- 构建 Observe 提示词：包含思考结果、执行结果、工具调用结果（完整内容）
- 提示词要求：必须输出 JSON 格式，包含 `observation`、`has_enough_info`、`needs_more` 字段
- 调用 `run_chain`，使用流式输出
- 包装 `on_sse_event`，为 `partial` 事件添加 `react_iteration` 和 `react_step="observe"`
- **解析 JSON 输出**：从模型输出中提取 JSON 对象
  - 如果输出包含 JSON 代码块（```json ... ```），提取其中的 JSON
  - 如果输出直接是 JSON，直接解析
  - 如果解析失败，记录错误并尝试从文本中提取关键信息
- **发送 Observe log 事件**：
  ```python
  on_sse_event({
    "type": "react_log",
    "data": {
      "iteration": iteration,
      "step": "observe",
      "log_type": "observe",
      "message": f"观察：{observe_json.get('observation', '')}",
      "data": observe_json
    }
  })
  ```
- 从 JSON 中读取 `has_enough_info` 设置 `observe_has_enough_info` 标志
- 发送 `react_step` 事件（`step="observe"`）
- **返回**：`observe_json`（解析后的 JSON 对象）、`content`（原始输出）、`has_enough_info`

#### `_build_final_answer_prompt`

- **接收参数**：`user_question`、`all_iterations`（所有迭代的完整信息列表）
- 构建最终答案提示词，包含：
  - 用户问题
  - 所有迭代的完整过程（Think、工具调用结果、Observe）
  - **明确要求输出纯文本答案，不要输出 JSON 格式**
  - 如果使用了网络搜索，要求列出参考来源
- **返回**：完整的最终答案提示词字符串

#### 最终答案生成

- 当 `is_complete` 为 `true` 时，停止循环
- 调用 `_build_final_answer_prompt` 构建包含完整上下文的提示词
- 调用 `run_chain`，使用流式输出
- 包装 `on_sse_event`，为 `partial` 事件添加 `react_iteration` 和 `react_step="final"`
- **重要**：最终答案必须是纯文本格式，不能是 JSON
- **返回**：`content`（纯文本答案）

#### `_summarize_tool_results`

- 将工具调用结果转换为简洁摘要（用于后续迭代的上下文）
- 如果是 `web_search`，提取关键信息（标题、URL）
- 如果是 `calculate`，提取计算结果
- 如果是 `get_current_time`，提取时间字符串

### 2.4 ReActService 类（react_service.py）

创建 `src/service/react_service.py`，实现以下方法：

#### `__init__`

- 接收 `session_service` 参数
- 从 `models.json` 读取 `react_agent` 配置
- 创建 `ReActAgent` 实例，传入 `REACT_TOOLS`

#### `process_message`

- **参数**：`session_id`、`user_input`、`on_tool_call`、`on_sse_event`

**流程：**

1. 保存用户消息到历史（`role="user"`, `agent_type="react"`）
2. 获取会话数据和历史记录
3. 构建对话历史（转换为模型需要的格式）
4. 发送 `model_request` 事件（`agent_type="react"`, `agent_class="ReActService"`, `model_name`）
5. 调用 `react_agent.run_react_loop()`
6. 发送 `model_response` 事件（包含 `duration`、`input_tokens`、`output_tokens`、`total_tokens`、`iterations`）
7. 保存 AI 响应到历史（`role="assistant"`, `agent_type="react"`）
8. 更新会话数据（`last_question`、`agent_type="react"`）
9. 返回结果字典

### 2.5 系统提示词（react_agent.md）

创建 `src/prompts/react_agent.md`，包含：

#### 工作流程说明

- **Think**：简洁思考（1-2 句话），分析问题需要什么信息、是否需要工具、当前信息是否足够，判断答案是否完整，确定下一步行动。**必须输出 JSON 格式**。
- **Act**：根据 Think JSON 中的 `tool_name` 和 `tool_params` 调用工具（不再使用关键词匹配）
- **Observe**：观察执行结果，分析工具返回的信息。**必须输出 JSON 格式**。

#### JSON 输出格式要求

**Think 阶段必须输出以下 JSON 格式：**

```json
{
  "reasoning": "思考内容（1-2句话）",
  "needs_tool": true,
  "tool_name": "web_search",
  "tool_params": {
    "query": "搜索内容",
    "max_results": 5
  },
  "is_complete": false,
  "next_action": "需要搜索相关信息"
}
```

**Observe 阶段必须输出以下 JSON 格式：**

```json
{
  "observation": "观察结果分析",
  "has_enough_info": true,
  "needs_more": false
}
```

#### 工具触发机制

- **不再使用关键词匹配**，改为从 Think JSON 中读取 `tool_name` 和 `tool_params`
- 工具名称必须是以下之一：`"web_search"`、`"calculate"`、`"date_calculator"`、`"get_current_time"` 或 `null`
- 工具参数必须符合对应工具的规范

#### 停止条件

- Think JSON 中的 `is_complete` 为 `true`
- 达到最大迭代次数（默认 5 次）
- 无法获取更多信息

#### 注意事项

- **必须严格遵循 JSON 格式**，确保可以正确解析
- 优先使用工具获取外部信息
- 如果使用了 `web_search`，在最终答案中引用参考网站
- 思考过程要简洁明了（1-2 句话）
- 逐步完善答案
- 诚实回答，如果无法获取信息或工具失败，诚实说明

### 2.6 模型配置（models.json）

在 `src/config/models.json` 中添加：

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

### 2.7 API 路由集成（routes.py）

在 `src/api/routes.py` 中：

#### 导入 ReActService

```python
from src.service.react_service import ReActService
```

#### 添加服务实例（懒加载）

- 创建全局变量 `_react_service = None`
- 创建函数 `get_react_service()` 返回服务实例

#### 在 `stream()` 函数中处理 REACT 类型

- 检查 `selected_agent == AgentType.REACT`
- 调用 `get_react_service()` 获取服务
- 调用 `service.process_message()`，传入 `on_sse_event` 回调

#### 在 `sse_event_callback` 中处理 `react_step` 事件

- 检查 `event_type == "react_step"`
- 将事件数据放入 SSE 事件队列
- 确保所有字段都传递：`iteration`、`step`、`description`、`model`、`input_tokens`、`output_tokens`、`total_tokens`、`duration`、`content`、`tool_calls`

#### 在 `sse_event_callback` 中处理 `react_log` 事件

- 检查 `event_type == "react_log"`
- 将事件数据放入 SSE 事件队列
- 确保所有字段都传递：`iteration`、`step`、`log_type`、`message`、`data`
- `log_type` 可能的值：
  - `"think"`：Think 阶段的日志
  - `"act"`：Act 阶段的日志（无工具调用时）
  - `"tool_call"`：工具调用前的日志
  - `"tool_result"`：工具调用后的日志
  - `"observe"`：Observe 阶段的日志

#### 在 `yield_event` 中处理 `react_step` 事件

- 对于 `react_step` 类型，传递所有数据字段（包括 `tool_calls`）
- 确保 `iteration`、`step`、`description`、`model`、`tokens`、`duration`、`content`、`tool_calls` 都正确传递

#### 在 `yield_event` 中处理 `react_log` 事件

- 对于 `react_log` 类型，传递所有数据字段
- 确保 `iteration`、`step`、`log_type`、`message`、`data` 都正确传递
- 格式：`data: {"type": "react_log", "data": {...}}`

#### 在 `partial` 事件处理中

- 检查是否有 `react_iteration` 和 `react_step` 字段
- 如果有，保留这些字段，传递给前端

### 2.8 环境配置

#### 环境变量

- `BOCHA_API_KEY`：博查 API 密钥（用于 `web_search` 工具）

#### 依赖包

在 `pyproject.toml` 中添加：

```toml
requests = "^2.31.0"
```

### 2.9 日志配置

#### 在 `src/main.py` 中配置日志

- 配置根日志记录器
- 配置特定父日志记录器（`resume-agent`、`api`、`service`）
- 确保所有 `logger.info` 语句都能打印

#### 在 `src/utils/logger.py` 中

- 设置 `logger.propagate = True`，确保日志传播到父处理器

## 三、前端实现

### 3.1 HTML 更新（index.html）

#### Agent 选择下拉框

添加选项：

```html
<option value="react">ReAct 模式 (Think-Act-Observe)</option>
```

#### CSS 样式

- `.react-step`：步骤容器基础样式（`margin`、`border-radius`、`padding`、`border-left`、`font-size`、`line-height`、`transition`）
- `.react-step.think`：思考阶段样式（`background-color: #eff6ff`, `border-left-color: #3b82f6`, `color: #1e40af`）
- `.react-step.act`：执行阶段样式（`background-color: #f0fdf4`, `border-left-color: #22c55e`, `color: #166534`）
- `.react-step.observe`：观察阶段样式（`background-color: #fefce8`, `border-left-color: #eab308`, `color: #854d0e`）
- `.react-step-header`：步骤头部样式（`font-weight: 600`, `margin-bottom`, `display: flex`, `align-items: center`, `gap`）
- `.react-step-badge`：轮次徽章样式（`display: inline-block`, `padding`, `border-radius`, `font-size`, `font-weight`, `background-color`）
- `.react-step-stats`：统计信息样式（`font-size`, `color`, `margin-top`, `padding-top`, `border-top`）
- `.react-step-content`：步骤内容样式（`margin-top`, `padding`, `background-color`, `border-radius`, `font-family`, `font-size`, `max-height`, `overflow-y`）
- `.react-output`：输出内容样式（`margin`, `padding`, `background-color`, `border-left`, `border-radius`, `font-size`, `white-space`）
- `.react-tool-calls`：工具调用容器样式（`margin-top`）
- `.react-tool-call-item`：工具调用项样式（`margin-bottom`, `border`, `border-radius`, `overflow`）
- `.react-tool-call-header`：工具调用头部样式（`padding`, `background-color`, `cursor`, `display`, `align-items`, `justify-content`, `user-select`）
- `.react-tool-call-details`：工具调用详情样式（`display: none` 默认折叠, `padding`, `background-color`, `border-top`）
- `.react-tool-expand-icon`：展开图标样式（`transition`, `font-size`, `color`）
- `.react-log`：日志容器基础样式（`margin`, `padding`, `border-radius`, `font-size`, `line-height`, `border-left`）
- `.react-log.think`：思考日志样式（`background-color: #eff6ff`, `border-left-color: #3b82f6`）
- `.react-log.act`：执行日志样式（`background-color: #f0fdf4`, `border-left-color: #22c55e`）
- `.react-log.tool-call`：工具调用日志样式（`background-color: #fef3c7`, `border-left-color: #f59e0b`）
- `.react-log.tool-result`：工具结果日志样式（`background-color: #d1fae5` 成功, `background-color: #fee2e2` 失败, `border-left-color: #10b981` 成功, `border-left-color: #ef4444` 失败）
- `.react-log.observe`：观察日志样式（`background-color: #fefce8`, `border-left-color: #eab308`）
- `.react-log-header`：日志头部样式（`display: flex`, `align-items: center`, `gap`, `font-weight: 600`, `margin-bottom`）
- `.react-log-badge`：日志轮次徽章样式（`display: inline-block`, `padding`, `border-radius`, `font-size`, `font-weight`, `background-color`）
- `.react-log-icon`：日志类型图标样式（`font-size`, `margin-right`）
- `.react-log-message`：日志消息样式（`flex: 1`）
- `.react-log-data`：日志数据容器样式（`margin-top`, `padding`, `background-color`, `border-radius`, `display: none` 默认折叠）
- `.react-log-data.expanded`：展开的日志数据样式（`display: block`）
- `.react-log-data pre`：JSON 数据显示样式（`margin: 0`, `font-family: monospace`, `font-size`, `overflow-x: auto`）

### 3.2 JavaScript 配置（config.js）

在 `static/js/config.js` 的 `CONFIG.AGENT_NAMES` 中添加：

```javascript
react: 'ReAct 模式'
```

### 3.3 JavaScript 事件处理（chat.js）

#### `handleSSEEvent` 函数中处理 `react_step` 事件

1. 检查 `data.type === 'react_step'`
2. 检查是否是 ReAct 模式（`appState.currentAgentType === 'react'`）
3. 创建步骤显示元素（`stepDiv`）
4. 设置步骤图标和名称映射：
   - `think`: 💭 思考
   - `act`: ⚡ 执行
   - `observe`: 👁️ 观察
5. 创建头部：显示轮次徽章、步骤图标和名称、描述
6. 添加统计信息：模型、耗时、Token（输入、输出、总计）
7. 添加内容（如果有）
8. 添加工具调用信息（如果有 `tool_calls`）：
   - 为每个工具调用创建可折叠的详情项
   - 显示工具名称、参数（JSON 格式）、输出结果（JSON 格式）、耗时
   - 点击头部展开/折叠详情
9. 添加到聊天容器

#### `handleSSEEvent` 函数中处理 `react_log` 事件

1. 检查 `data.type === 'react_log'`
2. 检查是否是 ReAct 模式（`appState.currentAgentType === 'react'`）
3. 获取 log 数据：`iteration`、`step`、`log_type`、`message`、`data`
4. 根据 `log_type` 创建不同类型的日志显示：
   - **`think`**：创建思考日志项，显示思考内容
   - **`act`**：创建执行日志项（无工具调用时）
   - **`tool_call`**：创建工具调用日志项，显示工具名称和参数
   - **`tool_result`**：创建工具结果日志项，显示工具返回结果
   - **`observe`**：创建观察日志项，显示观察结果
5. 日志显示格式：
   - 显示轮次徽章：`第 ${iteration} 轮`
   - 显示步骤标识：`[${step.toUpperCase()}]`
   - 显示日志类型图标：
     - `think`: 💭
     - `act`: ⚡
     - `tool_call`: 🔧
     - `tool_result`: ✅ 或 ❌（根据 success）
     - `observe`: 👁️
   - 显示消息：`message` 字段
   - 显示结构化数据（可折叠）：
     - 对于 `tool_call`：显示 `tool_name` 和 `tool_params`
     - 对于 `tool_result`：显示 `tool_name`、`tool_params`、`result`（包含 success、data、duration）、`error`（如果有）
     - 对于 `think` 和 `observe`：显示完整的 JSON 数据
6. 添加到聊天容器（按时间顺序，与 `react_step` 事件混合显示）

#### `handleSSEEvent` 函数中处理 `partial` 事件（ReAct 模式）

1. 检查是否是 ReAct 模式
2. 获取 `react_iteration` 和 `react_step`
3. 根据 `iteration` 和 `step` 创建唯一的输出块 ID：`react-output-${reactIteration}-${reactStep}`
4. 如果输出块不存在，创建新的输出块：
   - 创建 `outputDiv`，设置 `className` 为 `'react-output'`
   - 添加步骤标识头部：显示轮次徽章和步骤名称（💭 思考输出、⚡ 执行输出、👁️ 观察输出、📝 最终答案）
   - 创建内容容器（`contentSpan`），设置 `white-space: pre-wrap`
5. 更新输出内容：将 `currentContent` 设置到 `contentSpan`
6. 添加到聊天容器

#### `handleSSEEvent` 函数中处理 `final` 事件（ReAct 模式）

1. 检查是否是 ReAct 模式
2. 如果有 `react_iteration` 和 `react_step`，使用与 `partial` 相同的逻辑创建输出块
3. 否则使用原有逻辑

#### 确保事件顺序

- `react_step` 事件和 `partial` 事件会交替出现
- 前端需要能够处理这种混合显示
- 日志信息（`react_step`）和输出内容（`partial`）应该混合显示，方便查看逻辑

## 四、关键实现细节

### 4.1 流式模式与工具调用的兼容性

- 某些模型提供者不支持在流式模式下使用工具
- 在 `BaseAgent.run_chain()` 中检测错误
- 当检测到 "Tools are not supported in streaming mode" 错误时，自动切换到非流式模式（`ainvoke`）进行工具调用
- 工具调用完成后继续流式输出

### 4.2 Token 统计

- 每个步骤的 Token 使用情况单独统计
- 最终汇总所有步骤的 Token 使用
- 在 `model_response` 事件中返回总 Token 和迭代次数

### 4.3 停止条件

- **答案完整**：Think 阶段判断答案已完整
- **达到最大迭代次数**：默认 5 次，可在配置中调整
- **提前停止**：如果 Observe 阶段判断信息足够，且 Think 阶段未明确要求继续，则提前停止

### 4.4 上下文管理

- 使用 `accumulated_context` 存储每轮迭代的摘要
- 在后续迭代中，只包含最近 2-3 轮的上下文，避免 Token 浪费
- 工具调用结果使用摘要形式存储，完整结果只在 Observe 阶段使用

### 4.5 工具调用信息传递

- 在 Act 阶段记录工具调用信息：工具名称、参数、输出、耗时
- 通过 `react_step` 事件的 `tool_calls` 字段传递到前端
- 前端以可折叠形式显示工具调用详情

### 4.6 JSON 解析和错误处理

#### JSON 解析策略

1. **优先解析 JSON 代码块**：
   - 如果输出包含 ````json ... ``` ` 代码块，提取其中的 JSON
   - 使用正则表达式匹配代码块内容

2. **直接解析 JSON**：
   - 如果输出直接是 JSON 对象（以 `{` 开头），直接解析

3. **容错处理**：
   - 如果解析失败，尝试提取关键字段（使用正则表达式）
   - 记录警告日志，但继续执行流程
   - 如果完全无法解析，使用默认值：
     - `needs_tool`: `false`
     - `tool_name`: `null`
     - `is_complete`: `false`（保守策略，继续循环）

#### 常见 JSON 错误

- **缺少引号**：`{reasoning: "内容"}` → 应使用双引号
- **缺少逗号**：`{"field1": "value1" "field2": "value2"}` → 字段间需要逗号
- **布尔值用字符串**：`{"is_complete": "true"}` → 应使用 `true`（不带引号）
- **工具名拼写错误**：`{"tool_name": "websearch"}` → 应为 `"web_search"`
- **参数名不匹配**：`web_search` 使用 `search_query` → 应为 `query`

#### 边界情况处理

1. **工具调用失败**：
   - 记录错误信息到 `tool_results`
   - 在下一轮 Think 中，模型应该能够识别错误并调整策略

2. **信息不完整需要多轮搜索**：
   - 通过 `observe_json` 中的 `needs_more` 标志控制
   - 在下一轮 Think 中，模型应该根据 `needs_more` 决定是否继续搜索

3. **达到最大迭代次数**：
   - 强制设置 `is_complete = true`
   - 基于现有信息生成最终答案

4. **JSON 格式错误但能提取关键信息**：
   - 使用提取的信息继续流程
   - 记录警告日志，提醒优化提示词

## 五、测试要点

### 5.1 基本功能测试

- 简单问题（不需要工具，`needs_tool` 为 `false`）
- 需要计算的问题（`tool_name` 为 `"calculate"`）
- 需要网络搜索的问题（`tool_name` 为 `"web_search"`）
- 需要当前时间的问题（`tool_name` 为 `"get_current_time"`）
- 需要日期计算的问题（`tool_name` 为 `"date_calculator"`）

### 5.1.1 JSON 格式测试

- 验证 Think 阶段输出的 JSON 格式正确性
- 验证 Observe 阶段输出的 JSON 格式正确性
- 验证 JSON 解析错误处理（格式错误、缺少字段、类型错误）
- 验证工具参数格式正确性
- 验证边界情况（`needs_tool` 为 `false` 时 `tool_name` 为 `null`）

### 5.2 循环测试

- 验证循环是否正常执行
- 验证停止条件是否生效
- 验证提前停止是否工作

### 5.3 前端显示测试

- 验证不同阶段的颜色区分
- 验证轮次和阶段信息显示
- 验证工具调用信息显示
- 验证输出内容是否正确分散到不同步骤
- 验证 `react_log` 事件正确显示
- 验证工具调用的 log 事件（调用前和调用后）正确显示
- 验证日志数据的折叠/展开功能

### 5.4 SSE 事件测试

- 验证所有事件类型都正确发送（`react_step`、`react_log`、`partial`、`final`）
- 验证事件数据完整性
- 验证流式输出是否正常
- 验证 `react_log` 事件格式正确性
- 验证工具调用的 log 事件（`tool_call` 和 `tool_result`）是否正确发送

### 5.5 错误处理测试

- 工具调用失败
- 网络请求失败
- API 密钥缺失
- JSON 解析失败（格式错误、缺少字段）
- 工具参数不匹配
- 工具名称拼写错误

## 六、部署检查清单

- [ ] 后端文件创建完成（`react_agent.py`、`react_service.py`、`react_tools.py`、`react_agent.md`）
- [ ] `AgentType` 枚举添加 `REACT`
- [ ] `models.json` 添加 `react_agent` 配置
- [ ] API 路由集成完成
- [ ] 环境变量配置（`BOCHA_API_KEY`）
- [ ] 依赖包安装（`requests`）
- [ ] 日志配置正确
- [ ] 前端 HTML 更新（Agent 选择、CSS 样式）
- [ ] 前端 JavaScript 更新（事件处理、配置）
- [ ] 测试所有功能
- [ ] 验证前端显示效果

## 七、常见问题

### 7.1 前端显示 "第 undefined 轮"

- 确保 `react_step` 事件包含 `iteration` 字段
- 确保 `yield_event` 正确传递所有字段

### 7.2 JSON 格式错误

- 检查模型输出是否为有效的 JSON 格式
- 检查 JSON 字段名是否正确（`tool_name` 不是 `toolName`）
- 检查布尔值是否正确（`true`/`false` 不是 `"true"`/`"false"`）
- 检查工具参数格式是否匹配工具定义
- 查看日志中的 JSON 解析错误信息

### 7.3 工具未正确触发

- 检查 Think JSON 中的 `needs_tool` 是否为 `true`
- 检查 `tool_name` 是否正确（必须是 `"web_search"`、`"calculate"`、`"date_calculator"`、`"get_current_time"` 之一）
- 检查 `tool_params` 格式是否正确
- 检查工具参数名是否匹配（如 `web_search` 使用 `query` 不是 `search_query`）

### 7.4 模型一直调用 `get_current_time`

- 检查提示词是否正确强调 `web_search` 的优先级
- 检查 Think JSON 中的工具选择逻辑

### 7.5 工具调用失败

- 检查环境变量 `BOCHA_API_KEY` 是否设置
- 检查网络连接
- 查看日志中的错误信息
- 检查工具参数是否正确传递

### 7.6 循环不停止

- 检查 Think JSON 中的 `is_complete` 字段是否正确设置为 `true`
- 检查停止条件判断逻辑
- 检查 Think 阶段的提示词（是否包含判断答案完整性的要求）
- 检查 `observe_has_enough_info` 标志是否正确设置

### 7.7 前端不显示工具调用信息

- 确保 `tool_calls` 字段正确传递
- 检查前端 JavaScript 是否正确处理 `tool_calls`
- 检查工具调用信息的格式是否正确

## 八、总结

该实现包含：

- 完整的 Think-Act-Observe 循环（Think 阶段包含答案完整性判断）
- **JSON 格式数据传递**：各阶段通过结构化 JSON 传递信息，确保准确解析
- **参数化工具触发**：通过 JSON 参数指定工具，不再使用关键词匹配
- **独立的 log 事件传输**：每个步骤（Think、Act、Observe）都有独立的 log 事件传输到页面
- **工具调用详细日志**：工具调用前（`tool_call`）和调用后（`tool_result`）都有独立的 log 事件，包含工具名称、参数、返回结果、耗时、错误信息
- 网络搜索、计算、日期计算、时间获取等工具
- 流式输出和实时反馈
- 前端可视化（阶段颜色区分、轮次显示、工具调用详情、日志显示）
- 兼容现有 Agent 服务框架
- 提前停止机制
- 完整的错误处理和日志记录（包括 JSON 解析错误处理）
- **大量边界情况处理示例**：工具调用失败、信息不完整、JSON 格式错误等

该模式适合需要查询最新信息、进行复杂推理或需要多步骤处理的问题。
