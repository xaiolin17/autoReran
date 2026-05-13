from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base


class StockData(Base):
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), index=True, nullable=False)
    stock_name = Column(String(100))
    period = Column(String(10), nullable=False, default="1d")
    datetime = Column(DateTime, index=True, nullable=False)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    turnover = Column(Float)
    pe = Column(Float)
    pb = Column(Float)
    source = Column(String(50))

    # 用户标记（用于模型训练标签）
    label = Column(String(20), default=None)  # NULL / 买入 / 卖出

    # 技术指标
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    ma30 = Column(Float)
    ma60 = Column(Float)

    # MACD
    dif = Column(Float)
    dea = Column(Float)
    macd = Column(Float)

    # KDJ
    k = Column(Float)
    d = Column(Float)
    j = Column(Float)

    # RSI
    rsi6 = Column(Float)
    rsi12 = Column(Float)
    rsi24 = Column(Float)

    # 布林带
    upper = Column(Float)
    middle = Column(Float)
    lower = Column(Float)

    # 交易标记
    trade_marks = relationship("TradeMark", back_populates="stock_data", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StockData {self.stock_code} {self.datetime}>"


class StockCode(Base):
    __tablename__ = "stock_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100))
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<StockCode {self.code} {self.name}>"
