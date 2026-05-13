import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.crawlers.base import BaseCrawler
from app.core.logger import logger, log_function_call

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("Akshare 未安装，请安装 Akshare: pip install akshare")


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
                logger.warning(f"第 {attempt + 1}/{self.max_retries} 次尝试失败: {str(e)}。{wait_time}秒后重试...")
                time.sleep(wait_time)
        
        logger.error(f"所有 {self.max_retries} 次尝试均失败。最后一次错误: {str(last_exception)}")
        return None
    
    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串，支持多种格式"""
        formats = ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"无法解析日期: {date_str}")
    
    def _get_start_end_dates(self, 
                           start_date: Optional[str] = None, 
                           end_date: Optional[str] = None, 
                           default_months: float = 1.0) -> tuple:
        """统一处理 start_date 和 end_date"""
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        
        if start_date is None:
            end_dt = self._parse_date(end_date)
            start_dt = end_dt - timedelta(days=int(default_months * 30))
            start_date = start_dt.strftime("%Y%m%d")
        
        try:
            start_dt = self._parse_date(start_date)
            end_dt = self._parse_date(end_date)
        except ValueError as e:
            logger.warning(f"日期解析失败: {e}")
            return None, None
        
        if start_dt > end_dt:
            logger.warning(f"无效日期范围: start_date={start_date} > end_date={end_date}")
            return None, None
        
        # 统一转换为 Akshare 需要的格式
        return start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d")
    
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
    
    @log_function_call
    def fetch_stock_data(self, 
                       stock_code: str, 
                       period: str = "1d", 
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取股票数据
        
        Args:
            stock_code: 股票代码
            period: 时间周期（如 1d, 1h, 1w, 1M）
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            pd.DataFrame: 股票数据
        """
        logger.info(f"开始获取股票数据: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}")
        
        if not self.available:
            logger.warning("Akshare 不可用，请安装 Akshare: pip install akshare")
            return pd.DataFrame()
        
        try:
            clean_code = self._normalize_stock_code(stock_code)
            logger.debug(f"标准化股票代码: {stock_code} -> {clean_code}")
            
            processed_start, processed_end = self._get_start_end_dates(
                start_date=start_date,
                end_date=end_date,
                default_months=1.0
            )
            
            if processed_start is None or processed_end is None:
                logger.warning(f"日期处理失败，返回空DataFrame")
                return pd.DataFrame()
            
            logger.info(f"获取数据: {clean_code} {period} [{processed_start} ~ {processed_end}]")
            
            if clean_code == "000001":
                index_code = "sh000001"
            elif clean_code == "399001":
                index_code = "sz399001"
            else:
                index_code = None
            
            if index_code:
                logger.debug(f"识别为指数代码: {index_code}")
                result = self._fetch_index_data(
                    index_code=index_code,
                    period=period,
                    start_date=processed_start,
                    end_date=processed_end
                )
            else:
                logger.debug(f"识别为普通股票代码: {clean_code}")
                result = self._fetch_stock_data(
                    stock_code=clean_code,
                    period=period,
                    start_date=processed_start,
                    end_date=processed_end
                )
            
            logger.info(f"获取数据完成: {len(result)} 条记录")
            return result
            
        except Exception as e:
            logger.error(f"Akshare获取 {stock_code} 数据失败: {str(e)}", exc_info=True)
            return pd.DataFrame()
    
    def fetch_realtime_data(self, stock_code: str) -> Dict:
        if not self.available:
            logger.warning("Akshare 实时数据不可用")
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
                    'stock_name': '上证指数' if code == '000001' else ('深证成指' if code == '399001' else index_code),
                    'period': period,
                    'source': 'akshare'
                })
            
            df_result = pd.DataFrame(result)
            logger.info(f"获取指数数据成功: {index_code}, {len(df_result)} 条")
            return df_result
        except Exception as e:
            logger.error(f"获取指数 {index_code} 数据失败: {str(e)}")
            return pd.DataFrame()
    
    def _fetch_stock_data(self, stock_code: str, period: str, 
                          start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票数据，使用 ak.stock_zh_a_hist 并设置 adjust='hfq'"""
        logger.info(f"开始获取股票数据内部方法: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}")
        
        try:
            clean_code = self._normalize_stock_code(stock_code)
            logger.debug(f"标准化股票代码: {stock_code} -> {clean_code}")
            
            df = None
            
            try:
                logger.info(f"尝试第 1 种 API 方法: stock_zh_a_hist")
                if period == "1d":
                    df = self._retry_fetch(ak.stock_zh_a_hist, symbol=clean_code, period="daily", start_date=start_date, end_date=end_date, adjust="hfq")
                elif period == "1w":
                    df = self._retry_fetch(ak.stock_zh_a_hist, symbol=clean_code, period="weekly", start_date=start_date, end_date=end_date, adjust="hfq")
                elif period == "1M":
                    df = self._retry_fetch(ak.stock_zh_a_hist, symbol=clean_code, period="monthly", start_date=start_date, end_date=end_date, adjust="hfq")
                else:
                    prefixed_code = self._add_market_prefix(clean_code)
                    logger.debug(f"使用分钟级数据: {prefixed_code}")
                    df = self._retry_fetch(ak.stock_zh_a_hist_min_em, symbol=prefixed_code, period="60", start_date=start_date, end_date=end_date)
            except Exception as e:
                logger.warning(f"第 1 种方法失败: {e}")
                df = None
            
            if df is None or df.empty:
                logger.debug(f"第 1 种方法未返回有效数据，尝试第 2 种方法")
                try:
                    logger.info(f"尝试第 2 种 API 方法: stock_zh_a_hist_em")
                    if period == "1d":
                        df = self._retry_fetch(ak.stock_zh_a_hist_em, symbol=clean_code, period="daily", start_date=start_date, end_date=end_date)
                    elif period == "1w":
                        df = self._retry_fetch(ak.stock_zh_a_hist_em, symbol=clean_code, period="weekly", start_date=start_date, end_date=end_date)
                    elif period == "1M":
                        df = self._retry_fetch(ak.stock_zh_a_hist_em, symbol=clean_code, period="monthly", start_date=start_date, end_date=end_date)
                    else:
                        prefixed_code = self._add_market_prefix(clean_code)
                        logger.debug(f"使用分钟级数据: {prefixed_code}")
                        df = self._retry_fetch(ak.stock_zh_a_hist_min_em, symbol=prefixed_code, period="60", start_date=start_date, end_date=end_date)
                except Exception as e:
                    logger.warning(f"第 2 种方法失败: {e}")
                    df = None
            
            if df is None or df.empty:
                logger.warning(f"AkShare 返回空数据: stock={stock_code}, period={period}")
                return pd.DataFrame()
            
            logger.info(f"原始数据列名: {list(df.columns)}")
            
            df = df.rename(columns={
                '日期': 'datetime',
                '股票代码': 'stock_code',
                '开盘': 'open_price',
                '收盘': 'close_price',
                '最高': 'high_price',
                '最低': 'low_price',
                '成交量(手)': 'volume',
                '成交额(元)': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'price_change',
                '换手率': 'turnover_rate'
            })
            
            df['stock_code'] = stock_code
            df['period'] = period
            df['source'] = 'akshare'
            
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            logger.info(f"获取股票数据成功: {stock_code}, {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 数据失败: {str(e)}", exc_info=True)
            return pd.DataFrame()