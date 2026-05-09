#!/usr/bin/env python3
"""
数据库初始化脚本
创建所有数据表
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, engine
from app.models import StockData, TradeMark, MLModel, BacktestResult

def init_db():
    """初始化数据库，创建所有表"""
    print("正在创建数据库表...")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    print("✅ 数据库表创建成功！")
    print("已创建的表:")
    print("  - stock_data (股票数据)")
    print("  - trade_marks (交易标记)")
    print("  - ml_models (机器学习模型)")
    print("  - backtest_results (回测结果)")

if __name__ == "__main__":
    init_db()
