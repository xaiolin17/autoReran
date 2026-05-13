import logging
import sys
import functools
import inspect
from typing import Optional, Any, Callable
from app.core.config import settings


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
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_function_call(logger_instance=None):
    """
    装饰器：记录函数调用的参数和返回值
    
    Args:
        logger_instance: 指定的日志记录器实例，如果不提供则使用默认的logger
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 获取logger实例
            log = logger_instance or logger
            
            # 获取函数签名信息
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # 记录函数调用和参数
            log.debug(f"调用函数: {func.__module__}.{func.__qualname__}")
            log.debug(f"参数: {dict(bound_args.arguments)}")
            
            try:
                result = func(*args, **kwargs)
                log.debug(f"函数 {func.__qualname__} 执行成功，返回类型: {type(result).__name__}")
                return result
            except Exception as e:
                log.error(f"函数 {func.__qualname__} 执行失败: {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator


def log_api_call(func: Callable) -> Callable:
    """
    装饰器：专门用于API端点的日志记录
    
    Args:
        func: 被装饰的API端点函数
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        log.debug(f"API端点调用: {func.__module__}.{func.__qualname__}")
        log.debug(f"请求参数: {kwargs}")
        
        try:
            result = func(*args, **kwargs)
            log.debug(f"API端点 {func.__qualname__} 执行成功")
            return result
        except Exception as e:
            log.error(f"API端点 {func.__qualname__} 执行失败: {str(e)}", exc_info=True)
            raise
    
    return wrapper


logger = setup_logger()