from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from app.core.database import Base


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(100), nullable=False)
    stock_code = Column(String(20), index=True, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # 回测结果指标
    total_return = Column(Float)
    annual_return = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    avg_profit = Column(Float)
    avg_loss = Column(Float)
    profit_factor = Column(Float)

    # 详细数据
    trades = Column(JSON)  # 交易记录
    equity_curve = Column(JSON)  # 净值曲线
    params = Column(JSON)  # 策略参数
    description = Column(Text)

    def __repr__(self):
        return f"<BacktestResult {self.strategy_name} {self.stock_code}>"
