from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from app.core.database import get_db
from app.services.indicator_service import IndicatorService
from app.services.stock_service import StockService

router = APIRouter()

# 简单的后台任务状态管理
task_status: Dict[str, Dict] = {}


@router.get("/{stock_code}")
def get_stock_data_with_indicators(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 20,  # 默认展示最近1个月数据（约20个交易日）
    db: Session = Depends(get_db)
):
    service = IndicatorService(db)
    return service.get_stock_data_with_indicators(stock_code, period, start_date, end_date, limit)


@router.get("/{stock_code}/recent")
def get_recent_stock_data(
    stock_code: str,
    period: str = "1d",
    days: int = 180,  # 默认加载半年数据
    db: Session = Depends(get_db)
):
    """获取最近N天的数据（快速加载）"""
    from app.models.stock_data import StockData
    from sqlalchemy import desc
    import pandas as pd
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    query = db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == period,
        StockData.datetime >= start_date,
        StockData.datetime <= end_date
    ).order_by(StockData.datetime)
    
    stock_data_list = query.all()
    
    if not stock_data_list:
        return []
    
    data = []
    for stock in stock_data_list:
        data.append({
            'datetime': stock.datetime.isoformat() if hasattr(stock.datetime, 'isoformat') else str(stock.datetime),
            'open_price': stock.open_price,
            'high_price': stock.high_price,
            'low_price': stock.low_price,
            'close_price': stock.close_price,
            'volume': stock.volume,
            'amount': stock.amount,
        })
    
    df = pd.DataFrame(data)
    
    if len(df) > 0:
        df = IndicatorService.calculate_indicators_for_df_static(df)
        
        result = []
        for _, row in df.iterrows():
            item = {
                'datetime': row['datetime'],
                'open_price': float(row['open_price']),
                'high_price': float(row['high_price']),
                'low_price': float(row['low_price']),
                'close_price': float(row['close_price']),
                'volume': float(row['volume']),
                'amount': float(row['amount']) if pd.notna(row['amount']) else None
            }
            
            for col in ['kdj_k', 'kdj_d', 'kdj_j', 'macd', 'macd_signal', 'macd_histogram', 'rsi', 'bb_middle', 'bb_upper', 'bb_lower']:
                if col in row:
                    item[col] = float(row[col]) if pd.notna(row[col]) else None
            
            for col in ['ma5', 'ma10', 'ma20', 'ma60']:
                if col in row:
                    item[col] = float(row[col]) if pd.notna(row[col]) else None
            
            result.append(item)
        
        return result
    
    return []


@router.get("/{stock_code}/paged")
def get_paged_stock_data(
    stock_code: str,
    period: str = "1d",
    offset: int = 0,
    count: int = 90,  # 每次加载90天
    db: Session = Depends(get_db)
):
    """分页获取历史数据（用于加载更多）"""
    from app.models.stock_data import StockData
    from sqlalchemy import desc
    import pandas as pd
    
    query = db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == period
    ).order_by(desc(StockData.datetime))
    
    # 获取总数
    total = query.count()
    
    # 获取分页数据
    stock_data_list = query.offset(offset).limit(count).all()
    
    if not stock_data_list:
        return {
            'data': [],
            'total': total,
            'offset': offset,
            'has_more': False
        }
    
    # 按时间正序排序
    stock_data_list = sorted(stock_data_list, key=lambda x: x.datetime)
    
    data = []
    for stock in stock_data_list:
        data.append({
            'datetime': stock.datetime.isoformat() if hasattr(stock.datetime, 'isoformat') else str(stock.datetime),
            'open_price': stock.open_price,
            'high_price': stock.high_price,
            'low_price': stock.low_price,
            'close_price': stock.close_price,
            'volume': stock.volume,
            'amount': stock.amount,
        })
    
    df = pd.DataFrame(data)
    result = []
    
    if len(df) > 0:
        df = IndicatorService.calculate_indicators_for_df_static(df)
        
        for _, row in df.iterrows():
            item = {
                'datetime': row['datetime'],
                'open_price': float(row['open_price']),
                'high_price': float(row['high_price']),
                'low_price': float(row['low_price']),
                'close_price': float(row['close_price']),
                'volume': float(row['volume']),
                'amount': float(row['amount']) if pd.notna(row['amount']) else None
            }
            
            for col in ['kdj_k', 'kdj_d', 'kdj_j', 'macd', 'macd_signal', 'macd_histogram', 'rsi', 'bb_middle', 'bb_upper', 'bb_lower']:
                if col in row:
                    item[col] = float(row[col]) if pd.notna(row[col]) else None
            
            for col in ['ma5', 'ma10', 'ma20', 'ma60']:
                if col in row:
                    item[col] = float(row[col]) if pd.notna(row[col]) else None
            
            result.append(item)
    
    has_more = (offset + count) < total
    
    return {
        'data': result,
        'total': total,
        'offset': offset + len(result),
        'has_more': has_more
    }


