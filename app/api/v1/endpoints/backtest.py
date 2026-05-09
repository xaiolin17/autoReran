from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.backtest import BacktestResult, BacktestRequest
from app.services.backtest_service import BacktestService

router = APIRouter()


@router.post("/run", response_model=BacktestResult)
def run_backtest(request: BacktestRequest, db: Session = Depends(get_db)):
    service = BacktestService(db)
    try:
        return service.run_backtest(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/results", response_model=List[BacktestResult])
def get_backtests(
    stock_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = BacktestService(db)
    return service.get_backtests(stock_code)


@router.get("/results/{backtest_id}", response_model=Optional[BacktestResult])
def get_backtest(
    backtest_id: int,
    db: Session = Depends(get_db)
):
    service = BacktestService(db)
    result = service.get_backtest(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    return result


@router.delete("/results/{backtest_id}")
def delete_backtest(
    backtest_id: int,
    db: Session = Depends(get_db)
):
    service = BacktestService(db)
    success = service.delete_backtest(backtest_id)
    if not success:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    return {"message": "Backtest result deleted successfully"}
