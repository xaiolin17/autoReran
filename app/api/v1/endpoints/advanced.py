from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from app.core.database import get_db
from app.core.websocket_manager import manager
from app.core.serialization import json_dumps
from app.utils.export import export_to_csv, export_to_excel, create_backup, list_backups
from app.models.stock_data import StockData
from app.models.backtest_result import BacktestResult
from app.models.task_status import TaskStatus
from app.core.logger import logger

router = APIRouter()


@router.get("/export/stocks/csv")
def export_stocks_csv(
    stock_code: Optional[str] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(StockData)
    if stock_code:
        query = query.filter(StockData.stock_code == stock_code)
    if period:
        query = query.filter(StockData.period == period)
    
    data = query.all()
    dict_data = [
        {
            "id": d.id,
            "stock_code": d.stock_code,
            "stock_name": d.stock_name,
            "period": d.period,
            "datetime": d.datetime.isoformat() if d.datetime else None,
            "open_price": d.open_price,
            "high_price": d.high_price,
            "low_price": d.low_price,
            "close_price": d.close_price,
            "volume": d.volume,
            "amount": d.amount,
            "source": d.source,
        }
        for d in data
    ]
    
    filename = f"stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return export_to_csv(dict_data, filename)


@router.get("/export/stocks/excel")
def export_stocks_excel(
    stock_code: Optional[str] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(StockData)
    if stock_code:
        query = query.filter(StockData.stock_code == stock_code)
    if period:
        query = query.filter(StockData.period == period)
    
    data = query.all()
    dict_data = [
        {
            "id": d.id,
            "stock_code": d.stock_code,
            "stock_name": d.stock_name,
            "period": d.period,
            "datetime": d.datetime.isoformat() if d.datetime else None,
            "open_price": d.open_price,
            "high_price": d.high_price,
            "low_price": d.low_price,
            "close_price": d.close_price,
            "volume": d.volume,
            "amount": d.amount,
            "source": d.source,
        }
        for d in data
    ]
    
    filename = f"stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return export_to_excel(dict_data, filename, "Stock Data")


@router.get("/export/backtests/csv")
def export_backtests_csv(
    stock_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(BacktestResult)
    if stock_code:
        query = query.filter(BacktestResult.stock_code == stock_code)
    
    data = query.all()
    dict_data = [
        {
            "id": d.id,
            "stock_code": d.stock_code,
            "strategy_name": d.strategy_name,
            "start_date": d.start_date.isoformat() if d.start_date else None,
            "end_date": d.end_date.isoformat() if d.end_date else None,
            "initial_capital": d.initial_capital,
            "final_capital": d.final_capital,
            "total_return": d.total_return,
            "annual_return": d.annual_return,
            "max_drawdown": d.max_drawdown,
            "win_rate": d.win_rate,
            "total_trades": d.total_trades,
            "winning_trades": d.winning_trades,
            "losing_trades": d.losing_trades,
            "notes": d.notes,
        }
        for d in data
    ]
    
    filename = f"backtests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return export_to_csv(dict_data, filename)


@router.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str = "default"):
    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"收到WebSocket消息: channel={channel}, data={data}")
            await manager.broadcast({"type": "message", "data": data}, channel)
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        manager.disconnect(websocket, channel)


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "result": task.result,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.get("/tasks")
def list_tasks(
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(TaskStatus)
    if task_type:
        query = query.filter(TaskStatus.task_type == task_type)
    if status:
        query = query.filter(TaskStatus.status == status)
    
    tasks = query.order_by(TaskStatus.created_at.desc()).all()
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "status": t.status,
                "progress": t.progress,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]
    }


@router.post("/backup/create")
def create_data_backup(db: Session = Depends(get_db)):
    stocks = db.query(StockData).all()
    backtests = db.query(BacktestResult).all()
    
    backup_data = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "stocks": [
            {
                "stock_code": s.stock_code,
                "stock_name": s.stock_name,
                "period": s.period,
                "datetime": s.datetime.isoformat() if s.datetime else None,
                "open_price": s.open_price,
                "high_price": s.high_price,
                "low_price": s.low_price,
                "close_price": s.close_price,
                "volume": s.volume,
                "amount": s.amount,
                "source": s.source,
            }
            for s in stocks
        ],
        "backtests": [
            {
                "stock_code": b.stock_code,
                "strategy_name": b.strategy_name,
                "start_date": b.start_date.isoformat() if b.start_date else None,
                "end_date": b.end_date.isoformat() if b.end_date else None,
                "initial_capital": b.initial_capital,
                "final_capital": b.final_capital,
                "total_return": b.total_return,
                "annual_return": b.annual_return,
                "max_drawdown": b.max_drawdown,
                "win_rate": b.win_rate,
                "total_trades": b.total_trades,
                "winning_trades": b.winning_trades,
                "losing_trades": b.losing_trades,
                "trade_log": b.trade_log,
                "notes": b.notes,
            }
            for b in backtests
        ]
    }
    
    filepath = create_backup(json.dumps(backup_data, ensure_ascii=False), "full")
    return {"success": True, "filepath": filepath, "message": "备份创建成功"}


@router.get("/backup/list")
def list_data_backups():
    backups = list_backups()
    return {"success": True, "backups": backups}
