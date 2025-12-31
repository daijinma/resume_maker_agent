#!/bin/bash
# 重置數據庫腳本（僅用於開發環境）

set -e

echo "⚠️  警告：此操作將刪除所有數據！"
read -p "確認重置數據庫？(yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "已取消"
    exit 0
fi

echo "正在停止並刪除容器..."
docker-compose down -v

echo "正在重新啟動數據庫..."
docker-compose up -d postgres

echo "等待數據庫就緒..."
sleep 5

echo "數據庫已重置！"

