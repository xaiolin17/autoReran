from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.stock_data import StockData
from app.services.stock_service import StockService


class InitializationService:
    """初始化服务 - 获取真实默认数据"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_and_initialize_default_data(self):
        """检查并初始化默认数据"""
        try:
            # 检查是否已有默认的上证指数数据
            default_stock_code = "000001"
            
            # 简单的存在性检查，避免复杂查询
            count_query = self.db.query(StockData.id).filter(
                StockData.stock_code == default_stock_code,
                StockData.period == "1d"
            )
            
            # 使用 limit 1 快速检查
            exists = count_query.first() is not None
            
            if exists:
                print(f"✓ 默认数据已存在 (股票代码: {default_stock_code})")
                # 检查数据是否是旧的模拟数据，如果是则替换
                sample = count_query.first()
                if sample:
                    # 检查是否是旧的模拟数据（price < 500，通常上证指数>2000）
                    first_data = self.db.query(StockData).filter(
                        StockData.stock_code == default_stock_code,
                        StockData.period == "1d"
                    ).first()
                    if first_data and first_data.close_price < 500:
                        print("⚠️ 发现旧的模拟数据，正在删除并获取真实数据...")
                        self.db.query(StockData).filter(
                            StockData.stock_code == default_stock_code
                        ).delete()
                        self.db.commit()
                        exists = False
            
            if not exists:
                print(f"⚙️ 初始化默认数据 (股票代码: {default_stock_code})...")
                self._fetch_and_save_real_data(default_stock_code)
                print(f"✓ 默认数据初始化完成")
            
            return True
        except Exception as e:
            print(f"⚠️ 初始化服务出错: {e}")
            print("  提示: 如果数据库结构不匹配，请删除 stock_data.db 重新启动")
            return False
    
    def _fetch_and_save_real_data(self, stock_code: str):
        """获取真实数据并保存"""
        try:
            stock_service = StockService(self.db)
            
            # 获取上证指数的日线数据
            for period in ["1d", "1h", "1w", "1M"]:
                print(f"  获取 {period} 数据...")
                saved = stock_service.fetch_and_save_stock_data(stock_code, period)
                print(f"  保存了 {len(saved)} 条 {period} 数据")
            
        except Exception as e:
            print(f"获取真实数据出错: {e}")
