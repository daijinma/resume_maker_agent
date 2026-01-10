"""
日志工具
"""
import logging
import sys


def setup_logger(name: str = "resume-agent", level: int = logging.INFO) -> logging.Logger:
    """设置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 如果 logger 已经有 handler，不重复添加
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        # 允许传播到父 logger（如果父 logger 已配置）
        logger.propagate = True
    
    return logger

