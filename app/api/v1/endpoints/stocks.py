import threading
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logger import logger
from app.models.stock_data import StockData as StockDataModel
from app.schemas.stock import StockData, StockDataCreate
from app.services.indicator_service import IndicatorService
from app.services.stock_service import StockService

router = APIRouter()


class MarkUpdate(BaseModel):
    """
    标记更新请求模型（旧版，用于兼容）

    字段说明:
        date (str): 日期字符串，格式为 YYYY-MM-DD，表示要标记的日期
        label (Optional[str]): 标记标签，可选，用于给指定日期打标签
    """

    date: str
    label: Optional[str] = None


# ============================================================
# 1. 根路由 (无 path parameters)
# ============================================================
@router.get("/")
def get_available_stocks(db: Session = Depends(get_db)):
    """
    获取系统中所有可用的股票列表

    参数说明:
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"stocks": [...]}，其中 stocks 为股票代码列表

    API路径和HTTP方法:
        GET /api/v1/stocks/

    调用关系:
        被前端股票选择器/下拉框组件调用，用于展示可选股票

    关键逻辑说明:
        调用 StockService.get_available_stocks() 从数据库获取所有已注册的股票代码
    """
    service = StockService(db)
    stocks = service.get_available_stocks()
    return {"stocks": stocks}


@router.post("/", response_model=StockData)
def create_stock_data(stock_data: StockDataCreate, db: Session = Depends(get_db)):
    """
    手动创建单条股票数据记录

    参数说明:
        stock_data (StockDataCreate): 要创建的股票数据，包含股票代码、日期、开盘价、收盘价等字段
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        StockData: 创建成功后的股票数据对象

    API路径和HTTP方法:
        POST /api/v1/stocks/

    调用关系:
        被前端数据录入/管理后台调用，用于手动补录股票数据

    关键逻辑说明:
        调用 StockService.create_stock_data() 将数据写入数据库
    """
    service = StockService(db)
    return service.create_stock_data(stock_data)


# ============================================================
# 2. 股票代码搜索接口 (模糊查询)
# ============================================================
@router.get("/search")
def search_stocks(keyword: str, limit: int = 20, db: Session = Depends(get_db)):
    """
    模糊查询股票代码，返回匹配的代码列表

    参数说明:
        keyword (str): 搜索关键词，支持股票代码或名称的模糊匹配
        limit (int): 返回结果的最大数量，默认为20条
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"results": [...], "count": int}，results 为匹配的股票列表，count 为结果数量

    API路径和HTTP方法:
        GET /api/v1/stocks/search

    调用关系:
        被前端搜索框/自动补全组件调用，用于用户输入时实时提示匹配的股票

    关键逻辑说明:
        调用 StockService.search_stock_codes() 进行模糊查询，支持按代码或名称匹配
    """
    service = StockService(db)
    results = service.search_stock_codes(keyword, limit=limit)
    return {"results": results, "count": len(results)}


# ============================================================
# 3. 标记相关接口 (使用查询参数，避免 path parameter 冲突)
# ============================================================
class MarkUpdateV2(BaseModel):
    """
    标记更新请求模型（新版）

    字段说明:
        stock_code (str): 股票代码，支持短代码或完整代码
        date (str): 日期字符串，格式为 YYYY-MM-DD，表示要标记的日期
        label (Optional[str]): 标记标签，可选，用于给指定日期打标签
    """

    stock_code: str
    date: str
    label: Optional[str] = None


