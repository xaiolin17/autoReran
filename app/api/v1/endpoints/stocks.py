from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import threading
from app.core.database import get_db
from app.schemas.stock import StockData, StockDataCreate
from app.services.stock_service import StockService
from app.services.indicator_service import IndicatorService
from app.core.websocket_manager import manager
from app.models.stock_data import StockData as StockDataModel
from app.core.logger import log_api_call, logger

router = APIRouter()


class MarkUpdate(BaseModel):
    date: str
    label: Optional[str] = None


# ============================================================
# 1. 根路由 (无 path parameters)
# ============================================================
@router.get("/")
def get_available_stocks(db: Session = Depends(get_db)):
    service = StockService(db)
    stocks = service.get_available_stocks()
    return {"stocks": stocks}


@router.post("/", response_model=StockData)
def create_stock_data(stock_data: StockDataCreate, db: Session = Depends(get_db)):
    service = StockService(db)
    return service.create_stock_data(stock_data)


# ============================================================
# 2. 标记相关接口 (使用查询参数，避免 path parameter 冲突)
# ============================================================
class MarkUpdateV2(BaseModel):
    stock_code: str
    date: str
    label: Optional[str] = None


@router.get("/marks")
def get_marks(
    stock_code: str,
    period: str = "1d",
    db: Session = Depends(get_db)
):
    marks = db.query(StockDataModel).filter(
        StockDataModel.stock_code == stock_code,
        StockDataModel.period == period,
        StockDataModel.label.isnot(None)
    ).all()

    result = []
    for mark in marks:
        result.append({
            "datetime": mark.datetime.isoformat() if hasattr(mark.datetime, 'isoformat') else str(mark.datetime),
            "label": mark.label
        })

    return result


@router.put("/mark")
def update_mark(
    mark_data: MarkUpdateV2,
    period: str = "1d",
    db: Session = Depends(get_db)
):
    date_str = mark_data.date

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")

    next_date = target_date + timedelta(days=1)

    record = db.query(StockDataModel).filter(
        StockDataModel.stock_code == mark_data.stock_code,
        StockDataModel.period == period,
        StockDataModel.datetime >= target_date,
        StockDataModel.datetime < next_date
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"Record not found for date {date_str}")

    record.label = mark_data.label
    db.commit()

    return {
        "message": "Mark updated successfully",
        "stock_code": mark_data.stock_code,
        "date": date_str,
        "label": mark_data.label
    }


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
    return {
        "message": f"Successfully saved {len(saved_data)} records",
        "count": len(saved_data),
        "start_date": start_date,
        "end_date": end_date
    }


@router.post("/fetch-async/{stock_code}")
@log_api_call
def fetch_async(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """启动后台线程下载指定范围的数据，通过 WebSocket 通知进度"""
    logger.info(f"接收到异步下载请求: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}")
    
    thread = threading.Thread(
        target=_run_fetch_task,
        args=(stock_code, period, start_date, end_date),
        daemon=True
    )
    thread.start()
    
    logger.info(f"后台下载线程已启动: stock_code={stock_code}")
    return {
        "message": "Download started",
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date
    }


@router.get("/latest/{stock_code}", response_model=Optional[StockData])
def get_latest_stock_data(
    stock_code: str,
    period: str = "1d",
    db: Session = Depends(get_db)
):
    service = StockService(db)
    return service.get_latest_stock_data(stock_code, period)


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


# ============================================================
# 3. 泛化路由 /{stock_code} - 必须放在最后！
# ============================================================
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


# ============================================================
# 辅助函数
# ============================================================
def _send_progress_ws(stock_code: str, status: str, progress: int, message: str, new_data_available: bool = False):
    """Thread-safe WebSocket progress notification"""
    logger.debug(f"发送WebSocket进度通知: stock_code={stock_code}, status={status}, progress={progress}, message={message}")
    import asyncio

    async def _broadcast():
        logger.debug(f"开始广播WebSocket消息到realtime频道")
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
            logger.debug(f"WebSocket进度通知发送成功: {message}")
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"WebSocket进度通知发送失败: {str(e)}")
        pass  # Silently ignore WebSocket errors


def _run_fetch_task(stock_code: str, period: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """后台下载指定范围数据的任务"""
    from app.core.database import SessionLocal

    logger.info(f"开始执行后台下载任务: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}")
    
    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)

        logger.debug(f"发送下载开始进度通知")
        _send_progress_ws(stock_code, "downloading", 10, "正在从 AkShare 获取数据...")

        logger.debug(f"开始获取并保存股票数据")
        saved_data = service.fetch_and_save_stock_data(
            stock_code, period, start_date=start_date, end_date=end_date
        )

        if saved_data:
            logger.info(f"数据下载完成，开始计算技术指标: {len(saved_data)} 条数据")
            _send_progress_ws(stock_code, "calculating", 70, "正在计算技术指标...")
            indicator_service.calculate_and_save_indicators(stock_code, period)
            logger.info(f"技术指标计算完成")
            _send_progress_ws(stock_code, "completed", 100, f"下载完成，新增 {len(saved_data)} 条数据", True)
        else:
            logger.info(f"下载完成，无新数据")
            _send_progress_ws(stock_code, "completed", 100, "无新数据", False)
    except Exception as e:
        logger.error(f"后台下载任务失败: {str(e)}", exc_info=True)
        _send_progress_ws(stock_code, "error", 0, f"下载失败: {str(e)}")
    finally:
        db.close()
        logger.info(f"后台下载任务完成并关闭数据库连接: stock_code={stock_code}")


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