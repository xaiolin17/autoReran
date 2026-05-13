import threading
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.services.stock_service import StockService
from app.services.indicator_service import IndicatorService
from app.core.logger import logger


def _send_progress_ws(stock_code: str, status: str, progress: int, message: str, new_data_available: bool = False):
    import asyncio
    
    async def _broadcast():
        from app.core.websocket_manager import manager
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
        pass


def _run_initialization_task():
    from app.core.database import SessionLocal
    
    stock_code = "000001"
    period = "1d"
    
    db = SessionLocal()
    try:
        service = StockService(db)
        indicator_service = IndicatorService(db)
        
        logger.info("检查数据新鲜度...")
        
        latest_date = service.get_latest_date(stock_code, period)
        today = datetime.now().date()
        
        start_date_str: Optional[str] = None
        end_date_str: Optional[str] = None
        
        if latest_date is None:
            logger.info(f"股票 {stock_code} 无数据，下载最近1个月")
            one_month_ago = today - timedelta(days=30)
            start_date_str = one_month_ago.strftime("%Y%m%d")
            end_date_str = today.strftime("%Y%m%d")
            _send_progress_ws(stock_code, "downloading", 10, f"Downloading: {one_month_ago} ~ {today}")
        else:
            latest_date_only = latest_date.date()
            if latest_date_only >= today:
                logger.info(f"数据已是最新 (截至 {latest_date_only})")
                _send_progress_ws(stock_code, "completed", 100, f"数据已是最新 (截至 {latest_date_only})", False)
                return
            
            start_date_str = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
            end_date_str = today.strftime("%Y%m%d")
            logger.info(f"发现旧数据 (截至 {latest_date_only})，更新 {start_date_str} ~ {end_date_str}")
            _send_progress_ws(stock_code, "downloading", 10, f"下载中: {start_date_str} ~ {end_date_str}")
        
        if start_date_str is None:
            return
        
        saved_data = service.fetch_and_save_stock_data(
            stock_code, period, start_date=start_date_str, end_date=end_date_str
        )
        
        if saved_data:
            logger.info(f"已下载 {len(saved_data)} 条记录")
            _send_progress_ws(stock_code, "calculating", 70, f"已下载 {len(saved_data)} 条记录，正在计算指标...")
            
            indicator_service.calculate_and_save_indicators(stock_code, period)
            
            logger.info("指标计算完成")
            _send_progress_ws(stock_code, "completed", 100, f"初始化完成，{len(saved_data)} 条新记录", True)
        else:
            logger.info("未获取到新数据 (网络问题或非交易日)")
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
            stock_service = StockService(self.db)
            
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
            
            default_stock_code = "000001"
            
            has_data = stock_service.has_data(default_stock_code, "1d")
            
            if not has_data:
                logger.info(f"正在初始化默认数据: 上证指数 ({default_stock_code})...")
                success = stock_service.initialize_default_data(default_stock_code)
                
                if success:
                    logger.info(f"默认数据初始化完成，正在计算指标...")
                    indicator_service.calculate_and_save_indicators(default_stock_code, "1d")
                    logger.info(f"指标计算完成")
                else:
                    logger.warning(f"默认数据初始化失败 (网络问题)")
            else:
                logger.info(f"默认数据已存在: {default_stock_code}")
            
            return True
        except Exception as e:
            logger.error(f"初始化服务错误: {e}", exc_info=True)
            return False