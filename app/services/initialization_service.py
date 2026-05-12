from sqlalchemy.orm import Session
from app.services.stock_service import StockService
from app.services.indicator_service import IndicatorService


class InitializationService:
    def __init__(self, db: Session):
        self.db = db
    
    def check_and_initialize_default_data(self):
        try:
            stock_service = StockService(self.db)
            indicator_service = IndicatorService(self.db)
            
            default_stock_code = "000001"
            
            has_data = stock_service.has_data(default_stock_code, "1d")
            
            if not has_data:
                print(f"⚙️ 初始化默认数据: 上证指数 ({default_stock_code})...")
                success = stock_service.initialize_default_data(default_stock_code)
                
                if success:
                    print(f"✅ 默认数据初始化完成，正在计算技术指标...")
                    indicator_service.calculate_and_save_indicators(default_stock_code, "1d")
                    print(f"✅ 技术指标计算完成")
                else:
                    print(f"⚠️ 默认数据初始化失败（可能网络问题）")
            else:
                print(f"✅ 默认数据已存在: {default_stock_code}")
            
            return True
        except Exception as e:
            print(f"⚠️ 初始化服务出错: {e}")
            import traceback
            traceback.print_exc()
            return False
