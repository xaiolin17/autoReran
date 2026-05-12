import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.crawlers.base import BaseCrawler
from app.core.config import settings


class EastMoneyCrawler(BaseCrawler):
    def __init__(self):
        self.base_url = settings.EASTMONEY_URL
    
    def fetch_stock_data(self, stock_code: str, period: str = "1d", 
                        start_date: Optional[str] = None, 
                        end_date: Optional[str] = None) -> pd.DataFrame:
        try:
            secid = self._convert_code(stock_code)
            klt = self._get_klt(period)
            
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
            if end_date is None:
                end_date = datetime.now().strftime("%Y%m%d")
            
            params = {
                'secid': secid,
                'klt': klt,
                'fqt': 1,
                'beg': start_date,
                'end': end_date,
                '_': int(datetime.now().timestamp())
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_data(data, stock_code, period)
            return pd.DataFrame()
        except Exception as e:
            print(f"东方财富爬虫错误: {e}")
            return pd.DataFrame()
    
    def fetch_realtime_data(self, stock_code: str) -> Dict:
        try:
            data = self.fetch_stock_data(stock_code, period="1d", 
                                        start_date=datetime.now().strftime("%Y%m%d"),
                                        end_date=datetime.now().strftime("%Y%m%d"))
            if not data.empty:
                latest = data.iloc[-1]
                return {
                    'stock_code': stock_code,
                    'stock_name': latest.get('stock_name', ''),
                    'open': latest['open_price'],
                    'price': latest['close_price'],
                    'high': latest['high_price'],
                    'low': latest['low_price'],
                    'volume': latest['volume'],
                    'amount': latest.get('amount', 0),
                    'source': 'eastmoney'
                }
            return {}
        except Exception as e:
            print(f"东方财富实时数据错误: {e}")
            return {}
    
    def fetch_stock_list(self) -> List[Dict]:
        return [
            {"code": "600000", "name": "浦发银行"},
            {"code": "600519", "name": "贵州茅台"},
            {"code": "000001", "name": "平安银行"},
            {"code": "000002", "name": "万科A"}
        ]
    
    def _convert_code(self, stock_code: str) -> str:
        # 特殊处理：上证指数 000001 和 深证成指 399001
        if stock_code == "000001":
            return "1.000001"  # 上证指数
        elif stock_code == "399001":
            return "0.399001"  # 深证成指
        elif stock_code.startswith(('600', '601', '603', '605', '688')):
            return f"1.{stock_code}"
        else:
            return f"0.{stock_code}"
    
    def _get_klt(self, period: str) -> int:
        period_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "1d": 101,
            "1w": 102,
            "1M": 103
        }
        return period_map.get(period, 101)
    
    def _parse_data(self, data: Dict, stock_code: str, period: str) -> pd.DataFrame:
        try:
            if data.get('data') is None or data['data'].get('klines') is None:
                return pd.DataFrame()
            
            klines = data['data']['klines']
            stock_name = data['data'].get('name', '')
            
            result = []
            for kline in klines:
                parts = kline.split(',')
                if len(parts) >= 11:
                    dt_str = parts[0]
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S") if ' ' in dt_str else datetime.strptime(dt_str, "%Y-%m-%d")
                    
                    result.append({
                        'datetime': dt,
                        'open_price': float(parts[1]),
                        'close_price': float(parts[2]),
                        'high_price': float(parts[3]),
                        'low_price': float(parts[4]),
                        'volume': float(parts[5]),
                        'amount': float(parts[6]),
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'period': period,
                        'source': 'eastmoney'
                    })
            
            df = pd.DataFrame(result)
            return df
        except Exception as e:
            print(f"解析东方财富数据错误: {e}")
            return pd.DataFrame()
