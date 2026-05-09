from sqlalchemy.orm import Session
from sqlalchemy import desc, select
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
import os
from app.models.stock_data import StockData
from app.schemas.stock import StockDataCreate
from app.crawlers.sina import SinaCrawler
from app.crawlers.eastmoney import EastMoneyCrawler
from app.crawlers.data_processor import DataProcessor
from app.core.logger import logger
from app.core.config import settings


class StockService:
    def __init__(self, db: Session):
        self.db = db
        self.sina_crawler = SinaCrawler()
        self.eastmoney_crawler = EastMoneyCrawler()
        self.data_processor = DataProcessor()
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
    
    def get_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[StockData]:
        query = select(StockData).where(
            StockData.stock_code == stock_code,
            StockData.period == period
        )
        
        if start_date:
            query = query.where(StockData.datetime >= start_date)
        if end_date:
            query = query.where(StockData.datetime <= end_date)
        
        query = query.order_by(desc(StockData.datetime))
        
        if limit:
            query = query.limit(limit)
        
        result = self.db.execute(query).scalars().all()
        logger.info(f"获取股票 {stock_code} 数据: {len(result)} 条")
        
        return result
    
    def create_stock_data(self, stock_data: StockDataCreate) -> StockData:
        db_stock = StockData(**stock_data.model_dump())
        self.db.add(db_stock)
        self.db.commit()
        self.db.refresh(db_stock)
        logger.debug(f"创建股票数据: {stock_data.stock_code}")
        return db_stock
    
    def fetch_and_save_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[StockData]:
        logger.info(f"开始获取股票 {stock_code} 数据")
        
        sina_data = self.sina_crawler.fetch_stock_data(stock_code, period, start_date, end_date)
        eastmoney_data = self.eastmoney_crawler.fetch_stock_data(stock_code, period, start_date, end_date)
        
        data_list = []
        if not sina_data.empty:
            data_list.append(sina_data)
            logger.debug(f"新浪数据源: {len(sina_data)} 条")
        if not eastmoney_data.empty:
            data_list.append(eastmoney_data)
            logger.debug(f"东方财富数据源: {len(eastmoney_data)} 条")
        
        if not data_list:
            logger.warning("无数据源，生成示例数据")
            sample_data = self.data_processor.generate_sample_data(stock_code, period)
            data_list.append(sample_data)
        
        averaged_data = self.data_processor.average_data(data_list)
        cleaned_data = self.data_processor.clean_data(averaged_data)
        
        if cleaned_data.empty:
            logger.warning("清洗后无有效数据")
            return []
        
        existing_records = self._get_existing_records(stock_code, period, cleaned_data)
        new_records = self._filter_new_records(cleaned_data, existing_records)
        
        saved_stocks = self._bulk_insert_stock_data(new_records, stock_code, period)
        logger.info(f"保存股票 {stock_code} 数据: {len(saved_stocks)} 条新记录")
        
        return saved_stocks
    
    def _get_existing_records(self, stock_code: str, period: str, df: pd.DataFrame) -> set:
        datetimes = df['datetime'].tolist()
        query = select(StockData.datetime).where(
            StockData.stock_code == stock_code,
            StockData.period == period,
            StockData.datetime.in_(datetimes)
        )
        result = self.db.execute(query).scalars().all()
        return set(result)
    
    def _filter_new_records(self, df: pd.DataFrame, existing_datetimes: set) -> pd.DataFrame:
        return df[~df['datetime'].isin(existing_datetimes)]
    
    def _bulk_insert_stock_data(self, df: pd.DataFrame, stock_code: str, period: str) -> List[StockData]:
        if df.empty:
            return []
        
        stocks = []
        for _, row in df.iterrows():
            stock = StockData(
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
            stocks.append(stock)
        
        self.db.bulk_save_objects(stocks)
        self.db.commit()
        
        return stocks
    
    def get_latest_stock_data(self, stock_code: str, period: str = "1d") -> Optional[StockData]:
        query = select(StockData).where(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(desc(StockData.datetime)).limit(1)
        
        return self.db.execute(query).scalar_one_or_none()
    
    def get_available_stocks(self) -> List[str]:
        query = select(StockData.stock_code).distinct()
        result = self.db.execute(query).scalars().all()
        return list(result)
    
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
