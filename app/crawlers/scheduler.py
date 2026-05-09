from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import List, Optional
from datetime import datetime
import logging
from app.crawlers.sina import SinaCrawler
from app.crawlers.eastmoney import EastMoneyCrawler
from app.crawlers.data_processor import DataProcessor
from app.core.database import SessionLocal
from app.models.stock_data import StockData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrawlerScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.sina_crawler = SinaCrawler()
        self.eastmoney_crawler = EastMoneyCrawler()
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
            id='stock_crawl_job',
            name='Stock Data Crawling',
            replace_existing=True
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
        sina_data = self.sina_crawler.fetch_stock_data(stock_code, period="1d")
        eastmoney_data = self.eastmoney_crawler.fetch_stock_data(stock_code, period="1d")
        
        data_list = []
        if not sina_data.empty:
            data_list.append(sina_data)
        if not eastmoney_data.empty:
            data_list.append(eastmoney_data)
        
        if data_list:
            averaged_data = self.data_processor.average_data(data_list)
            cleaned_data = self.data_processor.clean_data(averaged_data)
            self._save_to_database(cleaned_data)
            
            logger.info(f"股票 {stock_code} 数据已保存")
    
    def _save_to_database(self, df):
        if df.empty:
            return
        
        db = SessionLocal()
        try:
            for _, row in df.iterrows():
                existing = db.query(StockData).filter(
                    StockData.stock_code == row['stock_code'],
                    StockData.period == row['period'],
                    StockData.datetime == row['datetime']
                ).first()
                
                if not existing:
                    stock_data = StockData(
                        stock_code=row['stock_code'],
                        stock_name=row.get('stock_name'),
                        period=row['period'],
                        datetime=row['datetime'],
                        open_price=row['open_price'],
                        high_price=row['high_price'],
                        low_price=row['low_price'],
                        close_price=row['close_price'],
                        volume=row['volume'],
                        amount=row.get('amount'),
                        source=row.get('source')
                    )
                    db.add(stock_data)
            
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"保存数据失败: {e}")
        finally:
            db.close()
    
    def get_status(self) -> dict:
        return {
            'is_running': self.is_running,
            'monitored_stocks': self.monitored_stocks,
            'job_count': len(self.scheduler.get_jobs())
        }


_scheduler_instance: Optional[CrawlerScheduler] = None


def get_scheduler() -> CrawlerScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CrawlerScheduler()
    return _scheduler_instance
