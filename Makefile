.PHONY: install dev clean help sync

VENV = .venv
PYTHON = $(VENV)/bin/python

# 默认目标
help:
	@echo "可用命令:"
	@echo "  make install  - 使用 uv 创建 venv 并安装依赖"
	@echo "  make sync     - 检查并同步 pyproject.toml 中的依赖"
	@echo "  make dev      - 自动同步依赖并启动 FastAPI 开发服务器"
	@echo "  make clean    - 清理 python 缓存文件和 venv"

# 初始化并安装
install:
	uv venv $(VENV)
	@$(MAKE) sync

# 同步依赖：检查并安装缺失的库
sync:
	@echo "正在检查并更新依赖..."
	@uv pip install -e .

# 启动开发服务器：先执行 sync 确保库是最新的
dev: sync
	@echo "正在启动服务..."
	uv run python src/main.py

# 清理环境
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf $(VENV)
