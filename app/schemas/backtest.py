from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any


class BacktestResultBase(BaseModel):
    stock_code: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    trade_log: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


class BacktestResultCreate(BacktestResultBase):
    pass


class BacktestResult(BacktestResultBase):
    id: int
    model_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    stock_code: str
    strategy_name: str
    model_id: Optional[int] = None
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    params: Optional[Dict[str, Any]] = None


class TradeLog(BaseModel):
    datetime: str
    action: str
    price: float
    shares: int
    reason: Optional[str] = None
    profit: Optional[float] = None
