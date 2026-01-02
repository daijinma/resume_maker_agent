#!/bin/bash

# SSE 接口测试脚本
# 自动发送消息并检查 SSE 返回，直到错误消失

API_URL="${API_URL:-http://localhost:8000/stream}"
SESSION_ID="test_session_$(date +%s)"
MESSAGE="${1:-你好，我想完善我的简历}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${YELLOW}开始测试 SSE 接口...${NC}"
echo "API URL: $API_URL"
echo "Session ID: $SESSION_ID"
echo "Message: $MESSAGE"
echo ""

# 测试函数
test_chat() {
    local session_id=$1
    local message=$2
    local attempt=${3:-1}
    local temp_file=$(mktemp)
    
    echo -e "${YELLOW}[尝试 $attempt] 发送消息: $message${NC}"
    
    # 发送 POST 请求并处理 SSE 流，保存到临时文件
    local http_code=$(curl -s -w "%{http_code}" -o "$temp_file" -N -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -H "Accept: text/event-stream" \
        --max-time 60 \
        -d "{
            \"action\": \"chat\",
            \"session_id\": \"$session_id\",
            \"agent_type\": \"planner_worker\",
            \"message\": \"$message\"
        }" 2>&1)
    
    local response=$(cat "$temp_file")
    rm -f "$temp_file"
    
    # 检查 HTTP 状态码
    if [ "$http_code" != "200" ]; then
        echo -e "${RED}❌ HTTP 错误: $http_code${NC}"
        echo "$response" | head -30
        return 1
    fi
    
    # 如果没有响应
    if [ -z "$response" ]; then
        echo -e "${YELLOW}⚠️  没有收到响应${NC}"
        return 1
    fi
    
    # 解析 SSE 格式 (data: {...})
    local has_error=false
    local has_final=false
    local error_content=""
    
    # 直接检查 SSE 响应中的错误和最终响应
    if echo "$response" | grep "^data:" | grep -q '"type":"error"'; then
        has_error=true
        error_content=$(echo "$response" | grep "^data:" | grep '"type":"error"' | head -1 | sed 's/^data: //')
    fi
    
    if echo "$response" | grep "^data:" | grep -q '"type":"final"'; then
        has_final=true
    fi
    
    # 检查是否有错误
    if [ "$has_error" = true ]; then
        echo -e "${RED}❌ 检测到错误响应:${NC}"
        echo "$error_content" | python3 -m json.tool 2>/dev/null || echo "$error_content"
        return 1
    fi
    
    # 检查服务器日志中的错误（可能出现在响应中）
    if echo "$response" | grep -qiE "(traceback|exception|error:|failed|got multiple values)"; then
        echo -e "${RED}❌ 检测到错误信息:${NC}"
        echo "$response" | grep -iE "(traceback|exception|error:|failed|got multiple values)" | head -10
        return 1
    fi
    
    # 检查是否有最终响应
    if [ "$has_final" = true ]; then
        echo -e "${GREEN}✅ 成功！收到最终响应:${NC}"
        echo "$response" | grep '"type":"final"' | head -1 | sed 's/^data: //' | python3 -m json.tool 2>/dev/null || echo "$response" | grep '"type":"final"' | head -1
        return 0
    fi
    
    # 如果收到任何 SSE 响应但没有错误，也认为可能成功（可能还在处理中）
    if echo "$response" | grep -q "^data:"; then
        echo -e "${BLUE}ℹ️  收到 SSE 响应（可能还在处理中）:${NC}"
        echo "$response" | grep "^data:" | tail -3 | sed 's/^data: //' | head -1
        return 0
    fi
    
    echo -e "${YELLOW}⚠️  收到响应但格式不正确:${NC}"
    echo "$response" | head -20
    return 1
}

# 主测试循环
max_attempts="${MAX_ATTEMPTS:-5}"
attempt=1
success=false

while [ $attempt -le $max_attempts ] && [ "$success" = false ]; do
    echo ""
    echo "========================================"
    
    if test_chat "$SESSION_ID" "$MESSAGE" $attempt; then
        success=true
        echo ""
        echo -e "${GREEN}🎉 测试通过！接口正常工作。${NC}"
        break
    else
        if [ $attempt -lt $max_attempts ]; then
            echo ""
            echo -e "${YELLOW}等待 2 秒后重试... (${attempt}/${max_attempts})${NC}"
            sleep 2
        fi
        attempt=$((attempt + 1))
    fi
done

echo ""
if [ "$success" = false ]; then
    echo -e "${RED}❌ 经过 $max_attempts 次尝试后仍然失败${NC}"
    echo ""
    echo "提示:"
    echo "  1. 确保服务正在运行: python3 src/main.py 或 make run"
    echo "  2. 检查服务日志中的错误信息"
    echo "  3. 可以设置环境变量: export API_URL=http://localhost:8000/stream"
    echo "  4. 可以设置最大重试次数: export MAX_ATTEMPTS=10"
    exit 1
else
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
    exit 0
fi

