from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.services.indicator_service import IndicatorService

router = APIRouter()


@router.get("/{stock_code}")
def get_stock_data_with_indicators(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    service = IndicatorService(db)
    return service.get_stock_data_with_indicators(stock_code, period, start_date, end_date, limit)


@router.get("/signals/{stock_code}")
def get_indicator_signals(
    stock_code: str,
    indicator_type: str = "all",
    db: Session = Depends(get_db)
):
    from app.services.stock_service import StockService
    
    stock_service = StockService(db)
    indicator_service = IndicatorService(db)
    
    stock_data = stock_service.get_stock_data(stock_code, "1d", limit=500)
    if not stock_data:
        raise HTTPException(status_code=404, detail="Stock data not found")
    
    df = stock_service.to_dataframe(stock_data)
    
    if indicator_type == "kdj":
        signals = indicator_service.get_kdj_signals(df)
    elif indicator_type == "macd":
        signals = indicator_service.get_macd_signals(df)
    else:
        signals = indicator_service.get_all_signals(df)
    
    return {"signals": signals}
