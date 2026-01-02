# 重构后功能测试指南

## 概述

本文档描述了如何测试重构后的统一 SSE 流式接口，确保两种 agent 类型（`planner_worker` 和 `dual_track`）都能正常工作。

## 前置条件

1. **启动数据库**（如果使用 dual_track）：
   ```bash
   make db-up
   make db-init
   ```

2. **启动服务器**：
   ```bash
   make dev
   ```

3. **验证服务器运行**：
   ```bash
   curl http://localhost:8000/
   ```

## 测试方法

### 方法 1: 使用自动化测试脚本（推荐）

运行综合测试脚本，自动测试所有功能：

```bash
# 使用虚拟环境中的 Python
.venv/bin/python scripts/test_refactored_functionality.py

# 或使用 uv
PYTHONPATH=. uv run python scripts/test_refactored_functionality.py
```

测试脚本会验证：
- ✅ planner_worker agent 的 chat 功能
- ✅ dual_track agent 的 chat 功能
- ✅ history 历史记录获取
- ✅ token_stats token 统计
- ✅ reasoning_status 推理状态（dual_track 特有）

### 方法 2: 使用前端 UI

1. 打开浏览器访问：`http://localhost:8000/`
2. 在 UI 中选择不同的 agent 类型（planner_worker 或 dual_track）
3. 发送测试消息，观察 SSE 流式输出
4. 检查历史记录和 token 统计功能

### 方法 3: 使用 curl 手动测试

#### 测试 planner_worker chat

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "action": "chat",
    "message": "你好，我是张三，36岁，毕业于北京大学计算机科学专业",
    "session_id": "test_session_pw",
    "agent_type": "planner_worker"
  }'
```

#### 测试 dual_track chat

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "action": "chat",
    "message": "你好，我是李四，30岁，有5年软件工程师经验",
    "session_id": "test_session_dt",
    "agent_type": "dual_track"
  }'
```

#### 测试 history

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "action": "history",
    "session_id": "test_session_pw",
    "limit": 10
  }'
```

#### 测试 token_stats

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "action": "token_stats",
    "session_id": "test_session_pw"
  }'
```

#### 测试 reasoning_status（仅 dual_track）

```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "action": "reasoning_status",
    "session_id": "test_session_dt",
    "agent_type": "dual_track"
  }'
```

## 验证点

### 1. SSE 流式输出格式

每个 SSE 事件应该符合以下格式：

```
data: {"type": "status|partial|final|error", "content": "...", ...}
```

事件类型：
- `status`: 状态更新（如工具调用、处理进度）
- `partial`: 部分响应内容（流式输出）
- `final`: 最终完整响应
- `error`: 错误信息

### 2. planner_worker 验证

- ✅ 能够正常处理聊天消息
- ✅ 返回正确的响应格式
- ✅ 工具调用状态正确显示
- ✅ 历史记录可以正常获取
- ✅ token 统计可以正常获取

### 3. dual_track 验证

- ✅ 能够正常处理聊天消息
- ✅ 返回正确的响应格式（包含 `pending_questions`）
- ✅ 工具调用状态正确显示
- ✅ 历史记录可以正常获取
- ✅ token 统计可以正常获取
- ✅ `reasoning_status` 可以正常获取

### 4. 错误处理

- ✅ 无效的 action 返回错误
- ✅ 缺少必需参数时返回错误
- ✅ 异常情况有适当的错误消息

### 5. 向后兼容性

- ✅ 旧的 API 端点返回废弃提示
- ✅ 提示信息包含新接口的使用示例

## 常见问题排查

### 问题 1: 服务器无法启动

**症状**: `make dev` 失败

**解决方案**:
1. 检查端口 8000 是否被占用：`lsof -ti:8000`
2. 检查依赖是否安装：`make sync`
3. 检查环境变量：确保 `.env` 文件存在且包含 `OPENROUTER_API_KEY`

### 问题 2: dual_track 报错需要数据库

**症状**: `Dual-Track 服务需要数据库支持`

**解决方案**:
1. 启动数据库：`make db-up`
2. 初始化数据库：`make db-init`
3. 检查环境变量：确保 `USE_DATABASE=true`（如果使用 `.env`）

### 问题 3: SSE 流式输出不工作

**症状**: 前端无法接收流式数据

**解决方案**:
1. 检查浏览器控制台是否有错误
2. 验证服务器日志是否有异常
3. 确认使用 `fetch API` 而不是 `EventSource`（因为 POST 请求）

### 问题 4: 工具调用状态不显示

**症状**: 看不到工具调用的实时状态

**解决方案**:
1. 检查 `tool_callback` 是否正确设置
2. 验证 `tool_events_queue` 是否正常工作
3. 查看服务器日志确认工具调用是否触发

## 测试结果示例

成功的测试应该看到类似以下输出：

```
======================================================================
  开始测试重构后的功能
======================================================================

ℹ 检查服务器状态...
✓ 服务器运行正常

======================================================================
  测试 1: planner_worker - chat
======================================================================
ℹ 发送请求: {
  "action": "chat",
  "message": "你好，我是张三...",
  "session_id": "test_xxx_pw",
  "agent_type": "planner_worker"
}
✓ 开始接收 SSE 流 (状态码: 200)
[状态] 开始处理 chat 操作...
[状态] 🔍 正在分析您的意图...
[状态] [planner] 正在调用工具: extract_intent
[部分] 根据您提供的信息...
[完成] 我已经了解了您的基本信息...
✓ 测试完成 (耗时: 5.23秒)
ℹ 收到事件统计: {
  "status": 3,
  "partial": 5,
  "final": 1
}
```

## 下一步

测试通过后，可以：
1. 进行性能测试
2. 进行压力测试
3. 集成到 CI/CD 流程
4. 编写单元测试

