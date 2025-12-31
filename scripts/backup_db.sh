#!/bin/bash
# 數據庫備份腳本

set -e

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "正在備份數據庫..."
docker-compose exec -T postgres pg_dump -U resume_agent resume_agent_db > "$BACKUP_FILE"

echo "備份完成: $BACKUP_FILE"
echo "文件大小: $(du -h "$BACKUP_FILE" | cut -f1)"

