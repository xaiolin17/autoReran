from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.schemas.stock import StockData, StockDataCreate
from app.services.stock_service import StockService

router = APIRouter()


@router.get("/{stock_code}", response_model=List[StockData])
def get_stock_data(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    service = StockService(db)
    return service.get_stock_data(stock_code, period, start_date, end_date, limit)


@router.post("/", response_model=StockData)
def create_stock_data(stock_data: StockDataCreate, db: Session = Depends(get_db)):
    service = StockService(db)
    return service.create_stock_data(stock_data)


@router.post("/fetch/{stock_code}")
def fetch_and_save_stock_data(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = StockService(db)
    saved_data = service.fetch_and_save_stock_data(stock_code, period, start_date, end_date)
    return {"message": f"Successfully saved {len(saved_data)} records", "count": len(saved_data)}


@router.get("/latest/{stock_code}", response_model=Optional[StockData])
def get_latest_stock_data(
    stock_code: str,
    period: str = "1d",
    db: Session = Depends(get_db)
):
    service = StockService(db)
    return service.get_latest_stock_data(stock_code, period)


@router.get("/")
def get_available_stocks(db: Session = Depends(get_db)):
    service = StockService(db)
    stocks = service.get_available_stocks()
    return {"stocks": stocks}