@router.post("/{stock_code}/download")
def download_stock_data(
    stock_code: str,
    period: str = "1d",
    download_all: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """启动后台下载数据任务"""
    task_id = f"{stock_code}_{datetime.now().timestamp()}"
    
    # 先检查是否已有数据
    stock_service = StockService(db)
    existing_data = stock_service.get_stock_data(stock_code, period, limit=1)
    
    if download_all:
        # 下载所有周期
        background_tasks.add_task(_download_all_periods_task, stock_code, task_id, incremental=bool(existing_data))
        return {
            "task_id": task_id,
            "message": "后台下载所有周期数据中，可先查看已有数据",
            "has_existing_data": bool(existing_data)
        }
    elif existing_data:
        # 如果已有数据，快速返回并后台更新
        background_tasks.add_task(_download_task, stock_code, period, task_id, incremental=True)
        return {
            "task_id": task_id,
            "message": "后台更新中，可先查看已有数据",
            "has_existing_data": True
        }
    else:
        # 没有数据，启动下载
        background_tasks.add_task(_download_task, stock_code, period, task_id, incremental=False)
        return {
            "task_id": task_id,
            "message": "开始下载数据",
            "has_existing_data": False
        }


@router.get("/task/{task_id}/status")
def get_task_status(task_id: str):
    """获取后台任务状态"""
    status = task_status.get(task_id, {
        "status": "not_found",
        "progress": 0,
        "message": "任务不存在"
    })
    return status


def _download_task(stock_code: str, period: str, task_id: str, incremental: bool):
    """后台下载任务"""
    from app.core.database import SessionLocal
    db_local = SessionLocal()
    
    try:
        task_status[task_id] = {
            "status": "downloading",
            "progress": 10,
            "message": "正在获取数据..."
        }
        
        stock_service = StockService(db_local)
        
        # 下载数据
        if incremental:
            # 更新最近数据
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        else:
            # 下载一年数据
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        
        task_status[task_id] = {
            "status": "downloading",
            "progress": 30,
            "message": "正在从东方财富获取数据..."
        }
        
        saved = stock_service.fetch_and_save_stock_data(stock_code, period, start_date, end_date)
        
        task_status[task_id] = {
            "status": "downloading",
            "progress": 70,
            "message": "正在计算技术指标..."
        }
        
        # 触发指标计算
        indicator_service = IndicatorService(db_local)
        indicator_service.get_stock_data_with_indicators(stock_code, period)
        
        task_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": f"数据下载完成，共更新{len(saved)}条记录",
            "new_data_available": True
        }
        
    except Exception as e:
        task_status[task_id] = {
            "status": "error",
            "progress": 0,
            "message": f"下载失败: {str(e)}"
        }
    finally:
        db_local.close()


def _download_all_periods_task(stock_code: str, task_id: str, incremental: bool):
    """后台下载所有周期数据任务"""
    from app.core.database import SessionLocal
    db_local = SessionLocal()
    
    periods = ["1h", "1d", "1w", "1M"]
    total_periods = len(periods)
    
    try:
        stock_service = StockService(db_local)
        indicator_service = IndicatorService(db_local)
        
        for i, period in enumerate(periods):
            progress = int(10 + (i / total_periods) * 80)
            task_status[task_id] = {
                "status": "downloading",
                "progress": progress,
                "message": f"正在下载{period}周期数据 ({i + 1}/{total_periods})..."
            }
            
            # 下载数据
            if incremental:
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            else:
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            
            try:
                saved = stock_service.fetch_and_save_stock_data(stock_code, period, start_date, end_date)
                
                # 计算技术指标
                indicator_service.get_stock_data_with_indicators(stock_code, period)
                
            except Exception as e:
                print(f"下载{period}周期数据时出错: {e}")
                continue
        
        task_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": "所有周期数据下载完成",
            "new_data_available": True
        }
        
    except Exception as e:
        task_status[task_id] = {
            "status": "error",
            "progress": 0,
            "message": f"下载失败: {str(e)}"
        }
    finally:
        db_local.close()


@router.get("/signals/{stock_code}")
def get_indicator_signals(
    stock_code: str,
    indicator_type: str = "all",
    db: Session = Depends(get_db)
):
    from app.models.stock_data import StockData
    from sqlalchemy import desc
    import pandas as pd
    
    indicator_service = IndicatorService(db)
    
    query = db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == "1d"
    ).order_by(desc(StockData.datetime)).limit(500)
    
    stock_data_list = query.all()
    
    if not stock_data_list:
        raise HTTPException(status_code=404, detail="Stock data not found")
    
    data = []
    for stock in stock_data_list:
        data.append({
            'datetime': stock.datetime,
            'open_price': stock.open_price,
            'high_price': stock.high_price,
            'low_price': stock.low_price,
            'close_price': stock.close_price,
            'volume': stock.volume,
            'amount': stock.amount,
        })
    
    df = pd.DataFrame(data)
    df = df.sort_values('datetime').reset_index(drop=True)
    
    if indicator_type == "kdj":
        signals = indicator_service.get_kdj_signals(df)
    elif indicator_type == "macd":
        signals = indicator_service.get_macd_signals(df)
    else:
        signals = indicator_service.get_all_signals(df)
    
    return {"signals": signals}
