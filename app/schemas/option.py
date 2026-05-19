from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class OptionData(BaseModel):
    """期权数据模型"""

    option_code: str
    stock_code: str
    strike_price: float
    expire_date: str
    option_type: str  # 'call' 或 'put'
    latest_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_volume: Optional[int] = None
    ask_volume: Optional[int] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    change_percent: Optional[float] = None
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    theta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    update_time: datetime

    class Config:
        from_attributes = True


class OptionChainData(BaseModel):
    """期权链数据"""

    stock_code: str
    stock_price: Optional[float] = None
    expire_dates: List[str]
    calls: List[OptionData]
    puts: List[OptionData]
    update_time: datetime
