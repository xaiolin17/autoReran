from fastapi import APIRouter
from app.api.v1.endpoints import stocks, indicators, ml, backtest, sample_data, options
from app.core.logger import logger

api_router = APIRouter()

# 核心路由 - 始终启用
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(indicators.router, prefix="/indicators", tags=["indicators"])
api_router.include_router(ml.router, prefix="/ml", tags=["ml"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
api_router.include_router(sample_data.router, prefix="/sample", tags=["sample"])
api_router.include_router(options.router, prefix="/options", tags=["options"])

# 可选路由 - 仅在依赖可用时注册
try:
    from app.api.v1.endpoints import scheduler
    api_router.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
    logger.info("调度器路由已加载")
except ImportError:
    logger.warning("调度器模块不可用，路由未加载")

try:
    from app.api.v1.endpoints import cache
    api_router.include_router(cache.router, prefix="/cache", tags=["cache"])
    logger.info("缓存路由已加载")
except ImportError:
    logger.warning("缓存模块不可用，路由未加载")
