import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import numpy as np


class DataProcessor:
    @staticmethod
    def merge_data(data_list: List[pd.DataFrame]) -> pd.DataFrame:
        if not data_list:
            return pd.DataFrame()
        
        merged = pd.concat(data_list, ignore_index=True)
        return merged
    
    @staticmethod
    def average_data(data_list: List[pd.DataFrame], method: str = "mean") -> pd.DataFrame:
        if not data_list:
            return pd.DataFrame()
        
        if len(data_list) == 1:
            return data_list[0]
        
        merged = pd.concat(data_list, ignore_index=True)
        
        if merged.empty:
            return pd.DataFrame()
        
        numeric_cols = ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 'amount']
        group_cols = ['datetime', 'stock_code', 'period']
        
        available_numeric = [col for col in numeric_cols if col in merged.columns]
        available_group = [col for col in group_cols if col in merged.columns]
        
        if not available_group or not available_numeric:
            return merged
        
        agg_dict = {}
        for col in available_numeric:
            if method == "mean":
                agg_dict[col] = "mean"
            elif method == "median":
                agg_dict[col] = "median"
            else:
                agg_dict[col] = "mean"
        
        if 'stock_name' in merged.columns:
            agg_dict['stock_name'] = 'first'
        if 'source' in merged.columns:
            agg_dict['source'] = lambda x: ','.join(set(x))
        
        result = merged.groupby(available_group, as_index=False).agg(agg_dict)
        return result
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        df = df.dropna(subset=['open_price', 'high_price', 'low_price', 'close_price', 'volume'])
        df = df[df['volume'] >= 0]
        df = df[df['high_price'] >= df['low_price']]
        df = df[df['high_price'] >= df['open_price']]
        df = df[df['high_price'] >= df['close_price']]
        df = df[df['low_price'] <= df['open_price']]
        df = df[df['low_price'] <= df['close_price']]
        
        df = df.sort_values('datetime').reset_index(drop=True)
        return df
    
    @staticmethod
    def resample_data(df: pd.DataFrame, target_period: str) -> pd.DataFrame:
        if df.empty:
            return df
        
        df = df.set_index('datetime').sort_index()
        
        period_map = {
            "1m": "1T",
            "5m": "5T",
            "15m": "15T",
            "30m": "30T",
            "1h": "1H",
            "1d": "1D",
            "1w": "1W",
            "1M": "1M"
        }
        
        freq = period_map.get(target_period, "1D")
        
        resampled = df.resample(freq).agg({
            'open_price': 'first',
            'high_price': 'max',
            'low_price': 'min',
            'close_price': 'last',
            'volume': 'sum',
            'amount': 'sum'
        }).dropna()
        
        resampled['stock_code'] = df['stock_code'].iloc[0] if 'stock_code' in df.columns else None
        resampled['stock_name'] = df['stock_name'].iloc[0] if 'stock_name' in df.columns else None
        resampled['period'] = target_period
        resampled['source'] = 'resampled'
        
        resampled = resampled.reset_index()
        return resampled
    
    @staticmethod
    def generate_sample_data(stock_code: str, period: str = "1d", 
                            days: int = 365, base_price: float = 3200.0) -> pd.DataFrame:
        """生成合理的模拟数据 - 用于网络不可用时的演示"""
        
        # 根据股票代码设置合理的基准价格
        if stock_code == "000001":
            base_price = 3200.0  # 上证指数
        elif stock_code == "399001":
            base_price = 11000.0  # 深证成指
        elif stock_code == "600519":
            base_price = 1800.0  # 贵州茅台
        elif stock_code == "510300":
            base_price = 4.2  # 沪深300ETF
        else:
            base_price = 100.0
        
        np.random.seed(42)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date)
            current_date += timedelta(days=1)
        
        data = []
        price = base_price
        
        for i, date in enumerate(date_list):
            # 模拟随机游走
            change = np.random.normal(0, 0.015)
            open_price = price
            close_price = price * (1 + change)
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.005)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.005)))
            
            volume = np.random.randint(1000000, 5000000)
            amount = close_price * volume * 0.1
            
            data.append({
                'datetime': date,
                'open_price': round(open_price, 2),
                'high_price': round(high_price, 2),
                'low_price': round(low_price, 2),
                'close_price': round(close_price, 2),
                'volume': volume,
                'amount': round(amount, 2),
                'stock_code': stock_code,
                'stock_name': f"模拟{stock_code}",
                'period': period,
                'source': 'demo_data'
            })
            
            price = close_price
        
        return pd.DataFrame(data)
