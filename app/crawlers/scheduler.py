from datetime import datetime, timedelta
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import desc

from app.core.database import SessionLocal
from app.core.logger import logger
from app.crawlers.data_processor import DataProcessor
from app.crawlers.tickflow_crawler import TickFlowCrawler
from app.models.stock_data import StockCode, StockData


class CrawlerScheduler:
    def __init__(self, db=None):
        self.scheduler = BackgroundScheduler()
        self.tickflow_crawler = TickFlowCrawler(db=db)
        self.data_processor = DataProcessor()
        self.monitored_stocks: List[str] = []
        self.is_running = False

    def add_stock(self, stock_code: str):
        if stock_code not in self.monitored_stocks:
            self.monitored_stocks.append(stock_code)
            logger.info(f"添加监控股票: {stock_code}")

    def remove_stock(self, stock_code: str):
        if stock_code in self.monitored_stocks:
            self.monitored_stocks.remove(stock_code)
            logger.info(f"移除监控股票: {stock_code}")

    def start(self, interval_minutes: int = 5):
        if self.is_running:
            logger.warning("调度器已在运行")
            return

        self.scheduler.add_job(
            self._crawl_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="stock_crawl_job",
            name="Stock Data Crawling",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info(f"调度器已启动，间隔: {interval_minutes}分钟")

    def stop(self):
        if not self.is_running:
            logger.warning("调度器未运行")
            return

        self.scheduler.shutdown()
        self.is_running = False
        logger.info("调度器已停止")

    def _crawl_job(self):
        logger.info(f"开始爬取任务，时间: {datetime.now()}")

        for stock_code in self.monitored_stocks:
            try:
                self._crawl_single_stock(stock_code)
            except Exception as e:
                logger.error(f"爬取股票 {stock_code} 失败: {e}")

    def _crawl_single_stock(self, stock_code: str):
        # 获取最新日期，做增量更新
        db = SessionLocal()
        try:
            # 将短代码转换为完整代码
            query_code = stock_code
            if "." not in stock_code:
                code_record = db.query(StockCode).filter(StockCode.code == stock_code).first()
                if code_record:
                    query_code = code_record.name

            latest = (
                db.query(StockData)
                .filter(StockData.stock_code == query_code, StockData.period == "1d")
                .order_by(desc(StockData.datetime))
                .first()
            )

            start_date = None
            if latest:
                start_date = (latest.datetime + timedelta(days=1)).strftime("%Y%m%d")

            tickflow_data = self.tickflow_crawler.fetch_stock_data(stock_code, period="1d", start_date=start_date)

            if not tickflow_data.empty:
                cleaned_data = self.data_processor.clean_data(tickflow_data)
                self._save_to_database(cleaned_data)
                logger.info(f"股票 {stock_code} 数据已保存: {len(cleaned_data)}条")
        finally:
            db.close()

    def _save_to_database(self, df):
        if df.empty:
            return

        db = SessionLocal()
        try:
            for _, row in df.iterrows():
                existing = (
                    db.query(StockData)
                    .filter(
                        StockData.stock_code == row["stock_code"],
                        StockData.period == row["period"],
                        StockData.datetime == row["datetime"],
                    )
                    .first()
                )

                if not existing:
                    stock_data = StockData(
                        stock_code=row["stock_code"],
                        stock_name=row.get("stock_name"),
                        period=row["period"],
                        datetime=row["datetime"],
                        open_price=row["open_price"],
                        high_price=row["high_price"],
                        low_price=row["low_price"],
                        close_price=row["close_price"],
                        volume=row["volume"],
                        amount=row.get("amount"),
                        source=row.get("source", "tickflow"),
                    )
                    db.add(stock_data)
                else:
                    # 检查数据是否有变化，有则更新
                    fields = [
                        ("open_price", row.get("open_price")),
                        ("high_price", row.get("high_price")),
                        ("low_price", row.get("low_price")),
                        ("close_price", row.get("close_price")),
                        ("volume", row.get("volume")),
                        ("amount", row.get("amount")),
                        ("stock_name", row.get("stock_name")),
                        ("source", row.get("source", "tickflow")),
                    ]
                    for field_name, new_value in fields:
                        if new_value is not None:
                            old_value = getattr(existing, field_name)
                            if isinstance(new_value, float) and isinstance(old_value, float):
                                if abs(new_value - old_value) > 0.0001:
                                    setattr(existing, field_name, new_value)
                            elif new_value != old_value:
                                setattr(existing, field_name, new_value)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"保存数据失败: {e}")
        finally:
            db.close()

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "monitored_stocks": self.monitored_stocks,
            "job_count": len(self.scheduler.get_jobs()),
        }


_scheduler_instance: Optional[CrawlerScheduler] = None


def get_scheduler() -> CrawlerScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CrawlerScheduler()
    return _scheduler_instance