@router.get("/marks")
def get_marks(stock_code: str, period: str = "1d", db: Session = Depends(get_db)):
    """
    获取指定股票和周期的所有标记数据

    参数说明:
        stock_code (str): 股票代码，支持短代码（如 000001）或完整代码（如 000001.SZ）
        period (str): 数据周期，默认为 "1d"（日线），可选其他周期
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        list[dict]: 每个元素包含 datetime（ISO格式日期时间字符串）和 label（标记标签）

    API路径和HTTP方法:
        GET /api/v1/stocks/marks

    调用关系:
        被前端K线图/标记管理页面调用，用于展示用户在图表上打的标记

    关键逻辑说明:
        1. 如果传入的是短代码，自动查询 StockCode 表转换为完整代码
        2. 从 StockDataModel 表中筛选指定股票、周期且 label 不为空的记录
        3. 将 datetime 字段统一转换为 ISO 格式字符串返回
    """
    from app.models.stock_data import StockCode

    # 将短代码转换为完整代码
    if "." not in stock_code:
        code_record = db.query(StockCode).filter(StockCode.code == stock_code).first()
        if code_record:
            stock_code = code_record.name

    marks = (
        db.query(StockDataModel)
        .filter(
            StockDataModel.stock_code == stock_code,
            StockDataModel.period == period,
            StockDataModel.label.isnot(None),
        )
        .all()
    )

    result = []
    for mark in marks:
        result.append(
            {
                "datetime": (mark.datetime.isoformat() if hasattr(mark.datetime, "isoformat") else str(mark.datetime)),
                "label": mark.label,
            }
        )

    return result


@router.put("/mark")
def update_mark(
    mark_data: MarkUpdateV2,
    period: str = "1d",
    db: Session = Depends(get_db),
):
    """
    更新指定股票某一天的标记标签

    参数说明:
        mark_data (MarkUpdateV2): 标记更新请求体，包含股票代码、日期和标签
        period (str): 数据周期，默认为 "1d"（日线）
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"message": str, "stock_code": str,
               "date": str, "label": str}，表示更新结果

    API路径和HTTP方法:
        PUT /api/v1/stocks/mark

    调用关系:
        被前端K线图的标记编辑功能调用，用于用户添加、修改或删除某日的标记

    关键逻辑说明:
        1. 将 date 字符串解析为 date 对象，格式必须为 YYYY-MM-DD
        2. 如果传入的是短代码，自动查询 StockCode 表转换为完整代码
        3. 在数据库中查找该股票、周期、日期范围内的第一条记录
        4. 更新该记录的 label 字段并提交事务
    """
    date_str = mark_data.date

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format: " + date_str + ". Use YYYY-MM-DD",
        )

    next_date = target_date + timedelta(days=1)

    stock_code = mark_data.stock_code
    from app.models.stock_data import StockCode

    if "." not in stock_code:
        code_record = db.query(StockCode).filter(StockCode.code == stock_code).first()
        if code_record:
            stock_code = code_record.name

    record = (
        db.query(StockDataModel)
        .filter(
            StockDataModel.stock_code == stock_code,
            StockDataModel.period == period,
            StockDataModel.datetime >= target_date,
            StockDataModel.datetime < next_date,
        )
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Record not found for date " + date_str,
        )

    record.label = mark_data.label
    db.commit()

    return {
        "message": "Mark updated successfully",
        "stock_code": mark_data.stock_code,
        "date": date_str,
        "label": mark_data.label,
    }


