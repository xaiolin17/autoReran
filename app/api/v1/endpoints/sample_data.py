from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logger import logger
from app.models.stock_data import StockData
from app.crawlers.data_processor import DataProcessor
from app.services.stock_service import StockService

router = APIRouter()


@router.post("/generate/{stock_code}")
def generate_sample_data(
    stock_code: str,
    days: int = 365,
    base_price: float = 100.0,
    db: Session = Depends(get_db)
):
    logger.info(f"生成示例数据: {stock_code}, {days}天")
    
    service = StockService(db)
    processor = DataProcessor()
    
    existing = service.get_stock_data(stock_code, "1d")
    for record in existing:
        db.delete(record)
    db.commit()
    
    df = processor.generate_sample_data(stock_code, "1d", days, base_price)
    
    new_records = []
    for _, row in df.iterrows():
        stock_data = StockData.__new__(StockData)
        stock_data.stock_code = row['stock_code']
        stock_data.stock_name = row['stock_name']
        stock_data.period = row['period']
        stock_data.datetime = row['datetime']
        stock_data.open_price = row['open_price']
        stock_data.high_price = row['high_price']
        stock_data.low_price = row['low_price']
        stock_data.close_price = row['close_price']
        stock_data.volume = row['volume']
        stock_data.amount = row['amount']
        stock_data.source = row['source']
        new_records.append(stock_data)
    
    db.bulk_save_objects(new_records)
    db.commit()
    
    logger.info(f"生成示例数据完成: {len(new_records)}条")
    return {
        "success": True,
        "message": f"Generated {len(new_records)} sample records",
        "stock_code": stock_code,
        "count": len(new_records)
    }
