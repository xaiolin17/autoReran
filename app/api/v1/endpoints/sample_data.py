from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from app.core.database import get_db
from app.models.stock_data import StockData

router = APIRouter()


@router.post("/generate/{stock_code}")
def generate_sample_data(
    stock_code: str,
    days: int = 365,
    base_price: float = 100.0,
    db: Session = Depends(get_db)
):
    np.random.seed(42)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    prices = [base_price]
    for _ in range(1, len(date_range)):
        change = np.random.normal(0, 0.02)
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, base_price * 0.5))
    
    existing = db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == "1d"
    ).all()
    for record in existing:
        db.delete(record)
    db.commit()
    
    saved_count = 0
    for i, date in enumerate(date_range):
        price = prices[i]
        open_p = price * (1 + np.random.normal(0, 0.005))
        close_p = price
        high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.01)))
        low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.01)))
        volume = np.random.randint(1000000, 10000000)
        amount = volume * close_p
        
        stock_data = StockData(
            stock_code=stock_code,
            stock_name=f"SAMPLE_{stock_code}",
            period="1d",
            datetime=date,
            open_price=open_p,
            high_price=high_p,
            low_price=low_p,
            close_price=close_p,
            volume=volume,
            amount=amount,
            source="sample"
        )
        db.add(stock_data)
        saved_count += 1
    
    db.commit()
    
    return {"message": f"Generated {saved_count} sample records", "stock_code": stock_code}
