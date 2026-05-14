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

        required_cols = ['open_price', 'high_price', 'low_price', 'close_price', 'volume']
        available_cols = [col for col in required_cols if col in df.columns]

        if len(available_cols) < len(required_cols):
            df = df.dropna(subset=available_cols)
        else:
            df = df.dropna(subset=required_cols)

        df = df[df['volume'] >= 0]
        df = df[df['high_price'] >= df['low_price']]
        df = df[df['high_price'] >= df['open_price']]
        df = df[df['high_price'] >= df['close_price']]
        df = df[df['low_price'] <= df['open_price']]
        df = df[df['low_price'] <= df['close_price']]

        # 去除重复数据：按 stock_code + period + datetime 去重，保留第一条
        dup_cols = ['stock_code', 'period', 'datetime']
        dup_cols_available = [col for col in dup_cols if col in df.columns]
        if len(dup_cols_available) >= 2:
            before_dedup = len(df)
            df = df.drop_duplicates(subset=dup_cols_available, keep='first')
            after_dedup = len(df)
            if before_dedup != after_dedup:
                print(f"[DataProcessor] 去重: 从 {before_dedup} 条减少到 {after_dedup} 条")

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
        """不使用模拟数据，抛出异常"""
        raise RuntimeError(
            f"模拟数据已禁用，请确保 TickFlow 可用或从数据库加载数据。"
            f"股票代码: {stock_code}"
        )
