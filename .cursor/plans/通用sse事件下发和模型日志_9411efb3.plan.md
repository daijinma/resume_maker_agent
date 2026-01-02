---
name: 通用SSE事件下发和模型日志
overview: 修改多个agent的处理流程，使其支持通用的SSE数据下发，并增加模型请求和模型切换的下发日志。通过统一的SSE事件回调机制，在routes.py中创建回调并传递到所有agent，实现模型请求开始、模型切换、模型响应完成等事件的实时下发。
todos:
  - id: modify_base_agent
    content: 修改BaseAgent类，增加on_sse_event回调参数，实现模型请求、切换、响应完成事件的发送
    status: completed
  - id: modify_router
    content: 修改Router类，在route方法中增加on_sse_event参数并传递给run_chain
    status: completed
    dependencies:
      - modify_base_agent
  - id: modify_workers
    content: 修改InfoWorker、ExperienceWorker、SkillWorker，在process方法中增加on_sse_event参数
    status: completed
    dependencies:
      - modify_base_agent
  - id: modify_aggregator
    content: 修改Aggregator类，在aggregate方法中增加on_sse_event参数并传递给run_chain
    status: completed
    dependencies:
      - modify_base_agent
  - id: modify_dual_track_service
    content: 修改DualTrackService，在process_message和相关方法中传递on_sse_event回调
    status: completed
    dependencies:
      - modify_router
      - modify_workers
      - modify_aggregator
  - id: modify_planner_worker_service
    content: 修改PlannerWorkerService，在process_message和相关方法中传递on_sse_event回调
    status: completed
    dependencies:
      - modify_router
      - modify_workers
      - modify_aggregator
  - id: modify_routes
    content: 修改routes.py，创建SSE事件回调并传递给service，实时处理并yield SSE事件
    status: completed
    dependencies:
      - modify_dual_track_service
      - modify_planner_worker_service
---

# 通用SSE事件下发和模型日志增强

## 目标

1. 修改现有多个agent的处理流程，使其支持通用的SSE数据下发
2. 增加模型发出请求、模型切换的下发日志
3. 统一SSE事件回调机制，便于扩展和维护

## 架构设计

### SSE事件类型

- `model_request`: 模型请求开始（包含模型名称、agent类型、输入摘要）
- `model_switch`: 模型切换（包含旧模型、新模型、切换原因）
- `model_response`: 模型响应完成（包含耗时、token使用情况）

### 数据流

```
routes.py (创建SSE回调)
  ↓
service (dual_track_service/planner_worker_service)
  ↓
agent (Router/InfoWorker/ExperienceWorker/SkillWorker/Aggregator)
  ↓
BaseAgent.run_chain (发送SSE事件)
```

## 实现步骤

### 1. 修改 BaseAgent 类 (`src/agents/base.py`)

#### 1.1 增加 SSE 事件回调参数

- 在 `run_chain` 方法中增加 `on_sse_event: Optional[Callable] = None` 参数
- 回调函数签名: `async def on_sse_event(event_type: str, data: dict)`

#### 1.2 发送模型请求开始事件

- 在 `run_chain` 方法开始处（调用LLM之前）发送 `model_request` 事件
- 事件数据包含:
  - `agent_type`: agent类型（通过 `_get_agent_type()` 获取）
  - `agent_class`: agent类名
  - `model_name`: 当前使用的模型名称
  - `input_preview`: 输入内容预览（前200字符）

#### 1.3 发送模型切换事件

- 在 `_switch_to_next_model` 方法中，切换成功后发送 `model_switch` 事件
- 事件数据包含:
  - `old_model`: 旧模型名称
  - `new_model`: 新模型名称
  - `reason`: 切换原因（如 "rate_limit_error"）
  - `agent_type`: agent类型

#### 1.4 发送模型响应完成事件

- 在 `run_chain` 方法结束前（返回结果前）发送 `model_response` 事件
- 事件数据包含:
  - `agent_type`: agent类型
  - `agent_class`: agent类名
  - `model_name`: 使用的模型名称
  - `duration`: 执行耗时（从 `self.last_duration` 获取）
  - `input_tokens`: 输入token数
  - `output_tokens`: 输出token数
  - `total_tokens`: 总token数

#### 1.5 传递回调到内部调用

