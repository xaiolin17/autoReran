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
                            days: int = 365, base_price: float = None) -> pd.DataFrame:
        raise RuntimeError(f"不允许生成模拟数据！请安装akshare并配置真实数据源！股票代码: {stock_code}")
