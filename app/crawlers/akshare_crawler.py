import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.crawlers.base import BaseCrawler
from app.core.logger import logger

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("Akshare not installed, please install Akshare: pip install akshare")


class AkshareCrawler(BaseCrawler):
    """使用Akshare作为数据源（更可靠）"""
    
    def __init__(self):
        self.available = AKSHARE_AVAILABLE
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def _retry_fetch(self, fetch_func, *args, **kwargs):
        """Retry helper with exponential backoff"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                result = fetch_func(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        logger.error(f"All {self.max_retries} attempts failed. Last error: {str(last_exception)}")
        return None
    
    def fetch_stock_data(self, stock_code: str, period: str = "1d", 
                        start_date: Optional[str] = None, 
                        end_date: Optional[str] = None) -> pd.DataFrame:
        if not self.available:
            logger.warning("Akshare 不可用，请安装 Akshare: pip install akshare")
            return pd.DataFrame()
        
        try:
            # 处理指数代码转换
            if stock_code == "000001":
                return self._fetch_index_data("sh000001", period, start_date, end_date)
            elif stock_code == "399001":
                return self._fetch_index_data("sz399001", period, start_date, end_date)
            else:
                return self._fetch_stock_data(stock_code, period, start_date, end_date)
        except Exception as e:
            logger.error(f"Akshare获取 {stock_code} 数据失败: {str(e)}")
            return pd.DataFrame()
    
    def fetch_realtime_data(self, stock_code: str) -> Dict:
        if not self.available:
            logger.warning("Akshare not available for realtime data")
            return {}
        
        try:
            return {}
        except Exception as e:
            logger.error(f"Akshare获取实时数据失败: {e}")
            return {}
    
    def fetch_stock_list(self) -> List[Dict]:
        return [
            {"code": "000001", "name": "上证指数"},
            {"code": "399001", "name": "深证成指"},
            {"code": "600519", "name": "贵州茅台"},
            {"code": "510300", "name": "沪深300ETF"}
        ]
    
    def _fetch_index_data(self, index_code: str, period: str, 
                          start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
        """获取指数数据"""
        try:
            # If we have end_date but no start_date (loading historical data), set start_date to 10 years earlier
            if start_date is None and end_date is not None:
                end_dt = datetime.strptime(end_date, "%Y%m%d")
                start_date = (end_dt - timedelta(days=3650)).strftime("%Y%m%d")  # 10 years back
            elif start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            
            if end_date is None:
                end_date = datetime.now().strftime("%Y%m%d")
            
            # 提取纯数字代码，去除 sh/sz 前缀
            code = index_code[2:] if len(index_code) > 2 else index_code
            
            # 根据周期选择不同的 API
            if period == "1d":
                df = self._retry_fetch(
                    ak.index_zh_a_hist,
                    symbol=code, 
                    period="daily", 
                    start_date=start_date, 
                    end_date=end_date
                )
            elif period == "1w":
                df = self._retry_fetch(
                    ak.index_zh_a_hist,
                    symbol=code, 
                    period="weekly", 
                    start_date=start_date, 
                    end_date=end_date
                )
            elif period == "1M":
                df = self._retry_fetch(
                    ak.index_zh_a_hist,
                    symbol=code, 
                    period="monthly", 
                    start_date=start_date, 
                    end_date=end_date
                )
            else:
                df = self._retry_fetch(
                    ak.index_zh_a_hist_min_em,
                    symbol=index_code, 
                    period="60", 
                    start_date=start_date, 
                    end_date=end_date
                )
            
            if df is None or df.empty:
                logger.warning(f"AkShare 返回空数据: index={index_code}, period={period}")
                return pd.DataFrame()
            
            # 标准化列名
            result = []
            for _, row in df.iterrows():
                result.append({
                    'datetime': pd.to_datetime(row.get('日期', row.get('time', ''))),
                    'open_price': float(row.get('开盘', row.get('open', 0))),
                    'high_price': float(row.get('最高', row.get('high', 0))),
                    'low_price': float(row.get('最低', row.get('low', 0))),
                    'close_price': float(row.get('收盘', row.get('close', 0))),
                    'volume': float(row.get('成交量', row.get('volume', 0))),
                    'amount': float(row.get('成交额', row.get('amount', 0))),
                    'stock_code': index_code[2:] if len(index_code) > 2 else index_code,
                    'stock_name': '上证指数' if index_code == 'sh000001' else '深证成指',
                    'period': period,
                    'source': 'akshare'
                })
            
            df_result = pd.DataFrame(result)
            logger.info(f"✅ Akshare 获取指数数据成功: {index_code}, {len(df_result)} 条")
            return df_result
        except Exception as e:
            logger.error(f"获取指数 {index_code} 数据失败: {str(e)}")
            return pd.DataFrame()
    
    def _fetch_stock_data(self, stock_code: str, period: str, 
                          start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
        """获取股票数据"""
        try:
            # If we have end_date but no start_date (loading historical data), set start_date to 10 years earlier
            if start_date is None and end_date is not None:
                end_dt = datetime.strptime(end_date, "%Y%m%d")
                start_date = (end_dt - timedelta(days=3650)).strftime("%Y%m%d")  # 10 years back
            elif start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            
            if end_date is None:
                end_date = datetime.now().strftime("%Y%m%d")
            
            # 确定市场并添加前缀
            if stock_code.startswith(('600', '601', '603', '605', '688')):
                symbol = f"sh{stock_code}"
            else:
                symbol = f"sz{stock_code}"
            
            # 根据周期选择不同的 API
            if period == "1d":
                df = self._retry_fetch(
                    ak.stock_zh_a_hist,
                    symbol=stock_code, 
                    period="daily", 
                    start_date=start_date, 
                    end_date=end_date
                )
            elif period == "1w":
                df = self._retry_fetch(
                    ak.stock_zh_a_hist,
                    symbol=stock_code, 
                    period="weekly", 
                    start_date=start_date, 
                    end_date=end_date
                )
            elif period == "1M":
                df = self._retry_fetch(
                    ak.stock_zh_a_hist,
                    symbol=stock_code, 
                    period="monthly", 
                    start_date=start_date, 
                    end_date=end_date
                )
            else:
                df = self._retry_fetch(
                    ak.stock_zh_a_hist_min_em,
                    symbol=symbol, 
                    period="60", 
                    start_date=start_date, 
                    end_date=end_date
                )
            
            if df is None or df.empty:
                logger.warning(f"AkShare 返回空数据: stock={stock_code}, period={period}")
                return pd.DataFrame()
            
            stock_name = df.iloc[0].get('股票名称', stock_code) if len(df) > 0 else stock_code
            
            # 标准化列名
            result = []
            for _, row in df.iterrows():
                result.append({
                    'datetime': pd.to_datetime(row.get('日期', row.get('time', ''))),
                    'open_price': float(row.get('开盘', row.get('open', 0))),
                    'high_price': float(row.get('最高', row.get('high', 0))),
                    'low_price': float(row.get('最低', row.get('low', 0))),
                    'close_price': float(row.get('收盘', row.get('close', 0))),
                    'volume': float(row.get('成交量', row.get('volume', 0))),
                    'amount': float(row.get('成交额', row.get('amount', 0))),
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'period': period,
                    'source': 'akshare'
                })
            
            df_result = pd.DataFrame(result)
            logger.info(f"✅ Akshare 获取股票数据成功: {stock_code}, {len(df_result)} 条")
            return df_result
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 数据失败: {str(e)}")
            return pd.DataFrame()
