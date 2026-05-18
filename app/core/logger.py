import logging
import sys
import inspect
import os
from typing import Optional
from app.core.config import settings


class CallerFilter(logging.Filter):
    """日志过滤器：动态添加调用者信息（模块名.函数名）"""

    def filter(self, record):
        # 查找实际的调用者（跳过日志相关的帧）
        frame = inspect.currentframe()
        try:
            # 向上回溯：filter -> handle -> callHandlers -> _log -> log -> 调用者
            # 需要跳过 logging 模块和当前 logger 模块的帧
            caller_frame = None
            while frame:
                filename = frame.f_code.co_filename
                func_name = frame.f_code.co_name
                # 跳过 logging 模块和 logger.py 自身的帧
                if 'logging' not in filename and 'logger.py' not in filename:
                    caller_frame = frame
                    break
                frame = frame.f_back

            if caller_frame:
                module = inspect.getmodule(caller_frame)
                module_name = module.__name__ if module else os.path.basename(caller_frame.f_code.co_filename)
                func_name = caller_frame.f_code.co_name

                # 如果是类方法，尝试获取类名
                if 'self' in caller_frame.f_locals:
                    class_name = caller_frame.f_locals['self'].__class__.__name__
                    record.caller_info = f"{module_name}.{class_name}.{func_name}"
                else:
                    record.caller_info = f"{module_name}.{func_name}"
            else:
                record.caller_info = record.name
        finally:
            del frame

        return True


def setup_logger(name: str = "stock_analysis") -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称，默认为"stock_analysis"

    Returns:
        logging.Logger: 配置好的日志记录器实例
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 使用 caller_info 替代固定的 name
    formatter = logging.Formatter(
        "%(asctime)s - %(caller_info)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 添加调用者过滤器
    caller_filter = CallerFilter()
    logger.addFilter(caller_filter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()