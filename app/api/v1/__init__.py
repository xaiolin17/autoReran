from fastapi import APIRouter

from app.api.v1.endpoints import backtest, indicators, ml, options, stocks

api_router = APIRouter()

api_router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["stocks"],
)
api_router.include_router(
    indicators.router,
    prefix="/indicators",
    tags=["indicators"],
)
api_router.include_router(
    ml.router, prefix="/ml", tags=["ml"]
)
api_router.include_router(
    backtest.router, prefix="/backtest", tags=["backtest"]
)
api_router.include_router(
    options.router, prefix="/options", tags=["options"]
)
