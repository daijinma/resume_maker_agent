#!/bin/bash
# 初始化數據庫腳本

set -e

echo "正在啟動 PostgreSQL 容器..."
docker-compose up -d postgres

echo "等待數據庫就緒..."
sleep 5

echo "檢查數據庫連接..."
until docker-compose exec -T postgres pg_isready -U resume_agent; do
  echo "等待數據庫啟動..."
  sleep 2
done

echo "數據庫已就緒！"

# 執行 SQL 初始化腳本
echo "正在執行數據庫初始化腳本..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker-compose exec -T postgres psql -U resume_agent -d resume_agent_db -f /docker-entrypoint-initdb.d/init.sql 2>/dev/null || \
docker-compose exec -T postgres psql -U resume_agent -d resume_agent_db < "$SCRIPT_DIR/init.sql" || {
  echo "嘗試直接執行 SQL..."
  docker-compose exec -T postgres psql -U resume_agent -d resume_agent_db <<EOF
$(cat "$SCRIPT_DIR/init.sql")
EOF
}

echo ""
echo "數據庫初始化完成！"
echo ""
echo "數據庫連接信息："
echo "  主機: localhost"
echo "  端口: 5432"
echo "  數據庫: resume_agent_db"
echo "  用戶: resume_agent"
echo "  密碼: resume_agent_pass"
echo ""
echo "連接字符串: postgresql://resume_agent:resume_agent_pass@localhost:5432/resume_agent_db"

