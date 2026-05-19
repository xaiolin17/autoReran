from typing import Optional

from pydantic import BaseModel


class KDJIndicator(BaseModel):
    k: float
    d: float
    j: float


class MACDIndicator(BaseModel):
    macd: float
    signal: float
    histogram: float


class TechnicalIndicators(BaseModel):
    kdj: Optional[KDJIndicator] = None
    macd: Optional[MACDIndicator] = None


class StockDataWithIndicators(BaseModel):
    datetime: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
