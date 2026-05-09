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
                            days: int = 365, base_price: float = 100.0) -> pd.DataFrame:
        np.random.seed(42)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        prices = [base_price]
        for _ in range(1, len(date_range)):
            change = np.random.normal(0, 0.02)
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, base_price * 0.5))
        
        data = []
        for i, date in enumerate(date_range):
            price = prices[i]
            open_p = price * (1 + np.random.normal(0, 0.005))
            close_p = price
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.01)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.01)))
            volume = np.random.randint(1000000, 10000000)
            amount = volume * close_p
            
            data.append({
                'datetime': date,
                'open_price': open_p,
                'high_price': high_p,
                'low_price': low_p,
                'close_price': close_p,
                'volume': volume,
                'amount': amount,
                'stock_code': stock_code,
                'stock_name': f"Sample{stock_code}",
                'period': period,
                'source': 'sample'
            })
        
        df = pd.DataFrame(data)
        return df
