.PHONY: install dev clean help sync db-up db-down db-init db-migrate db-reset db-logs db-fix-schema test-auto

VENV = .venv
PYTHON = $(VENV)/bin/python

# 默认目标
help:
	@echo "可用命令:"
	@echo "  make install  - 使用 uv 创建 venv 并安装依赖"
	@echo "  make sync     - 检查并同步 pyproject.toml 中的依赖"
	@echo "  make dev      - 自动同步依赖并启动 FastAPI 开发服务器"
	@echo "  make clean    - 清理 python 缓存文件和 venv"
	@echo "  make test-auto - 运行自动测试脚本（测试第一句话）"
	@echo ""
	@echo "數據庫命令（雙軌架構）:"
	@echo "  make db-up     - 啟動 PostgreSQL 容器"
	@echo "  make db-down   - 停止 PostgreSQL 容器"
	@echo "  make db-init   - 初始化數據庫表結構"
	@echo "  make db-migrate - 從 JSON 遷移數據到 PostgreSQL"
	@echo "  make db-fix-schema - 修復數據庫表結構（添加缺失的列）"
	@echo "  make db-reset  - 重置數據庫（開發用，會刪除所有數據）"
	@echo "  make db-logs   - 查看數據庫日誌"

# 初始化并安装
install:
	uv venv $(VENV)
	@$(MAKE) sync

# 同步依赖：检查并安装缺失的库
sync:
	@echo "正在检查并更新依赖..."
	@uv pip install -e .

# 启动开发服务器：先执行 sync 确保库是最新的
dev:
	@echo "正在启动服务..."
	lsof -ti:8000 | xargs kill -9 && PYTHONPATH=. uv run python src/main.py

# 清理环境
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf $(VENV)

# 數據庫命令（雙軌架構）
db-up:
	@echo "正在啟動 PostgreSQL 容器..."
	@docker-compose up -d postgres
	@echo "等待數據庫就緒..."
	@sleep 3
	@echo "數據庫已啟動！"

db-down:
	@echo "正在停止 PostgreSQL 容器..."
	@docker-compose down

db-init:
	@echo "正在初始化數據庫..."
	@bash scripts/init_db.sh

db-migrate:
	@echo "正在從 JSON 遷移數據到 PostgreSQL..."
	@PYTHONPATH=. uv run python scripts/migrate_from_json.py

db-fix-schema:
	@echo "正在修復數據庫表結構..."
	@docker-compose exec -T postgres psql -U resume_agent -d resume_agent_db -f /docker-entrypoint-initdb.d/add_history_column.sql 2>/dev/null || \
	docker-compose exec -T postgres psql -U resume_agent -d resume_agent_db < scripts/add_history_column.sql || \
	docker-compose exec -T postgres psql -U resume_agent -d resume_agent_db <<EOF
	$$(cat scripts/add_history_column.sql)
	EOF
	@echo "數據庫表結構修復完成！"

db-reset:
	@bash scripts/reset_db.sh

db-logs:
	@docker-compose logs -f postgres

# 自动测试脚本
test-auto:
	@echo "正在运行自动测试脚本..."
	@PYTHONPATH=. uv run python scripts/auto_test_first_message.py