- 在 `_invoke_with_retry` 方法中，如果发生模型切换，触发 `model_switch` 事件
- 确保回调能够访问到 `on_sse_event`（通过闭包或实例变量）

### 2. 修改所有 Agent 子类

#### 2.1 Router (`src/agents/router.py`)

- 在 `route` 方法中增加 `on_sse_event` 参数
- 传递给 `run_chain` 方法

#### 2.2 InfoWorker (`src/agents/info_worker.py`)

- 在 `process` 方法中增加 `on_sse_event` 参数
- 传递给 `run_chain` 方法

#### 2.3 ExperienceWorker (`src/agents/experience_worker.py`)

- 在 `process` 方法中增加 `on_sse_event` 参数
- 传递给 `run_chain` 方法

#### 2.4 SkillWorker (`src/agents/skill_worker.py`)

- 在 `process` 方法中增加 `on_sse_event` 参数
- 传递给 `run_chain` 方法

#### 2.5 Aggregator (`src/agents/aggregator.py`)

- 在 `aggregate` 方法中增加 `on_sse_event` 参数
- 传递给 `run_chain` 方法

### 3. 修改 Service 层

#### 3.1 DualTrackService (`src/service/dual_track_service.py`)

- 在 `process_message` 方法中增加 `on_sse_event` 参数
- 传递给:
  - `router.route()` 方法
  - `_run_workers()` 方法（再传递给各个worker）
  - `_fast_response()` 方法（传递给快速响应agent）
  - `_get_response_wi

  - `_get_response_withth_questions()` 方法（传递给aggregator）

- 在 `_run_workers` 方法中，将 `on_sse_event` 传递给各个worker的 `process` 方法

#### 3.2 PlannerWorkerService (`src/service/planner_worker_service.py`)

- 在 `process_message` 方法中增加 `on_sse_event` 参数
- 传递给:

  - `router.route()` 方法

  - `_run_workers()` 方法

  - `aggregator.aggregate()` 方法
  - 其他调用agent的地方

### 4. 修改 API 路由层 (`src/api/routes.py`)

#### 4.1 创建统一的 SSE 事件回调

- 在 `stream` 函数的 `event_generator` 中，创建 `sse_event_queue`（类似 `tool_events_queue`）

- 创建 `sse_event_callback` 函数，将事件放入队列

- 在后台任务运行期间，实时处理队列中的SSE事件并yield

#### 4.2 传递回调到 Service

- 将 `sse_event_callback` 传递给 `service.process_message()` 方法

- 确保回调能够正确处理所有事件类型

#### 4.3 SSE 事件格式

- `model_request`: `{"type": "status", "content": "🤖 [Router] 正在使用模型 xxx 处理请求...", "debug": {"agent": "router", "model": "xxx", "event": "model_request"}}`

- `model_switch`: `{"type": "status", "content": "🔄 模型切换: xxx → yyy (原因: rate_limit)", "debug": {"agent": "router", "old_model": "xxx", "new_model": "yyy", "reason": "rate_limit", "event": "model_switch"}}`

- `model_response`: `{"type": "status", "content": "✅ [Router] 处理完成 (耗时: 2.3s, tokens: 150/200)", "debug": {"agent": "router", "model": "xxx", "duration": 2.3, "tokens": {"input": 150, "output": 200}, "event": "model_response"}}`

## 技术细节

### 回调函数设计

```python
async def sse_event_callback(event_type: str, data: dict):
    """SSE事件回调
    Args:
        event_type: 事件类型 ("model_request", "model_switch", "model_response")
        data: 事件数据字典
    """
    await sse_event_queue.put({
        "type": "status",  # 统一使用status类型
        "content": format_event_content(event_type, data),
        "debug": {
            "event": event_type,
            **data
        }
    })
```



### 事件内容格式化

- `model_request`: 显示agent类型和模型名称

- `model_switch`: 显示切换前后的模型和原因

- `model_response`: 显示耗时和token使用情况

### 向后兼容

- 所有新增参数都设置为可选（`Optional`），默认值为 `None`

- 如果 `on_sse_event` 为 `None`，则不发送事件（不影响现有功能）

## 测试要点

1. 验证所有agent都能正确发送SSE事件
2. 验证模型切换时能正确发送切换事件
3. 验证事件格式符合前端预期