# Agent 選擇功能使用指南

## 概述

現在系統支持兩種 Agent 架構，可以通過前端選擇器或 API 參數進行切換：

1. **經典架構 (Classic)** - 原有的架構，使用 JSON 文件存儲
2. **雙軌架構 (Dual Track)** - 新的架構，使用 PostgreSQL，支持異步推理

## 前端使用

### 頁面選擇器

在頁面右上角有一個下拉選擇器，可以選擇使用的 Agent 類型：

- **經典架構 (Classic)**: 使用流式響應，適合快速測試
- **雙軌架構 (Dual Track)**: 使用異步推理，適合生產環境

### 使用方式

1. 打開頁面 `http://localhost:8000`
2. 在右上角選擇 Agent 類型
3. 發送消息，系統會使用選中的 Agent 處理

## API 使用

### POST /chat

**請求示例：**

```bash
# 使用經典架構
curl -X POST "http://localhost:8000/chat?agent_type=classic" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我想寫一份簡歷",
    "session_id": "test_session"
  }'

# 使用雙軌架構
curl -X POST "http://localhost:8000/chat?agent_type=dual_track" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我想寫一份簡歷",
    "session_id": "test_session"
  }'
```

**或者在請求體中指定：**

```json
{
  "message": "我想寫一份簡歷",
  "session_id": "test_session",
  "agent_type": "dual_track"
}
```

### GET /chat/stream

**請求示例：**

```bash
# 經典架構（支持流式響應）
curl "http://localhost:8000/chat/stream?message=我想寫一份簡歷&session_id=test_session&agent_type=classic"

# 雙軌架構（目前不支持流式響應，會返回提示）
curl "http://localhost:8000/chat/stream?message=我想寫一份簡歷&session_id=test_session&agent_type=dual_track"
```

## 兩種架構的區別

| 特性 | 經典架構 | 雙軌架構 |
|------|---------|---------|
| 存儲方式 | JSON 文件 | PostgreSQL |
| 推理方式 | 同步執行 | 異步執行 |
| 響應速度 | 中等 | 快速（小模型響應） |
| 問題管理 | 簡單列表 | 結構化佇列 |
| 流式響應 | ✅ 支持 | ❌ 暫不支持 |
| 背景推理 | ❌ 不支持 | ✅ 支持 |
| 數據持久化 | 文件系統 | 數據庫 |

## 響應格式

### 經典架構響應

```json
{
  "status": "success",
  "response": "AI 響應內容",
  "session_id": "test_session",
  "pending_questions": ["問題1", "問題2"],
  "agent_type": "classic",
  "debug": {
    "intents": ["info", "experience"],
    "duration": "2.5s"
  }
}
```

### 雙軌架構響應

```json
{
  "status": "success",
  "response": "AI 響應內容",
  "session_id": "test_session",
  "pending_questions": ["問題1", "問題2"],
  "agent_type": "dual_track",
  "debug": {
    "intents": ["info", "experience"],
    "questions_count": 2,
    "background_reasoning_status": "completed"
  }
}
```

## 查詢推理狀態（僅雙軌架構）

```bash
curl "http://localhost:8000/dual-track/reasoning-status/test_session"
```

**響應示例：**

```json
{
  "session_id": "test_session",
  "background_reasoning_status": "completed",
  "last_reasoning_time": "2025-01-23T10:30:00",
  "pending_questions_count": 3,
  "pending_questions": [
    {
      "id": "q_001",
      "content": "請提供您的姓名",
      "priority": 1,
      "field": "name"
    }
  ],
  "inference_insights": ["分析結果1", "分析結果2"]
}
```

## 注意事項

1. **數據庫設置**：使用雙軌架構前，需要先啟動 PostgreSQL：
   ```bash
   make db-up
   make db-init
   ```

2. **會話隔離**：兩種架構使用不同的存儲方式，會話數據不共享

3. **性能考慮**：
   - 經典架構：適合快速測試和開發
   - 雙軌架構：適合生產環境，響應更快，支持異步推理

4. **流式響應**：目前只有經典架構支持流式響應，雙軌架構使用普通 POST 請求

## 開發建議

- **開發階段**：使用經典架構進行快速迭代
- **生產環境**：使用雙軌架構獲得更好的性能和可擴展性
- **測試對比**：可以同時使用兩種架構，對比響應質量和速度

