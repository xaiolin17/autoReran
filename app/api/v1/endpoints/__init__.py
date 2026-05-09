from app.api.v1.endpoints import stocks
from app.api.v1.endpoints import indicators
from app.api.v1.endpoints import ml
from app.api.v1.endpoints import backtest
from app.api.v1.endpoints import sample_data
from app.api.v1.endpoints import options

__all__ = [
    "stocks",
    "indicators",
    "ml",
    "backtest",
    "sample_data",
    "options"
]

# 可选模块 - 不会导致导入错误
try:
    from app.api.v1.endpoints import scheduler
    __all__.append("scheduler")
except ImportError:
    pass

try:
    from app.api.v1.endpoints import cache
    __all__.append("cache")
except ImportError:
    pass
