from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
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


@router.post("/refresh/{stock_code}")
def refresh_stock_data(
    stock_code: str,
    period: str = "1d",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    from datetime import timedelta
    
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
    
    background_tasks.add_task(run_refresh_task, stock_code, period, start_date_str)
    
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
    from datetime import timedelta
    
    service = StockService(db)
    earliest_date = service.get_earliest_date(stock_code, period)
    
    historical_end_date_str = None
    if earliest_date:
        historical_end_date_str = (earliest_date - timedelta(days=1)).strftime("%Y%m%d")
        message = f"发现现有数据，截至 {historical_end_date_str} 之前获取历史数据"
    else:
        message = f"没有现有数据，将下载完整历史数据"
    
    background_tasks.add_task(run_load_historical_task, stock_code, period, historical_end_date_str)
    
    return {
        "message": message,
        "stock_code": stock_code,
        "period": period,
        "has_existing_data": earliest_date is not None
    }


def run_load_historical_task(stock_code: str, period: str = "1d", historical_end_date: Optional[str] = None):
    import asyncio
    from app.core.database import SessionLocal
    
    async def async_load():
        db = SessionLocal()
        try:
            service = StockService(db)
            indicator_service = IndicatorService(db)
            
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "downloading",
                    "progress": 10,
                    "message": "正在从 AkShare 获取历史数据..."
                }
            }, channel="realtime")
            
            saved_data = service.fetch_and_save_stock_data(
                stock_code, period, historical=True
            )
            
            if saved_data:
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "calculating",
                        "progress": 70,
                        "message": "正在计算技术指标..."
                    }
                }, channel="realtime")
                
                indicator_service.calculate_and_save_indicators(stock_code, period)
                
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "completed",
                        "progress": 100,
                        "message": f"历史数据加载完成，新增 {len(saved_data)} 条数据",
                        "new_data_available": True
                    }
                }, channel="realtime")
            else:
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "completed",
                        "progress": 100,
                        "message": "没有更多历史数据",
                        "new_data_available": False
                    }
                }, channel="realtime")
                
        except Exception as e:
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "error",
                    "progress": 0,
                    "message": f"加载历史数据失败: {str(e)}"
                }
            }, channel="realtime")
        finally:
            db.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_load())
    finally:
        loop.close()


def run_refresh_task(stock_code: str, period: str = "1d", start_date: Optional[str] = None):
    import asyncio
    from app.core.database import SessionLocal
    
    async def async_refresh():
        db = SessionLocal()
        try:
            service = StockService(db)
            indicator_service = IndicatorService(db)
            
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "downloading",
                    "progress": 10,
                    "message": "正在从 AkShare 获取数据..."
                }
            }, channel="realtime")
            
            saved_data = service.fetch_and_save_stock_data(
                stock_code, period, start_date=start_date, incremental=True
            )
            
            if saved_data:
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "calculating",
                        "progress": 70,
                        "message": "正在计算技术指标..."
                    }
                }, channel="realtime")
                
                indicator_service.calculate_and_save_indicators(stock_code, period)
                
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "completed",
                        "progress": 100,
                        "message": f"刷新完成，新增 {len(saved_data)} 条数据",
                        "new_data_available": True
                    }
                }, channel="realtime")
            else:
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "completed",
                        "progress": 100,
                        "message": "已是最新数据，无需更新",
                        "new_data_available": False
                    }
                }, channel="realtime")
                
        except Exception as e:
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "error",
                    "progress": 0,
                    "message": f"刷新失败: {str(e)}"
                }
            }, channel="realtime")
        finally:
            db.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_refresh())
    finally:
        loop.close()
