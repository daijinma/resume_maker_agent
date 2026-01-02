# SSE 接口测试脚本使用说明

## 脚本说明

`test_sse_curl.sh` 是一个用于测试 SSE (Server-Sent Events) 接口的 bash 脚本。它会自动发送消息到 `/stream` 端点，并检查响应直到错误消失或达到最大重试次数。

## 使用方法

### 基本用法

```bash
# 使用默认消息测试
./scripts/test_sse_curl.sh

# 使用自定义消息测试
./scripts/test_sse_curl.sh "你好，我想了解你的功能"
```

### 环境变量配置

```bash
# 设置 API URL（默认为 http://localhost:8000/stream）
export API_URL=http://localhost:8000/stream

# 设置最大重试次数（默认为 5）
export MAX_ATTEMPTS=10

# 运行测试
./scripts/test_sse_curl.sh
```

## 功能特点

1. **自动重试**: 如果检测到错误，会自动重试（默认最多 5 次）
2. **错误检测**: 自动检测以下错误类型：
   - HTTP 状态码错误
   - SSE 响应中的 `"type":"error"` 错误
   - Python traceback 和异常信息
   - 其他常见错误关键词
3. **SSE 解析**: 正确解析 SSE 格式的响应（`data: {...}`）
4. **彩色输出**: 使用颜色区分成功、错误和警告信息
5. **JSON 格式化**: 自动格式化 JSON 响应以便阅读

## 输出说明

- ✅ **绿色**: 成功响应
- ❌ **红色**: 错误信息
- ⚠️ **黄色**: 警告信息
- ℹ️ **蓝色**: 信息提示

## 示例输出

```
开始测试 SSE 接口...
API URL: http://localhost:8000/stream
Session ID: test_session_1234567890
Message: 你好，我想完善我的简历

========================================
[尝试 1] 发送消息: 你好，我想完善我的简历
✅ 成功！收到最终响应:
{
  "type": "final",
  "content": "好的，我来帮你完善简历...",
  "session_id": "test_session_1234567890"
}

🎉 测试通过！接口正常工作。
✅ 所有测试通过！
```

## 故障排除

如果测试失败，请检查：

1. **服务是否运行**: 确保服务正在运行
   ```bash
   # 检查服务状态
   curl http://localhost:8000/
   ```

2. **端口是否正确**: 默认端口是 8000，如果不同请设置 `API_URL`

3. **查看服务日志**: 检查服务器端的错误日志

4. **增加重试次数**: 如果网络不稳定，可以增加 `MAX_ATTEMPTS`

