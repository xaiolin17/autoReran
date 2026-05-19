from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StockDataBase(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    period: str
    datetime: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    amount: Optional[float] = None
    source: Optional[str] = None


class StockDataCreate(StockDataBase):
    pass


class StockData(StockDataBase):
    id: int

    class Config:
        from_attributes = True


class StockDataWithIndicators(StockData):
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
