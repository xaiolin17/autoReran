import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from app.crawlers.base import BaseCrawler
from app.core.config import settings


class SinaCrawler(BaseCrawler):
    def __init__(self):
        self.base_url = settings.SINA_STOCK_URL
    
    def fetch_stock_data(self, stock_code: str, period: str = "1d", 
                        start_date: Optional[str] = None, 
                        end_date: Optional[str] = None) -> pd.DataFrame:
        try:
            code = self._convert_code(stock_code)
            url = f"{self.base_url}{code}"
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                data = self._parse_data(response.text, stock_code, period)
                return data
            return pd.DataFrame()
        except Exception as e:
            print(f"新浪爬虫错误: {e}")
            return pd.DataFrame()
    
    def fetch_realtime_data(self, stock_code: str) -> Dict:
        try:
            code = self._convert_code(stock_code)
            url = f"{self.base_url}{code}"
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                return self._parse_realtime(response.text, stock_code)
            return {}
        except Exception as e:
            print(f"新浪实时数据错误: {e}")
            return {}
    
    def fetch_stock_list(self) -> List[Dict]:
        return [
            {"code": "sh600000", "name": "浦发银行"},
            {"code": "sh600519", "name": "贵州茅台"},
            {"code": "sz000001", "name": "平安银行"},
            {"code": "sz000002", "name": "万科A"}
        ]
    
    def _convert_code(self, stock_code: str) -> str:
        if stock_code.startswith(('600', '601', '603', '605', '688', '51', '56', '58', '110', '113', '132', '204')):
            return f"sh{stock_code}" if not stock_code.startswith('sh') else stock_code
        else:
            return f"sz{stock_code}" if not stock_code.startswith('sz') else stock_code
    
    def _parse_data(self, text: str, stock_code: str, period: str) -> pd.DataFrame:
        try:
            data = text.split('"')[1].split(',')
            if len(data) < 32:
                return pd.DataFrame()
            
            name = data[0]
            now = float(data[3])
            open_p = float(data[1])
            high = float(data[4])
            low = float(data[5])
            volume = float(data[8])
            amount = float(data[9])
            
            df = pd.DataFrame([{
                'datetime': datetime.now(),
                'open_price': open_p,
                'high_price': high,
                'low_price': low,
                'close_price': now,
                'volume': volume,
                'amount': amount,
                'stock_code': stock_code,
                'stock_name': name,
                'period': period,
                'source': 'sina'
            }])
            return df
        except Exception as e:
            print(f"解析新浪数据错误: {e}")
            return pd.DataFrame()
    
    def _parse_realtime(self, text: str, stock_code: str) -> Dict:
        try:
            data = text.split('"')[1].split(',')
            if len(data) < 32:
                return {}
            
            return {
                'stock_code': stock_code,
                'stock_name': data[0],
                'open': float(data[1]),
                'pre_close': float(data[2]),
                'price': float(data[3]),
                'high': float(data[4]),
                'low': float(data[5]),
                'volume': float(data[8]),
                'amount': float(data[9]),
                'source': 'sina'
            }
        except Exception as e:
            print(f"解析新浪实时数据错误: {e}")
            return {}
