#!/usr/bin/env python3
"""
数据库初始化脚本
创建所有数据表，可选生成示例数据
"""

import sys
import os
from datetime import datetime, timedelta
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, engine, SessionLocal
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
    print("  - users (用户表)")
    print("  - task_status (任务状态)")
    print("  - roles (角色表)")
    print("  - permissions (权限表)")
    print("  - user_role (用户角色关联)")
    print("  - role_permission (角色权限关联)")


def generate_sample_data():
    """生成示例股票数据"""
    print("\n正在生成示例数据...")
    
    db = SessionLocal()
    try:
        # 生成过去 30 天的示例数据
        stock_code = "sh000001"
        now = datetime.now()
        
        base_price = 3200.0
        data_points = []
        
        for i in range(30 * 24 * 6):  # 30天 x 24小时 x 6个数据点
            time_point = now - timedelta(minutes=10 * i)
            variation = random.uniform(-20, 20)
            current_price = base_price + variation
            
            open_price = current_price + random.uniform(-5, 5)
            high_price = max(open_price, current_price) + random.uniform(0, 5)
            low_price = min(open_price, current_price) - random.uniform(0, 5)
            volume = random.randint(100000, 500000)
            
            data_points.append(StockData(
                stock_code=stock_code,
                period="1m",
                datetime=time_point,
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(current_price, 2),
                volume=volume,
                amount=round(volume * current_price, 2)
            ))
        
        # 保存到数据库
        db.add_all(data_points)
        db.commit()
        
        print(f"✅ 生成了 {len(data_points)} 条示例股票数据")
        print("  - 股票代码: sh000001 (上证指数)")
        print("  - 数据周期: 1分钟K线")
        print("  - 时间范围: 过去30天")
        
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ 生成示例数据失败: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument("--sample", action="store_true", help="生成示例数据")
    args = parser.parse_args()
    
    init_db()
    
    if args.sample:
        generate_sample_data()
    
    print("\n🎉 数据库初始化完成！")
    print("\n下一步:")
    print("  启动应用: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("  或者使用脚本: ./start.sh (Linux/Mac) 或 start.bat (Windows)")
