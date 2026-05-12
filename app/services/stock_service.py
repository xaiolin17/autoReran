from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
from app.core.logger import logger
from app.models.stock_data import StockData
from app.schemas.stock import StockDataCreate
from app.crawlers.akshare_crawler import AkshareCrawler
from app.crawlers.data_processor import DataProcessor


class StockService:
    def __init__(self, db: Session):
        self.db = db
        self.data_processor = DataProcessor()
        self.crawler = AkshareCrawler()
    
    def get_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[StockData]:
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        )
        
        if start_date:
            query = query.filter(StockData.datetime >= start_date)
        if end_date:
            query = query.filter(StockData.datetime <= end_date)
        
        query = query.order_by(desc(StockData.datetime))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def create_stock_data(self, stock_data: StockDataCreate) -> StockData:
        db_stock = StockData(**stock_data.dict())
        self.db.add(db_stock)
        self.db.commit()
        self.db.refresh(db_stock)
        return db_stock
    
    def has_data(self, stock_code: str, period: str) -> bool:
        count = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).count()
        return count > 0
    
    def get_latest_date(self, stock_code: str, period: str) -> Optional[datetime]:
        latest = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(desc(StockData.datetime)).first()
        return latest.datetime if latest else None
    
    def get_earliest_date(self, stock_code: str, period: str) -> Optional[datetime]:
        earliest = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(StockData.datetime).first()
        return earliest.datetime if earliest else None
    
    def fetch_and_save_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental: bool = False,
        historical: bool = False
    ) -> List[StockData]:
        if incremental:
            latest_date = self.get_latest_date(stock_code, period)
            today = datetime.now().date()
            
            if latest_date:
                latest_date_only = latest_date.date()
                if latest_date_only >= today:
                    # Already have data up to today or later, no need to fetch
                    logger.info(f"已有数据已是最新 (截止 {latest_date_only}，无需更新")
                    return []
                
                start_date = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
                logger.info(f"增量更新: 从 {start_date} 开始获取 {stock_code} {period} 数据")
        
        if historical:
            earliest_date = self.get_earliest_date(stock_code, period)
            if earliest_date:
                # For historical data: start date is 4 months before earliest date, end date is earliest date minus 1 day
                end_date = (earliest_date - timedelta(days=1)).strftime("%Y%m%d")
                earliest_date_only = earliest_date.date()
                start_date = (earliest_date_only - timedelta(days=120)).strftime("%Y%m%d")  # ~4 months back
                logger.info(f"加载历史数据: 从 {start_date} 到 {end_date} 获取 {stock_code} {period} 数据")
        
        df = self.crawler.fetch_stock_data(stock_code, period, start_date, end_date)
        
        if df.empty:
            logger.warning(f"未能从 Akshare 获取到数据: {stock_code} {period}")
            return []
        
        cleaned_data = self.data_processor.clean_data(df)
        
        saved_stocks = []
        for _, row in cleaned_data.iterrows():
            existing = self.db.query(StockData).filter(
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
                    source=row.get('source', 'akshare')
                )
                self.db.add(stock_data)
                saved_stocks.append(stock_data)
        
        try:
            self.db.commit()
            logger.info(f"✅ 保存了 {len(saved_stocks)} 条 {stock_code} {period} 数据")
        except Exception as e:
            logger.error(f"保存数据时出错: {e}")
            self.db.rollback()
            return []
        
        return saved_stocks
    
    def initialize_default_data(self, stock_code: str = "000001") -> bool:
        logger.info(f"开始初始化默认数据: {stock_code}")
        
        try:
            if self.has_data(stock_code, "1d"):
                logger.info(f"{stock_code} 已有数据，跳过初始化")
                return True
            
            saved_data = self.fetch_and_save_stock_data(stock_code, "1d")
            
            if saved_data:
                logger.info(f"✅ 成功初始化 {stock_code} 数据: {len(saved_data)} 条")
                return True
            else:
                logger.error(f"❌ 未能初始化 {stock_code} 数据")
                return False
                
        except Exception as e:
            logger.error(f"初始化默认数据失败: {e}")
            return False
    
    def get_latest_stock_data(self, stock_code: str, period: str = "1d") -> Optional[StockData]:
        return self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(desc(StockData.datetime)).first()
    
    def get_available_stocks(self) -> List[str]:
        result = self.db.query(StockData.stock_code).distinct().all()
        return [r[0] for r in result]
    
    def to_dataframe(self, stock_data_list: List[StockData]) -> pd.DataFrame:
        if not stock_data_list:
            return pd.DataFrame()
        
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
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'period': stock.period,
                'source': stock.source
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('datetime').reset_index(drop=True)
        return df
