from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TradeMarkBase(BaseModel):
    stock_code: str
    period: str
    datetime: datetime
    mark_type: str
    price: float
    reason: Optional[str] = None
    is_active: bool = True


class TradeMarkCreate(TradeMarkBase):
    pass


class TradeMark(TradeMarkBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
