from sqlalchemy import (Column, DateTime, Float, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from app.core.database import Base


class StockData(Base):
    """
    股票K线数据模型

    职责:
        映射stock_data数据库表，存储股票的历史K线数据和技术指标。
        包含价格数据（开高低收）、成交量、技术指标（MA/MACD/KDJ/RSI/布林带）等字段。
        与TradeMark模型建立一对多关系。

    被调用方:
        - indicators.py: 查询股票数据并计算指标
        - stock_service.py: 保存和查询股票数据
        - tickflow_crawler.py: 查询StockCode映射

    表名: stock_data
    """
    __tablename__ = "stock_data"

    # 唯一索引：同一股票同一周期同一天只能有一条数据
    __table_args__ = (
        UniqueConstraint('stock_code', 'period', 'datetime', name='uix_stock_period_datetime'),
    )

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
        """
        模型的字符串表示

        返回值:
            str: 格式为 <StockData {stock_code} {datetime}>
        """
        return f"<StockData {self.stock_code} {self.datetime}>"


class StockCode(Base):
    """
    股票代码映射模型

    职责:
        映射stock_codes数据库表，存储短代码到完整代码的映射关系。
        用于将用户输入的6位短代码转换为带市场后缀的完整代码（如000001.SZ）。
        支持股票、指数、期货、债券等多种类别。

    被调用方:
        - indicators.py: 将短代码转换为完整代码后查询数据
        - tickflow_crawler.py: 查询完整代码用于API请求
        - stock_service.py: 管理和查询代码映射

    表名: stock_codes
    """
    __tablename__ = "stock_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), index=True, nullable=False)  # 短代码（如 000001）
    name = Column(String(100), unique=True, index=True, nullable=False)  # 完整代码（如 000001.SZ）
    category = Column(String(50))  # 类别：stock/index/futures/bond 等
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        """
        模型的字符串表示

        返回值:
            str: 格式为 <StockCode {code} {name}>
        """
        return f"<StockCode {self.code} {self.name}>"
