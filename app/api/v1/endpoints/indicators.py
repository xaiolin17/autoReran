from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from app.core.database import get_db
from app.services.indicator_service import IndicatorService
from app.services.stock_service import StockService
from app.core.logger import log_api_call, logger

router = APIRouter()

# 简单的后台任务状态管理（内存存储，重启后丢失）
# 结构: {task_id: {"status": str, "progress": int, "message": str, ...}}
task_status: Dict[str, Dict] = {}


@router.get("/{stock_code}")
@log_api_call
def get_stock_data_with_indicators(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,  # 有日期范围时不使用 limit，优先保证日期范围完整
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    获取股票数据及技术指标（主接口）

    参数:
        stock_code: 股票代码（如000001或000001.SZ）
        period: 时间周期（如 1d, 1h, 1w, 1M）
        start_date: 开始日期（YYYY-MM-DD格式）
        end_date: 结束日期（YYYY-MM-DD格式）
        limit: 返回数据条数限制（有日期范围时自动设为None）
        background_tasks: FastAPI后台任务管理器，用于启动缺失数据下载
        db: 数据库会话（由FastAPI依赖注入）

    返回值:
        Dict: 包含以下字段:
            - data: 股票数据及技术指标列表
            - missing_ranges: 缺失数据时间段列表
            - stock_code: 股票代码
            - stock_name: 股票名称
            - download_task_id: 后台下载任务ID（如有缺失数据）

    调用关系:
        被调用: 前端HTTP GET /api/v1/indicators/{stock_code}
        调用: IndicatorService.get_stock_data_with_indicators, StockService, _download_missing_ranges_task

    关键逻辑:
        1. 从StockData或StockCode表查询股票中文名称
        2. 有日期范围时取消limit限制，确保缺失检测完整
        3. 调用IndicatorService获取数据及缺失范围
        4. 若有缺失数据且提供background_tasks，启动后台下载任务
        5. 通过WebSocket通知前端下载进度
    """
    logger.info(f"获取股票指标数据请求: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}")
    
    service = IndicatorService(db)
    stock_service = StockService(db)

    # 查询股票名称（从 StockData 记录中获取中文名称）
    stock_name = None
    try:
        from app.models.stock_data import StockData as StockDataModel
        # 优先从已有数据中获取中文名称
        name_record = db.query(StockDataModel).filter(
            StockDataModel.stock_code == stock_code
        ).order_by(StockDataModel.datetime.desc()).first()
        if name_record and name_record.stock_name:
            stock_name = name_record.stock_name
    except Exception:
        pass

    # 如果 StockData 中没有名称，从 StockCode 表获取完整代码作为 fallback
    if not stock_name:
        try:
            from app.models.stock_data import StockCode
            clean_code = stock_code.split('.')[0] if '.' in stock_code else stock_code
            user_suffix = None
            if '.' in stock_code:
                parts = stock_code.split('.')
                if len(parts) == 2:
                    user_suffix = parts[1].upper()

            records = db.query(StockCode).filter(StockCode.code == clean_code).all()
            if records:
                if user_suffix:
                    for r in records:
                        if r.name.endswith(f".{user_suffix}"):
                            stock_name = r.name
                            break
                if not stock_name:
                    stock_name = records[0].name
        except Exception:
            pass

    # 日期范围优先：有日期范围时不限制条数，确保缺失检测能正确执行
    if start_date or end_date:
        limit = None
        logger.debug(f"有日期范围参数，取消limit限制")

    result = service.get_stock_data_with_indicators(stock_code, period, start_date, end_date, limit)
    # result: {"data": [...], "missing_ranges": [...]}
    
    # 添加股票代码和名称信息到响应
    result["stock_code"] = stock_code
    result["stock_name"] = stock_name or stock_code
    
    logger.info(f"查询结果: 数据条数={len(result.get('data', []))}, 缺失范围数量={len(result.get('missing_ranges', []))}")
    
    # 如果有缺失范围，启动后台下载任务
    if result.get("missing_ranges") and background_tasks:
        task_id = f"{stock_code}_{period}_{datetime.now().timestamp()}_{len(result['missing_ranges'])}"
        task_status[task_id] = {
            "status": "starting",
            "progress": 0,
            "message": f"检测到{len(result['missing_ranges'])}个缺失数据范围，开始下载..."
        }
        
        logger.info(f"启动后台下载任务: task_id={task_id}, 缺失范围={result['missing_ranges']}")
        
        # 启动后台下载任务
        background_tasks.add_task(_download_missing_ranges_task, stock_code, period, result["missing_ranges"], task_id)
        
        # 添加任务ID到响应
        result["download_task_id"] = task_id
    
    logger.info(f"股票指标数据请求完成: stock_code={stock_code}")
    return result


@router.get("/{stock_code}/recent")
def get_recent_stock_data(
    stock_code: str,
    period: str = "1d",
    days: int = 180,  # 默认加载半年数据
    db: Session = Depends(get_db)
):
    """
    获取最近N天的数据（快速加载）

    参数:
        stock_code: 股票代码（短代码或完整代码）
        period: 时间周期，默认"1d"
        days: 回溯天数，默认180天（约半年）
        db: 数据库会话（由FastAPI依赖注入）

    返回值:
        List[Dict]: 最近N天的股票数据及技术指标列表

    调用关系:
        被调用: 前端HTTP GET /api/v1/indicators/{stock_code}/recent
        调用: IndicatorService.calculate_indicators_for_df_static

    关键逻辑:
        1. 若传入短代码，从StockCode表查询完整代码
        2. 计算start_date和end_date（当前日期回溯days天）
        3. 从数据库查询指定范围的数据
        4. 转换为DataFrame并计算技术指标
        5. 将结果转换为字典列表返回
    """
    from app.models.stock_data import StockData, StockCode
    from sqlalchemy import desc
    import pandas as pd

    # 将短代码转换为完整代码
    if '.' not in stock_code:
        code_record = db.query(StockCode).filter(StockCode.code == stock_code).first()
        if code_record:
            stock_code = code_record.name

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
    """
    分页获取历史数据（用于加载更多）

    参数:
        stock_code: 股票代码（短代码或完整代码）
        period: 时间周期，默认"1d"
        offset: 分页偏移量，默认0
        count: 每页数量，默认90条
        db: 数据库会话（由FastAPI依赖注入）

    返回值:
        Dict: 包含以下字段:
            - data: 股票数据及技术指标列表
            - total: 总记录数
            - offset: 下一页偏移量
            - has_more: 是否还有更多数据

    调用关系:
        被调用: 前端HTTP GET /api/v1/indicators/{stock_code}/paged
        调用: IndicatorService.calculate_indicators_for_df_static

    关键逻辑:
        1. 若传入短代码，从StockCode表查询完整代码
        2. 按时间倒序查询数据库，获取total总数
        3. 使用offset和limit分页
        4. 将分页结果按时间正序排序
        5. 转换为DataFrame并计算技术指标
        6. 组装分页信息返回
    """
    from app.models.stock_data import StockData, StockCode
    from sqlalchemy import desc
    import pandas as pd

    # 将短代码转换为完整代码
    if '.' not in stock_code:
        code_record = db.query(StockCode).filter(StockCode.code == stock_code).first()
        if code_record:
            stock_code = code_record.name

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
    """
    启动后台下载数据任务

    参数:
        stock_code: 股票代码
        period: 时间周期，默认"1d"
        download_all: 是否下载所有周期（1h/1d/1w/1M），默认False
        background_tasks: FastAPI后台任务管理器
        db: 数据库会话（由FastAPI依赖注入）

    返回值:
        Dict: 包含以下字段:
            - task_id: 后台任务ID
            - message: 状态消息
            - has_existing_data: 是否已有历史数据

    调用关系:
        被调用: 前端HTTP POST /api/v1/indicators/{stock_code}/download
        调用: StockService.get_stock_data, _download_task, _download_all_periods_task

    关键逻辑:
        1. 生成唯一task_id
        2. 检查是否已有数据
        3. 若download_all为True，启动全周期下载任务
        4. 若已有数据，启动增量更新任务
        5. 若无数据，启动全量下载任务
        6. 立即返回任务信息，下载在后台执行
    """
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
    """
    获取后台任务状态

    参数:
        task_id: 后台任务ID

    返回值:
        Dict: 任务状态信息，包含status/progress/message等字段
              若任务不存在返回{"status": "not_found", ...}

    调用关系:
        被调用: 前端HTTP GET /api/v1/indicators/task/{task_id}/status
        调用: 无（直接读取task_status字典）

    关键逻辑:
        1. 从task_status字典中查询任务状态
        2. 若不存在则返回not_found状态
    """
    status = task_status.get(task_id, {
        "status": "not_found",
        "progress": 0,
        "message": "任务不存在"
    })
    return status


def _download_task(stock_code: str, period: str, task_id: str, incremental: bool):
    """
    后台下载任务（单周期）

    参数:
        stock_code: 股票代码
        period: 时间周期
        task_id: 任务ID（用于更新任务状态）
        incremental: 是否增量更新（True只更新最近30天，False下载一年）

    返回值:
        无

    调用关系:
        被调用: download_stock_data 通过background_tasks.add_task启动
        调用: StockService.fetch_and_save_stock_data, IndicatorService.get_stock_data_with_indicators

    关键逻辑:
        1. 创建独立数据库会话
        2. 根据incremental决定日期范围
        3. 调用StockService下载并保存数据
        4. 触发IndicatorService计算技术指标
        5. 更新task_status状态为completed或error
        6. 确保数据库连接关闭
    """
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


def _merge_missing_ranges(missing_ranges: List[Dict]) -> List[Dict]:
    """
    合并相邻的缺失范围，减少API调用次数（实时接口范围不合并）

    参数:
        missing_ranges: 缺失数据范围列表，每项包含start/end/source字段

    返回值:
        List[Dict]: 合并后的缺失范围列表

    调用关系:
        被调用: _download_missing_ranges_task
        调用: datetime.strptime

    关键逻辑:
        1. 分离实时接口范围（source="realtime"）和历史接口范围
        2. 历史范围按start日期排序
        3. 遍历合并：若当前范围与上一个间隔<=3天则合并
        4. 实时范围不合并，直接追加到结果末尾
        5. 返回合并后的列表
    """
    if not missing_ranges or len(missing_ranges) <= 1:
        return missing_ranges

    # 分离实时接口范围和历史接口范围
    realtime_ranges = [r for r in missing_ranges if r.get("source") == "realtime"]
    history_ranges = [r for r in missing_ranges if r.get("source") != "realtime"]

    # 只合并历史接口范围
    if len(history_ranges) <= 1:
        merged_history = history_ranges
    else:
        sorted_history = sorted(history_ranges, key=lambda x: x["start"])
        merged_history = [sorted_history[0].copy()]

        for current in sorted_history[1:]:
            last = merged_history[-1]
            last_end = datetime.strptime(last["end"], "%Y-%m-%d").date()
            curr_start = datetime.strptime(current["start"], "%Y-%m-%d").date()

            if curr_start <= last_end + timedelta(days=3):
                last["end"] = max(last["end"], current["end"])
            else:
                merged_history.append(current.copy())

    # 实时接口范围不合并，直接追加
    return merged_history + realtime_ranges


def _download_missing_ranges_task(stock_code: str, period: str, missing_ranges: List[Dict], task_id: str):
    """
    后台下载缺失数据范围的任务（带WebSocket通知）

    参数:
        stock_code: 股票代码
        period: 时间周期
        missing_ranges: 缺失数据范围列表
        task_id: 任务ID

    返回值:
        无

    调用关系:
        被调用: get_stock_data_with_indicators 通过background_tasks.add_task启动
        调用: _merge_missing_ranges, StockService.fetch_and_save_stock_data, IndicatorService.get_stock_data_with_indicators, WebSocketManager

    关键逻辑:
        1. 合并相邻缺失范围减少API调用
        2. 遍历每个缺失范围，更新任务进度
        3. 通过WebSocket广播下载进度
        4. 根据source判断使用实时接口或历史接口
        5. 下载完成后计算技术指标
        6. 发送完成或错误WebSocket通知
        7. 确保数据库连接关闭
    """
    from app.core.database import SessionLocal
    from app.services.stock_service import StockService
    from app.services.indicator_service import IndicatorService
    from app.core.websocket_manager import manager
    import asyncio

    # 合并相邻的缺失范围
    original_count = len(missing_ranges)
    missing_ranges = _merge_missing_ranges(missing_ranges)
    merged_count = len(missing_ranges)
    if merged_count < original_count:
        logger.info(f"合并缺失范围: {original_count} 个 -> {merged_count} 个")

    logger.info(f"开始执行后台下载任务: task_id={task_id}, stock_code={stock_code}, period={period}, missing_ranges_count={merged_count}")

    db_local = SessionLocal()

    try:
        stock_service = StockService(db_local)
        indicator_service = IndicatorService(db_local)

        total_ranges = len(missing_ranges)
        logger.info(f"总共需要下载 {total_ranges} 个数据范围")

        for i, missing_range in enumerate(missing_ranges):
            logger.info(f"开始下载数据范围 {i + 1}/{total_ranges}: {missing_range['start']} 到 {missing_range['end']}")
            progress = int(10 + (i / total_ranges) * 80)
            task_status[task_id] = {
                "status": "downloading",
                "progress": progress,
                "message": f"正在下载缺失数据范围 ({i + 1}/{total_ranges}): {missing_range['start']} 到 {missing_range['end']}"
            }

            # 发送WebSocket通知
            def _send_websocket_notification():
                async def _broadcast():
                    logger.debug(f"发送WebSocket进度通知: task_id={task_id}, progress={progress}")
                    await manager.broadcast({
                        "type": "download_progress",
                        "data": {
                            "stock_code": stock_code,
                            "task_id": task_id,
                            "progress": progress,
                            "step": f"正在下载数据范围 ({i + 1}/{total_ranges}): {missing_range['start']} 到 {missing_range['end']}",
                            "message": f"正在下载缺失数据范围 ({i + 1}/{total_ranges}): {missing_range['start']} 到 {missing_range['end']}",
                            "status": "downloading",
                            "new_data_available": False
                        }
                    }, "realtime")

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_broadcast())
                finally:
                    loop.close()

            _send_websocket_notification()

            try:
                # 判断数据源类型：实时接口或历史接口
                range_source = missing_range.get("source", "history")

                if range_source == "realtime":
                    # 使用实时行情接口获取当天数据
                    logger.info(f"使用实时行情接口获取当天数据: {stock_code}")
                    saved = stock_service.fetch_and_save_stock_data(
                        stock_code=stock_code,
                        period=period,
                        source="realtime"
                    )
                else:
                    # 使用历史K线接口获取数据
                    logger.debug(f"调用fetch_and_save_stock_data: stock_code={stock_code}, period={period}, start_date={missing_range['start']}, end_date={missing_range['end']}")
                    saved = stock_service.fetch_and_save_stock_data(
                        stock_code=stock_code,
                        period=period,
                        start_date=datetime.strptime(missing_range["start"], "%Y-%m-%d").strftime("%Y%m%d"),
                        end_date=datetime.strptime(missing_range["end"], "%Y-%m-%d").strftime("%Y%m%d")
                    )

                logger.info(f"数据范围 {i + 1}/{total_ranges} 下载完成: {len(saved)} 条数据")

                # 计算新下载数据的技术指标
                logger.debug(f"开始计算技术指标: stock_code={stock_code}, period={period}, start_date={missing_range['start']}, end_date={missing_range['end']}")
                indicator_service.get_stock_data_with_indicators(
                    stock_code=stock_code,
                    period=period,
                    start_date=missing_range["start"],
                    end_date=missing_range["end"]
                )

            except Exception as e:
                logger.error(f"下载数据范围 {missing_range} 时出错: {e}", exc_info=True)
                continue

        logger.info(f"所有数据范围下载完成: task_id={task_id}, 总计 {total_ranges} 个范围")
        task_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": f"{total_ranges}个缺失数据范围下载完成",
            "new_data_available": True
        }

        # 发送完成通知
        def _send_completion_notification():
            async def _broadcast():
                logger.info(f"发送下载完成WebSocket通知: task_id={task_id}")
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "task_id": task_id,
                        "progress": 100,
                        "step": f"{total_ranges}个缺失数据范围下载完成",
                        "message": f"{total_ranges}个缺失数据范围下载完成",
                        "status": "completed",
                        "new_data_available": True
                    }
                }, "realtime")

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_broadcast())
            finally:
                loop.close()

        _send_completion_notification()

    except Exception as e:
        logger.error(f"后台下载任务执行失败: task_id={task_id}, error={e}", exc_info=True)
        task_status[task_id] = {
            "status": "error",
            "progress": 0,
            "message": f"下载失败: {str(e)}"
        }

        # 发送错误通知
        def _send_error_notification():
            async def _broadcast():
                logger.info(f"发送下载错误WebSocket通知: task_id={task_id}")
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "task_id": task_id,
                        "progress": 0,
                        "step": f"下载失败: {str(e)}",
                        "message": f"下载失败: {str(e)}",
                        "status": "error",
                        "new_data_available": False
                    }
                }, "realtime")

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_broadcast())
            finally:
                loop.close()

        _send_error_notification()

    finally:
        db_local.close()
        logger.info(f"后台下载任务完成并关闭数据库连接: task_id={task_id}")


def _download_missing_ranges_task(stock_code: str, period: str, missing_ranges: List[Dict], task_id: str):
    """后台下载缺失数据范围的任务"""
    from app.core.database import SessionLocal
    from app.services.stock_service import StockService
    
    db_local = SessionLocal()
    
    try:
        stock_service = StockService(db_local)
        indicator_service = IndicatorService(db_local)
        
        total_ranges = len(missing_ranges)
        
        for i, missing_range in enumerate(missing_ranges):
            progress = int(10 + (i / total_ranges) * 80)
            task_status[task_id] = {
                "status": "downloading",
                "progress": progress,
                "message": f"正在下载缺失数据范围 ({i + 1}/{total_ranges}): {missing_range['start']} 到 {missing_range['end']}"
            }
            
            try:
                # 判断数据源类型：实时接口或历史接口
                range_source = missing_range.get("source", "history")

                if range_source == "realtime":
                    # 使用实时行情接口获取当天数据
                    logger.info(f"使用实时行情接口获取当天数据: {stock_code}")
                    saved = stock_service.fetch_and_save_stock_data(
                        stock_code=stock_code,
                        period=period,
                        source="realtime"
                    )
                else:
                    # 使用历史K线接口获取数据
                    saved = stock_service.fetch_and_save_stock_data(
                        stock_code=stock_code,
                        period=period,
                        start_date=datetime.strptime(missing_range["start"], "%Y-%m-%d").strftime("%Y%m%d"),
                        end_date=datetime.strptime(missing_range["end"], "%Y-%m-%d").strftime("%Y%m%d")
                    )
                
                # 计算新下载数据的技术指标
                indicator_service.get_stock_data_with_indicators(
                    stock_code=stock_code,
                    period=period,
                    start_date=missing_range["start"],
                    end_date=missing_range["end"]
                )
                
            except Exception as e:
                logger.error(f"下载数据范围 {missing_range} 时出错: {e}", exc_info=True)
                continue
        
        task_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": f"{total_ranges}个缺失数据范围下载完成",
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
    """
    后台下载所有周期数据任务

    参数:
        stock_code: 股票代码
        task_id: 任务ID
        incremental: 是否增量更新

    返回值:
        无

    调用关系:
        被调用: download_stock_data 当download_all=True时启动
        调用: StockService.fetch_and_save_stock_data, IndicatorService.get_stock_data_with_indicators

    关键逻辑:
        1. 创建独立数据库会话
        2. 定义需要下载的周期列表：["1h", "1d", "1w", "1M"]
        3. 遍历每个周期，更新任务进度和状态
        4. 根据incremental决定日期范围
        5. 逐个周期下载数据并计算指标
        6. 任一周期出错记录日志但继续其他周期
        7. 更新task_status为completed或error
        8. 确保数据库连接关闭
    """
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
                logger.error(f"下载{period}周期数据时出错: {e}", exc_info=True)
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
    """
    获取技术指标交易信号

    参数:
        stock_code: 股票代码（短代码或完整代码）
        indicator_type: 指标类型，"all"/"kdj"/"macd"，默认"all"
        db: 数据库会话（由FastAPI依赖注入）

    返回值:
        Dict: 包含signals字段的交易信号列表

    调用关系:
        被调用: 前端HTTP GET /api/v1/indicators/signals/{stock_code}
        调用: IndicatorService.get_kdj_signals/get_macd_signals/get_all_signals

    关键逻辑:
        1. 若传入短代码，从StockCode表查询完整代码
        2. 查询最近500条日线数据
        3. 转换为DataFrame并排序
        4. 根据indicator_type调用对应信号计算方法
        5. 返回交易信号列表
    """
    from app.models.stock_data import StockData, StockCode
    from sqlalchemy import desc
    import pandas as pd

    # 将短代码转换为完整代码
    if '.' not in stock_code:
        code_record = db.query(StockCode).filter(StockCode.code == stock_code).first()
        if code_record:
            stock_code = code_record.name

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