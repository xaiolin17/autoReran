from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class TradeMark(Base):
    __tablename__ = "trade_marks"

    id = Column(Integer, primary_key=True, index=True)
    stock_data_id = Column(Integer, ForeignKey("stock_data.id"), nullable=False)
    mark_type = Column(String(20), nullable=False)  # buy, sell, hold
    mark_date = Column(DateTime, nullable=False)
    price = Column(Float)
    reason = Column(String(500))
    confidence = Column(Float)  # 置信度 0-1
    created_at = Column(DateTime, nullable=False)

    # 关联
    stock_data = relationship("StockData", back_populates="trade_marks")

    def __repr__(self):
        return f"<TradeMark {self.mark_type} {self.mark_date}>"
