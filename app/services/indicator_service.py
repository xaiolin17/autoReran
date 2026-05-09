from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import pandas as pd
from app.services.stock_service import StockService
from app.utils.technical_indicators import TechnicalIndicators


class IndicatorService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_service = StockService(db)
    
    def get_stock_data_with_indicators(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        stock_data = self.stock_service.get_stock_data(
            stock_code, period, start_date, end_date, limit
        )
        
        if not stock_data:
            return []
        
        df = self.stock_service.to_dataframe(stock_data)
        df = TechnicalIndicators.calculate_all_indicators(df)
        
        result = []
        for _, row in df.iterrows():
            item = {
                'datetime': row['datetime'].isoformat() if hasattr(row['datetime'], 'isoformat') else str(row['datetime']),
                'open_price': float(row['open_price']),
                'high_price': float(row['high_price']),
                'low_price': float(row['low_price']),
                'close_price': float(row['close_price']),
                'volume': float(row['volume']),
                'amount': float(row['amount']) if pd.notna(row['amount']) else None
            }
            
            for col in ['kdj_k', 'kdj_d', 'kdj_j', 'macd', 'macd_signal', 'macd_histogram', 'rsi', 'bb_middle', 'bb_upper', 'bb_lower']:
                if col in row:
                    item[col] = float(row[col]) if pd.notna(row[col]) else None
            
            for col in ['ma5', 'ma10', 'ma20', 'ma60']:
                if col in row:
                    item[col] = float(row[col]) if pd.notna(row[col]) else None
            
            result.append(item)
        
        return result
    
    def calculate_indicators_for_df(self, df: pd.DataFrame) -> pd.DataFrame:
        return TechnicalIndicators.calculate_all_indicators(df)
    
    def get_kdj_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        df = TechnicalIndicators.calculate_kdj(df)
        
        for i in range(1, len(df)):
            prev_k = df.iloc[i-1]['kdj_k']
            prev_d = df.iloc[i-1]['kdj_d']
            curr_k = df.iloc[i]['kdj_k']
            curr_d = df.iloc[i]['kdj_d']
            curr_j = df.iloc[i]['kdj_j']
            
            if prev_k <= prev_d and curr_k > curr_d and curr_k < 20:
                signals.append({
                    'datetime': df.iloc[i]['datetime'],
                    'type': 'buy',
                    'indicator': 'KDJ',
                    'reason': 'K线上穿D线，超卖区域金叉',
                    'price': df.iloc[i]['close_price']
                })
            elif prev_k >= prev_d and curr_k < curr_d and curr_k > 80:
                signals.append({
                    'datetime': df.iloc[i]['datetime'],
                    'type': 'sell',
                    'indicator': 'KDJ',
                    'reason': 'K线下穿D线，超买区域死叉',
                    'price': df.iloc[i]['close_price']
                })
        
        return signals
    
    def get_macd_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        signals = []
        
        df = TechnicalIndicators.calculate_macd(df)
        
        for i in range(1, len(df)):
            prev_macd = df.iloc[i-1]['macd']
            prev_signal = df.iloc[i-1]['macd_signal']
            curr_macd = df.iloc[i]['macd']
            curr_signal = df.iloc[i]['macd_signal']
            
            if prev_macd <= prev_signal and curr_macd > curr_signal:
                signals.append({
                    'datetime': df.iloc[i]['datetime'],
                    'type': 'buy',
                    'indicator': 'MACD',
                    'reason': 'MACD上穿信号线，金叉',
                    'price': df.iloc[i]['close_price']
                })
            elif prev_macd >= prev_signal and curr_macd < curr_signal:
                signals.append({
                    'datetime': df.iloc[i]['datetime'],
                    'type': 'sell',
                    'indicator': 'MACD',
                    'reason': 'MACD下穿信号线，死叉',
                    'price': df.iloc[i]['close_price']
                })
        
        return signals
    
    def get_all_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        kdj_signals = self.get_kdj_signals(df)
        macd_signals = self.get_macd_signals(df)
        
        all_signals = kdj_signals + macd_signals
        all_signals.sort(key=lambda x: x['datetime'])
        
        return all_signals
