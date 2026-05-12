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
        np.random.seed(42)
        
        # 设置正确的股票基础价格
        stock_configs = {
            "000001": {"name": "上证指数", "base": 3250.0, "volatility": 0.012},
            "399001": {"name": "深证成指", "base": 10600.0, "volatility": 0.015},
            "600519": {"name": "贵州茅台", "base": 1680.0, "volatility": 0.018},
            "000002": {"name": "万科A", "base": 11.5, "volatility": 0.022},
        }
        
        config = stock_configs.get(stock_code, {
            "name": f"Stock{stock_code}", 
            "base": 100.0, 
            "volatility": 0.02
        })
        
        base_price = base_price or config["base"]
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # 生成更真实的价格走势
        prices = [base_price]
        for _ in range(1, len(date_range)):
            # 使用随机游走
            change = np.random.normal(0, config["volatility"])
            new_price = prices[-1] * (1 + change)
            
            # 限制价格范围在合理区间
            new_price = max(new_price, base_price * 0.7)
            new_price = min(new_price, base_price * 1.3)
            prices.append(new_price)
        
        data = []
        for i, date in enumerate(date_range):
            price = prices[i]
            
            # 生成合理的OHLC
            open_change = np.random.uniform(-config["volatility"] * 0.3, config["volatility"] * 0.3)
            open_p = price * (1 + open_change)
            
            close_change = np.random.uniform(-config["volatility"] * 0.5, config["volatility"] * 0.5)
            close_p = open_p * (1 + close_change)
            
            high_spread = np.random.uniform(0, config["volatility"])
            low_spread = np.random.uniform(0, config["volatility"])
            
            high_p = max(open_p, close_p) * (1 + high_spread)
            low_p = min(open_p, close_p) * (1 - low_spread)
            
            volume = np.random.randint(5000000, 50000000)
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
                'stock_name': config["name"],
                'period': period,
                'source': 'reliable_mock'
            })
        
        df = pd.DataFrame(data)
        print(f"✅ 生成 {stock_code} ({config['name']}) 数据: {len(df)} 条, 价格范围: {df['close_price'].min():.2f} - {df['close_price'].max():.2f}")
        return df
