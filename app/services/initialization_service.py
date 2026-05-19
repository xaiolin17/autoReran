import threading
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.indicator_service import IndicatorService
from app.services.stock_service import StockService


def _send_progress_ws(
    stock_code: str,
    status: str,
    progress: int,
    message: str,
    new_data_available: bool = False,
):
    import asyncio

    from app.core.websocket_manager import manager

    async def _broadcast():
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
    except Exception:
        pass  # Silently ignore WebSocket errors


def _run_initialization_task():
    from app.core.database import SessionLocal

    stock_code = "000001.SH"
    period = "1d"

    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)

        # 获取完整代码（带后缀），因为数据库中保存的是完整代码
        full_symbol = service.get_full_symbol(stock_code)
        display_code = full_symbol if full_symbol else stock_code

        # 使用完整代码查询最新日期
        latest_date = service.get_latest_date(display_code, period)
        today = datetime.now().date()

        start_date_str: Optional[str] = None
        end_date_str: Optional[str] = None

        if latest_date is None:
            one_month_ago = today - timedelta(days=30)
            start_date_str = one_month_ago.strftime("%Y%m%d")
            end_date_str = today.strftime("%Y%m%d")
            _send_progress_ws(stock_code, "downloading", 10, f"Downloading: {one_month_ago} ~ {today}")
        else:
            latest_date_only = latest_date.date()
            if latest_date_only >= today:
                _send_progress_ws(
                    stock_code,
                    "completed",
                    100,
                    f"数据已是最新 (截至 {latest_date_only})",
                    False,
                )
                return

            start_date_str = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
            end_date_str = today.strftime("%Y%m%d")
            _send_progress_ws(
                stock_code,
                "downloading",
                10,
                f"下载中: {start_date_str} ~ {end_date_str}",
            )

        if start_date_str is None:
            return

        # 判断是否需要获取今天的数据：如果是当天单独获取，使用实时接口
        today_str = today.strftime("%Y%m%d")
        if start_date_str == end_date_str == today_str:
            _send_progress_ws(stock_code, "downloading", 20, f"获取今日实时数据: {today_str}")
            saved_data = service.fetch_and_save_stock_data(
                stock_code,
                period,
                start_date=start_date_str,
                end_date=end_date_str,
                source="realtime",
            )
        else:
            # 使用短代码调用（内部会自动映射为完整代码）
            saved_data = service.fetch_and_save_stock_data(
                stock_code, period, start_date=start_date_str, end_date=end_date_str
            )

        if saved_data:
            _send_progress_ws(
                stock_code,
                "calculating",
                70,
                f"已下载 {len(saved_data)} 条记录，正在计算指标...",
            )

            indicator_service.calculate_and_save_indicators(stock_code, period)

            _send_progress_ws(
                stock_code,
                "completed",
                100,
                f"初始化完成，{len(saved_data)} 条新记录",
                True,
            )
        else:
            _send_progress_ws(stock_code, "completed", 100, "未获取到新数据 (非交易日)", False)

    except Exception as e:
        logger.error(f"初始化任务错误: {e}", exc_info=True)
        _send_progress_ws(stock_code, "error", 0, f"初始化失败: {str(e)}")
    finally:
        db.close()


class InitializationService:
    def __init__(self, db: Session):
        self.db = db

    def check_and_initialize_default_data(self):
        try:
            StockService(self.db)

            thread = threading.Thread(target=_run_initialization_task, daemon=True)
            thread.start()
            logger.info("数据新鲜度检查已开始 (后台运行)")

            return True
        except Exception as e:
            logger.error(f"初始化服务错误: {e}", exc_info=True)
            return False

    def check_and_initialize_default_data_sync(self):
        try:
            stock_service = StockService(self.db)
            indicator_service = IndicatorService(self.db)

            default_stock_code = "000001.SH"

            # 先清理可能的重复数据
            dedup_count = stock_service.deduplicate_stock_data(default_stock_code, "1d")
            if dedup_count > 0:
                logger.info(f"启动时清理了 {dedup_count} 条重复数据")

            has_data = stock_service.has_data(default_stock_code, "1d")

            if not has_data:
                success = stock_service.initialize_default_data(default_stock_code)

                if success:
                    indicator_service.calculate_and_save_indicators(default_stock_code, "1d")
                else:
                    logger.warning("默认数据初始化失败 (网络问题)")

            return True
        except Exception as e:
            logger.error(f"初始化服务错误: {e}", exc_info=True)
            return False
