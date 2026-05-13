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
        self.max_retries = 5
        self.retry_delay = 3  # seconds
    
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
    
    def _get_start_end_dates(self, 
                           start_date: Optional[str] = None, 
                           end_date: Optional[str] = None, 
                           default_days: int = 365,
                           historical_mode: bool = False,
                           historical_end_date: Optional[str] = None,
                           historical_days: int = 120) -> tuple:
        """统一处理 start_date 和 end_date"""
        # 如果是历史数据模式
        if historical_mode and historical_end_date:
            end_dt = datetime.strptime(historical_end_date, "%Y%m%d")
            end_date = historical_end_date
            start_dt = end_dt - timedelta(days=historical_days)
            start_date = start_dt.strftime("%Y%m%d")
            return start_date, end_date
        
        # 正常模式
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        
        if start_date is None:
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_dt = end_dt - timedelta(days=default_days)
            start_date = start_dt.strftime("%Y%m%d")
        
        # 检查时间范围有效性
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        
        if start_dt > end_dt:
            logger.warning(f"无效日期范围: start_date={start_date} > end_date={end_date}")
            return None, None
        
        return start_date, end_date
    
    def _normalize_stock_code(self, stock_code: str) -> str:
        """标准化股票代码，去除 sh/sz 前缀"""
        if len(stock_code) > 6 and stock_code[:2] in ('sh', 'sz'):
            return stock_code[2:]
        return stock_code
    
    def _add_market_prefix(self, stock_code: str) -> str:
        """为股票代码添加市场前缀"""
        code = self._normalize_stock_code(stock_code)
        if code.startswith(('600', '601', '603', '605', '688')):
            return f"sh{code}"
        else:
            return f"sz{code}"
    
    def fetch_stock_data(self, stock_code: str, period: str = "1d", 
                        start_date: Optional[str] = None, 
                        end_date: Optional[str] = None,
                        historical_mode: bool = False,
                        historical_end_date: Optional[str] = None) -> pd.DataFrame:
        if not self.available:
            logger.warning("Akshare 不可用，请安装 Akshare: pip install akshare")
            return pd.DataFrame()
        
        try:
            # 标准化股票代码（去除前缀）
            clean_code = self._normalize_stock_code(stock_code)
            
            # 统一处理日期
            processed_start, processed_end = self._get_start_end_dates(
                start_date=start_date,
                end_date=end_date,
                default_days=365,
                historical_mode=historical_mode,
                historical_end_date=historical_end_date
            )
            
            if processed_start is None or processed_end is None:
                return pd.DataFrame()
            
            logger.info(f"获取数据: {clean_code} {period} [{processed_start} ~ {processed_end}]")
            
            # 处理指数
            if clean_code == "000001" or clean_code == "399001":
                index_code = f"sh{clean_code}" if clean_code == "000001" else f"sz{clean_code}"
                return self._fetch_index_data(
                    index_code=index_code,
                    period=period,
                    start_date=processed_start,
                    end_date=processed_end
                )
            else:
                return self._fetch_stock_data(
                    stock_code=clean_code,
                    period=period,
                    start_date=processed_start,
                    end_date=processed_end
                )
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
                          start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数数据"""
        try:
            code = index_code[2:] if len(index_code) > 2 else index_code
            
            df = None
            
            # 尝试方法 1
            try:
                logger.info(f"尝试第 1 种 API 方法")
                if period == "1d":
                    df = self._retry_fetch(ak.index_zh_a_hist, symbol=code, period="daily", start_date=start_date, end_date=end_date)
                elif period == "1w":
                    df = self._retry_fetch(ak.index_zh_a_hist, symbol=code, period="weekly", start_date=start_date, end_date=end_date)
                elif period == "1M":
                    df = self._retry_fetch(ak.index_zh_a_hist, symbol=code, period="monthly", start_date=start_date, end_date=end_date)
                else:
                    df = self._retry_fetch(ak.index_zh_a_hist_min_em, symbol=index_code, period="60", start_date=start_date, end_date=end_date)
            except Exception as e:
                logger.warning(f"第 1 种方法失败: {e}")
                df = None
            
            if df is None or df.empty:
                try:
                    logger.info(f"尝试第 2 种 API 方法")
                    if period == "1d":
                        df = self._retry_fetch(ak.index_zh_a_hist_em, symbol=code, period="daily", start_date=start_date, end_date=end_date)
                    elif period == "1w":
                        df = self._retry_fetch(ak.index_zh_a_hist_em, symbol=code, period="weekly", start_date=start_date, end_date=end_date)
                    elif period == "1M":
                        df = self._retry_fetch(ak.index_zh_a_hist_em, symbol=code, period="monthly", start_date=start_date, end_date=end_date)
                    else:
                        df = self._retry_fetch(ak.index_zh_a_hist_min_em, symbol=index_code, period="60", start_date=start_date, end_date=end_date)
                except Exception as e:
                    logger.warning(f"第 2 种方法失败: {e}")
                    df = None
            
            if df is None or df.empty:
                logger.warning(f"AkShare 返回空数据: index={index_code}, period={period}")
                return pd.DataFrame()
            
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
                          start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票数据"""
        try:
            # 标准化代码
            clean_code = self._normalize_stock_code(stock_code)
            # 带前缀的代码（用于需要前缀的 API）
            prefixed_code = self._add_market_prefix(clean_code)
            
            df = None
            
            try:
                logger.info(f"尝试第 1 种 API 方法")
                # stock_zh_a_hist 不需要前缀
                if period == "1d":
                    df = self._retry_fetch(ak.stock_zh_a_hist, symbol=clean_code, period="daily", start_date=start_date, end_date=end_date)
                elif period == "1w":
                    df = self._retry_fetch(ak.stock_zh_a_hist, symbol=clean_code, period="weekly", start_date=start_date, end_date=end_date)
                elif period == "1M":
                    df = self._retry_fetch(ak.stock_zh_a_hist, symbol=clean_code, period="monthly", start_date=start_date, end_date=end_date)
                else:
                    # stock_zh_a_hist_min_em 需要前缀
                    df = self._retry_fetch(ak.stock_zh_a_hist_min_em, symbol=prefixed_code, period="60", start_date=start_date, end_date=end_date)
            except Exception as e:
                logger.warning(f"第 1 种方法失败: {e}")
                df = None
            
            if df is None or df.empty:
                try:
                    logger.info(f"尝试第 2 种 API 方法")
                    # stock_zh_a_hist_em 不需要前缀
                    if period == "1d":
                        df = self._retry_fetch(ak.stock_zh_a_hist_em, symbol=clean_code, period="daily", start_date=start_date, end_date=end_date)
                    elif period == "1w":
                        df = self._retry_fetch(ak.stock_zh_a_hist_em, symbol=clean_code, period="weekly", start_date=start_date, end_date=end_date)
                    elif period == "1M":
                        df = self._retry_fetch(ak.stock_zh_a_hist_em, symbol=clean_code, period="monthly", start_date=start_date, end_date=end_date)
                    else:
                        # stock_zh_a_hist_min_em 需要前缀
                        df = self._retry_fetch(ak.stock_zh_a_hist_min_em, symbol=prefixed_code, period="60", start_date=start_date, end_date=end_date)
                except Exception as e:
                    logger.warning(f"第 2 种方法失败: {e}")
                    df = None
            
            if df is None or df.empty:
                logger.warning(f"AkShare 返回空数据: stock={stock_code}, period={period}")
                return pd.DataFrame()
            
            stock_name = df.iloc[0].get('股票名称', stock_code) if len(df) > 0 else stock_code
            
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