@router.post("/fetch/{stock_code}")
def fetch_and_save_stock_data(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    同步获取并保存指定股票的历史数据

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        start_date (Optional[str]): 开始日期，格式 YYYYMMDD，可选
        end_date (Optional[str]): 结束日期，格式 YYYYMMDD，可选
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"message": str, "count": int,
               "start_date": str, "end_date": str}，表示保存结果

    API路径和HTTP方法:
        POST /api/v1/stocks/fetch/{stock_code}

    调用关系:
        被前端数据管理/手动下载按钮调用，用于同步下载指定范围的股票数据

    关键逻辑说明:
        调用 StockService.fetch_and_save_stock_data() 从外部数据源（TickFlow）获取数据并保存到数据库
    """
    service = StockService(db)
    saved_data = service.fetch_and_save_stock_data(stock_code, period, start_date, end_date)
    return {
        "message": "Successfully saved " + str(len(saved_data)) + " records",
        "count": len(saved_data),
        "start_date": start_date,
        "end_date": end_date,
    }


@router.post("/fetch-async/{stock_code}")
def fetch_async(
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    异步启动后台线程下载指定范围的股票数据，并通过 WebSocket 实时通知进度

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        start_date (Optional[str]): 开始日期，格式 YYYYMMDD，可选
        end_date (Optional[str]): 结束日期，格式 YYYYMMDD，可选
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"message": str, "stock_code": str,
               "start_date": str, "end_date": str}，表示下载已启动

    API路径和HTTP方法:
        POST /api/v1/stocks/fetch-async/{stock_code}

    调用关系:
        被前端数据下载/初始化按钮调用，用于异步下载股票数据并展示进度条

    关键逻辑说明:
        1. 记录日志并启动后台线程执行 _run_fetch_task
        2. 通过 WebSocket 向客户端推送下载进度
           （downloading -> calculating -> completed/error）
        3. 下载完成后自动计算技术指标
    """
    logger.info(
        "接收到异步下载请求: stock_code="
        + stock_code
        + ", period="
        + period
        + ", start_date="
        + str(start_date)
        + ", end_date="
        + str(end_date)
    )

    thread = threading.Thread(
        target=_run_fetch_task,
        args=(stock_code, period, start_date, end_date),
        daemon=True,
    )
    thread.start()

    logger.info("后台下载线程已启动: stock_code=" + stock_code)
    return {
        "message": "Download started",
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date,
    }


@router.get("/latest/{stock_code}", response_model=Optional[StockData])
def get_latest_stock_data(
    stock_code: str,
    period: str = "1d",
    db: Session = Depends(get_db),
):
    """
    获取指定股票的最新一条数据记录

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        Optional[StockData]: 最新的股票数据对象，如果没有数据则返回 None

    API路径和HTTP方法:
        GET /api/v1/stocks/latest/{stock_code}

    调用关系:
        被前端数据状态显示/最新数据展示组件调用，用于显示该股票最新行情

    关键逻辑说明:
        调用 StockService.get_latest_stock_data() 查询数据库中该股票、周期的最新记录
    """
    service = StockService(db)
    return service.get_latest_stock_data(stock_code, period)


