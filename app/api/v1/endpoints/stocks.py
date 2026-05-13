from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import threading
from app.core.database import get_db
from app.schemas.stock import StockData, StockDataCreate
from app.services.stock_service import StockService
from app.services.indicator_service import IndicatorService
from app.core.websocket_manager import manager

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


def _send_progress_ws(stock_code: str, status: str, progress: int, message: str, new_data_available: bool = False):
    """Thread-safe WebSocket progress notification"""
    import asyncio
    
    async def _broadcast():
        await manager.broadcast({
            "type": "download_progress",
            "data": {
                "stock_code": stock_code,
                "status": status,
                "progress": progress,
                "message": message,
                "new_data_available": new_data_available
            }
        }, channel="realtime")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_broadcast())
        finally:
            loop.close()
    except Exception:
        pass  # Silently ignore WebSocket errors


def _run_load_historical_task(stock_code: str, period: str):
    """Sync task for loading historical data"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)
        
        _send_progress_ws(stock_code, "downloading", 10, "正在从 AkShare 获取历史数据...")
        
        saved_data = service.fetch_and_save_stock_data(stock_code, period, historical=True)
        
        if saved_data:
            _send_progress_ws(stock_code, "calculating", 70, "正在计算技术指标...")
            indicator_service.calculate_and_save_indicators(stock_code, period)
            _send_progress_ws(stock_code, "completed", 100, f"历史数据加载完成，新增 {len(saved_data)} 条数据", True)
        else:
            _send_progress_ws(stock_code, "completed", 100, "没有更多历史数据", False)
    except Exception as e:
        _send_progress_ws(stock_code, "error", 0, f"加载历史数据失败: {str(e)}")
    finally:
        db.close()


def _run_refresh_task(stock_code: str, period: str, start_date: Optional[str] = None):
    """Sync task for refreshing data"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)
        
        _send_progress_ws(stock_code, "downloading", 10, "正在从 AkShare 获取数据...")
        
        saved_data = service.fetch_and_save_stock_data(
            stock_code, period, start_date=start_date, incremental=True
        )
        
        if saved_data:
            _send_progress_ws(stock_code, "calculating", 70, "正在计算技术指标...")
            indicator_service.calculate_and_save_indicators(stock_code, period)
            _send_progress_ws(stock_code, "completed", 100, f"刷新完成，新增 {len(saved_data)} 条数据", True)
        else:
            _send_progress_ws(stock_code, "completed", 100, "已是最新数据，无需更新", False)
    except Exception as e:
        _send_progress_ws(stock_code, "error", 0, f"刷新失败: {str(e)}")
    finally:
        db.close()


@router.post("/refresh/{stock_code}")
def refresh_stock_data(
    stock_code: str,
    period: str = "1d",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    service = StockService(db)
    latest_date = service.get_latest_date(stock_code, period)
    
    start_date_str = None
    if latest_date:
        latest_date_only = latest_date.date()
        today = datetime.now().date()
        if latest_date_only >= today:
            message = f"已有数据已是最新 (截止 {latest_date_only})，无需更新"
        else:
            start_date_str = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
            message = f"发现现有数据，从 {start_date_str} 开始增量更新"
    else:
        message = f"没有现有数据，将下载完整数据"
    
    thread = threading.Thread(target=_run_refresh_task, args=(stock_code, period, start_date_str), daemon=True)
    thread.start()
    
    return {
        "message": message,
        "stock_code": stock_code,
        "period": period,
        "incremental": latest_date is not None
    }


@router.post("/load-historical/{stock_code}")
def load_historical_data(
    stock_code: str,
    period: str = "1d",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    service = StockService(db)
    earliest_date = service.get_earliest_date(stock_code, period)
    
    if not earliest_date:
        # 数据库中没有数据，直接下载
        message = f"没有现有数据，将下载完整历史数据"
        thread = threading.Thread(target=_run_load_historical_task, args=(stock_code, period), daemon=True)
        thread.start()
    else:
        # 数据库中已有数据，尝试获取更多历史数据
        # 先计算要获取的历史数据范围（往前3个月）
        historical_end_date = (earliest_date - timedelta(days=1)).strftime("%Y%m%d")
        historical_start_date = (earliest_date - timedelta(days=90)).strftime("%Y%m%d")
        
        # 同步获取数据
        saved_data = service.fetch_and_save_stock_data(
            stock_code, period, 
            start_date=historical_start_date, 
            end_date=historical_end_date
        )
        
        if saved_data:
            # 获取到新数据，计算指标
            indicator_service = IndicatorService(db)
            indicator_service.calculate_and_save_indicators(stock_code, period)
            message = f"加载历史数据完成，新增 {len(saved_data)} 条记录"
        else:
            message = f"没有更多历史数据（最早数据：{earliest_date.strftime('%Y-%m-%d')}）"
    
    return {
        "message": message,
        "stock_code": stock_code,
        "period": period,
        "has_existing_data": earliest_date is not None
    }
