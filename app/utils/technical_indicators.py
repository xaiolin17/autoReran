import pandas as pd
import numpy as np
from typing import Optional, Tuple
from app.core.logger import logger


class TechnicalIndicators:
    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        logger.debug(f"开始计算KDJ指标: 数据条数={len(df)}, 参数n={n}, m1={m1}, m2={m2}")
        
        if df.empty:
            logger.warning("输入数据为空，返回带有NaN值的KDJ列")
            df['kdj_k'] = np.nan
            df['kdj_d'] = np.nan
            df['kdj_j'] = np.nan
            return df
        
        df = df.copy()
        
        low_list = df['low_price'].rolling(n, min_periods=1).min()
        high_list = df['high_price'].rolling(n, min_periods=1).max()
        
        rsv = (df['close_price'] - low_list) / (high_list - low_list) * 100
        rsv = rsv.fillna(50)
        
        df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
        
        logger.debug(f"KDJ指标计算完成")
        return df
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        if df.empty:
            df['macd'] = np.nan
            df['macd_signal'] = np.nan
            df['macd_histogram'] = np.nan
            return df
        
        df = df.copy()
        
        ema_fast = df['close_price'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close_price'].ewm(span=slow, adjust=False).mean()
        
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        return df
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        if df.empty:
            df['rsi'] = np.nan
            return df
        
        df = df.copy()
        
        delta = df['close_price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> pd.DataFrame:
        if df.empty:
            df['bb_middle'] = np.nan
            df['bb_upper'] = np.nan
            df['bb_lower'] = np.nan
            return df
        
        df = df.copy()
        
        df['bb_middle'] = df['close_price'].rolling(window=period).mean()
        std = df['close_price'].rolling(window=period).std()
        
        df['bb_upper'] = df['bb_middle'] + (std * std_dev)
        df['bb_lower'] = df['bb_middle'] - (std * std_dev)
        
        return df
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        if df.empty:
            for period in periods:
                df[f'ma{period}'] = np.nan
            return df
        
        df = df.copy()
        
        for period in periods:
            df[f'ma{period}'] = df['close_price'].rolling(window=period).mean()
        
        return df
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        logger.info(f"开始计算所有技术指标: 数据条数={len(df)}")
        
        if df.empty:
            logger.warning("输入数据为空，直接返回")
            return df
        
        df = df.copy()
        logger.debug("开始计算KDJ指标")
        df = TechnicalIndicators.calculate_kdj(df)
        logger.debug("开始计算MACD指标")
        df = TechnicalIndicators.calculate_macd(df)
        logger.debug("开始计算RSI指标")
        df = TechnicalIndicators.calculate_rsi(df)
        logger.debug("开始计算布林带指标")
        df = TechnicalIndicators.calculate_bollinger_bands(df)
        logger.debug("开始计算移动平均线指标")
        df = TechnicalIndicators.calculate_ma(df)
        
        logger.info(f"所有技术指标计算完成")
        return df
    
    @staticmethod
    def convert_period(df: pd.DataFrame, target_period: str) -> pd.DataFrame:
        if df.empty:
            return df
        
        df = df.copy()
        df = df.set_index('datetime')
        
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
        
        if 'stock_code' in df.columns:
            resampled['stock_code'] = df['stock_code'].iloc[0]
        if 'stock_name' in df.columns:
            resampled['stock_name'] = df['stock_name'].iloc[0]
        
        resampled['period'] = target_period
        resampled = resampled.reset_index()
        
        return resampled