@router.post("/refresh/{stock_code}")
def refresh_stock_data(
    stock_code: str,
    period: str = "1d",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    增量刷新指定股票的数据，自动判断是否需要更新并启动后台任务

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        background_tasks (BackgroundTasks): FastAPI 后台任务对象（当前未使用，采用线程方式）
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"message": str, "stock_code": str,
               "period": str, "incremental": bool}，表示刷新状态

    API路径和HTTP方法:
        POST /api/v1/stocks/refresh/{stock_code}

    调用关系:
        被前端"更新数据"按钮调用，用于增量更新股票数据到最新日期

    关键逻辑说明:
        1. 查询数据库获取该股票最新数据的日期
        2. 如果最新日期 >= 今天，说明已是最新，无需更新
        3. 如果最新日期 < 今天，计算增量开始日期（最新日期+1天）
        4. 如果没有现有数据，将下载完整历史数据
        5. 启动后台线程执行 _run_refresh_task 进行异步刷新
    """
    service = StockService(db)
    latest_date = service.get_latest_date(stock_code, period)

    start_date_str = None
    if latest_date:
        latest_date_only = latest_date.date()
        today = datetime.now().date()
        if latest_date_only >= today:
            message = "已有数据已是最新 (截止 " + str(latest_date_only) + ")，无需更新"
        else:
            start_date_str = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
            message = "发现现有数据，从 " + start_date_str + " 开始增量更新"
    else:
        message = "没有现有数据，将下载完整数据"

    thread = threading.Thread(
        target=_run_refresh_task,
        args=(stock_code, period, start_date_str),
        daemon=True,
    )
    thread.start()

    return {
        "message": message,
        "stock_code": stock_code,
        "period": period,
        "incremental": latest_date is not None,
    }


@router.post("/force-refresh/{stock_code}")
def force_refresh_stock_data(
    stock_code: str,
    period: str = "1d",
    db: Session = Depends(get_db),
):
    """
    强制刷新指定股票的历史数据，下载完整数据并对比更新数据库

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"message": str, "stock_code": str, "period": str}，表示强制刷新已启动

    API路径和HTTP方法:
        POST /api/v1/stocks/force-refresh/{stock_code}

    调用关系:
        被前端"强制刷新"按钮调用，用于数据异常时重新下载完整历史数据

    关键逻辑说明:
        1. 启动后台线程执行 _run_force_refresh_task
        2. 下载过去2年的完整历史数据
        3. force=True 表示对比更新所有数据字段（下载数据为空则不更新该字段）
        4. 刷新完成后自动重新计算技术指标
    """

    # 启动后台任务重新下载并对比更新
    thread = threading.Thread(
        target=_run_force_refresh_task,
        args=(stock_code, period),
        daemon=True,
    )
    thread.start()

    return {
        "message": "开始强制刷新历史数据，将下载完整数据并对比更新",
        "stock_code": stock_code,
        "period": period,
    }


@router.post("/deduplicate/{stock_code}")
def deduplicate_stock_data(
    stock_code: str,
    period: str = "1d",
    db: Session = Depends(get_db),
):
    """
    手动清理指定股票代码和周期的重复数据，保留最早插入的记录

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        dict: {"message": str, "stock_code": str,
               "period": str, "deleted_count": int}，表示清理结果

    API路径和HTTP方法:
        POST /api/v1/stocks/deduplicate/{stock_code}

    调用关系:
        被前端数据管理/维护工具调用，用于清理因重复下载产生的冗余数据

    关键逻辑说明:
        调用 StockService.deduplicate_stock_data() 按股票代码、周期、日期去重，保留最早插入的记录
    """
    service = StockService(db)
    deleted_count = service.deduplicate_stock_data(stock_code, period)
    return {
        "message": ("已清理 " + str(deleted_count) + " 条重复数据" if deleted_count > 0 else "没有重复数据"),
        "stock_code": stock_code,
        "period": period,
        "deleted_count": deleted_count,
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
    db: Session = Depends(get_db),
):
    """
    获取指定股票的历史K线数据

    参数说明:
        stock_code (str): 股票代码，URL路径参数
        period (str): 数据周期，默认为 "1d"（日线）
        start_date (Optional[datetime]): 开始日期时间，可选，用于筛选数据范围
        end_date (Optional[datetime]): 结束日期时间，可选，用于筛选数据范围
        limit (Optional[int]): 返回记录数量限制，可选
        db (Session): 数据库会话对象，通过依赖注入获取

    返回值说明:
        List[StockData]: 股票数据列表，每条数据包含日期、开盘价、收盘价、最高价、最低价、成交量等

    API路径和HTTP方法:
        GET /api/v1/stocks/{stock_code}

    调用关系:
        被前端K线图/股票详情页调用，用于绘制K线图和展示历史行情

    关键逻辑说明:
        调用 StockService.get_stock_data() 从数据库查询指定股票、周期、日期范围的数据，支持分页限制
    """
    service = StockService(db)
    return service.get_stock_data(stock_code, period, start_date, end_date, limit)


# ============================================================
# 辅助函数
# ============================================================
def _send_progress_ws(
    stock_code: str,
    status: str,
    progress: int,
    message: str,
    new_data_available: bool = False,
):
    """
    线程安全的 WebSocket 进度通知函数

    参数说明:
        stock_code (str): 股票代码，用于标识当前下载任务
        status (str): 下载状态，可选值：downloading（下载中）、
                       calculating（计算中）、completed（完成）、error（错误）
        progress (int): 进度百分比，0-100
        message (str): 进度描述信息，用于前端展示
        new_data_available (bool): 是否有新数据可用，用于通知前端刷新图表，默认为 False

    返回值说明:
        无返回值

    调用关系:
        被 _run_fetch_task、_run_refresh_task、_run_force_refresh_task 等后台任务调用

    关键逻辑说明:
        1. 检查当前是否有运行的事件循环，如果有则使用 asyncio.run_coroutine_threadsafe 调度广播任务
        2. 如果没有事件循环，则创建新的事件循环执行广播
        3. 通过 WebSocket manager 向 realtime 频道广播下载进度消息
        4. 发送失败时静默忽略，避免影响主任务
    """
    logger.debug(
        "发送WebSocket进度通知: stock_code="
        + stock_code
        + ", status="
        + status
        + ", progress="
        + str(progress)
        + ", message="
        + message
    )
    import asyncio

    from app.core.websocket_manager import manager

    async def _broadcast():
        logger.debug("开始广播WebSocket消息到realtime频道")
        await manager.broadcast(
            {
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": status,
                    "progress": progress,
                    "message": message,
                    "new_data_available": new_data_available,
                },
            },
            channel="realtime",
        )

    try:
        # 检查当前是否有运行的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 在当前事件循环中调度任务
            future = asyncio.run_coroutine_threadsafe(_broadcast(), loop)
            # 等待任务完成
            future.result(timeout=5.0)  # 5秒超时
        except RuntimeError:
            # 没有运行的事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_broadcast())
            loop.close()
        logger.debug("WebSocket进度通知发送成功: " + message)
    except Exception as e:
        logger.warning("WebSocket进度通知发送失败: " + str(e))
        pass  # Silently ignore WebSocket errors


def _run_fetch_task(
    stock_code: str,
    period: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    后台下载指定范围股票数据的任务函数

    参数说明:
        stock_code (str): 股票代码
        period (str): 数据周期，如 "1d"
        start_date (Optional[str]): 开始日期，格式 YYYYMMDD，可选
        end_date (Optional[str]): 结束日期，格式 YYYYMMDD，可选

    返回值说明:
        无返回值

    调用关系:
        被 fetch_async 路由函数启动为后台线程调用

    关键逻辑说明:
        1. 创建独立的数据库会话（SessionLocal）
        2. 发送 downloading 进度通知（10%）
        3. 调用 StockService.fetch_and_save_stock_data() 从 TickFlow 获取并保存数据
        4. 如果有新数据，发送 calculating 进度通知（70%），
           并调用 IndicatorService.calculate_and_save_indicators() 计算技术指标
        5. 发送 completed 进度通知（100%），new_data_available=True 通知前端刷新
        6. 异常时发送 error 进度通知
    """
    from app.core.database import SessionLocal

    logger.info(
        "开始执行后台下载任务: stock_code="
        + stock_code
        + ", period="
        + period
        + ", start_date="
        + str(start_date)
        + ", end_date="
        + str(end_date)
    )

    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)

        logger.debug("发送下载开始进度通知")
        _send_progress_ws(stock_code, "downloading", 10, "正在从 TickFlow 获取数据...")

        logger.debug("开始获取并保存股票数据")
        saved_data = service.fetch_and_save_stock_data(stock_code, period, start_date=start_date, end_date=end_date)

        if saved_data:
            logger.info("数据下载完成，开始计算技术指标: " + str(len(saved_data)) + " 条数据")
            _send_progress_ws(stock_code, "calculating", 70, "正在计算技术指标...")
            indicator_service.calculate_and_save_indicators(stock_code, period)
            logger.info("技术指标计算完成")
            _send_progress_ws(
                stock_code,
                "completed",
                100,
                "下载完成，新增 " + str(len(saved_data)) + " 条数据",
                True,
            )
        else:
            logger.info("下载完成，无新数据")
            _send_progress_ws(stock_code, "completed", 100, "无新数据", False)
    except Exception as e:
        logger.error("后台下载任务失败: " + str(e), exc_info=True)
        _send_progress_ws(stock_code, "error", 0, "下载失败: " + str(e))
    finally:
        db.close()
        logger.info("后台下载任务完成并关闭数据库连接: stock_code=" + stock_code)


def _run_refresh_task(stock_code: str, period: str, start_date: Optional[str] = None):
    """
    后台增量刷新股票数据的任务函数

    参数说明:
        stock_code (str): 股票代码
        period (str): 数据周期，如 "1d"
        start_date (Optional[str]): 增量开始日期，格式 YYYYMMDD，可选

    返回值说明:
        无返回值

    调用关系:
        被 refresh_stock_data 路由函数启动为后台线程调用

    关键逻辑说明:
        1. 创建独立的数据库会话（SessionLocal）
        2. 发送 downloading 进度通知（10%）
        3. 调用 StockService.fetch_and_save_stock_data(incremental=True) 增量获取数据
        4. 如果有新数据，计算技术指标并发送 completed 通知
        5. 如果没有新数据，发送"已是最新数据"通知
        6. 异常时发送 error 进度通知
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)

        _send_progress_ws(stock_code, "downloading", 10, "正在从 TickFlow 获取数据...")

        saved_data = service.fetch_and_save_stock_data(stock_code, period, start_date=start_date, incremental=True)

        if saved_data:
            _send_progress_ws(stock_code, "calculating", 70, "正在计算技术指标...")
            indicator_service.calculate_and_save_indicators(stock_code, period)
            _send_progress_ws(
                stock_code,
                "completed",
                100,
                "刷新完成，新增 " + str(len(saved_data)) + " 条数据",
                True,
            )
        else:
            _send_progress_ws(
                stock_code,
                "completed",
                100,
                "已是最新数据，无需更新",
                False,
            )
    except Exception as e:
        _send_progress_ws(stock_code, "error", 0, "刷新失败: " + str(e))
    finally:
        db.close()


def _run_force_refresh_task(stock_code: str, period: str):
    """
    后台强制刷新股票历史数据的任务函数，下载完整数据并对比更新

    参数说明:
        stock_code (str): 股票代码
        period (str): 数据周期，如 "1d"

    返回值说明:
        无返回值

    调用关系:
        被 force_refresh_stock_data 路由函数启动为后台线程调用

    关键逻辑说明:
        1. 创建独立的数据库会话（SessionLocal）
        2. 发送 downloading 进度通知（10%）
        3. 计算日期范围：过去2年（730天）到今天
        4. 调用 StockService.fetch_and_save_stock_data(
           incremental=False, force=True) 强制下载完整数据并对比更新
        5. 如果有数据更新，计算技术指标并发送 completed 通知
        6. 如果没有数据更新，发送"无数据更新"通知
        7. 异常时发送 error 进度通知
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)

        _send_progress_ws(
            stock_code,
            "downloading",
            10,
            "正在强制刷新，从 TickFlow 获取完整历史数据...",
        )

        # 强制刷新：获取过去2年的完整历史数据，force=True 表示对比更新所有数据
        # 将日期范围对齐到交易日，避免请求非交易日的数据
        try:
            import exchange_calendars as ec

            calendar = ec.get_calendar("XSHG")
            today = date.today()
            start_dt = today - timedelta(days=730)
            # 找到最近的交易日
            end_date = calendar.session_offset(today, 0).strftime("%Y%m%d")
            start_date = calendar.session_offset(start_dt, 0).strftime("%Y%m%d")
        except Exception:
            # fallback: 不使用交易日对齐
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        saved_data = service.fetch_and_save_stock_data(
            stock_code,
            period,
            start_date=start_date,
            end_date=end_date,
            incremental=False,
            force=True,
        )

        if saved_data:
            _send_progress_ws(stock_code, "calculating", 70, "正在计算技术指标...")
            indicator_service.calculate_and_save_indicators(stock_code, period)
            _send_progress_ws(
                stock_code,
                "completed",
                100,
                "强制刷新完成，共处理 " + str(len(saved_data)) + " 条数据",
                True,
            )
        else:
            _send_progress_ws(
                stock_code,
                "completed",
                100,
                "强制刷新完成，无数据更新",
                False,
            )
    except Exception as e:
        _send_progress_ws(stock_code, "error", 0, "强制刷新失败: " + str(e))
    finally:
        db.close()
