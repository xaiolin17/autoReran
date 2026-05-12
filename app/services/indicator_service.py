from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import pandas as pd
from app.utils.technical_indicators import TechnicalIndicators


class IndicatorService:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_and_save_indicators(self, stock_code: str, period: str = "1d") -> None:
        """计算并保存技术指标到数据库"""
        from app.models.stock_data import StockData
        from sqlalchemy import desc
        
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(StockData.datetime)
        
        stock_data_list = query.all()
        
        if not stock_data_list:
            return
        
        data = []
        for stock in stock_data_list:
            data.append({
                'datetime': stock.datetime,
                'open_price': stock.open_price,
                'high_price': stock.high_price,
                'low_price': stock.low_price,
                'close_price': stock.close_price,
                'volume': stock.volume,
                'amount': stock.amount,
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('datetime').reset_index(drop=True)
        df = TechnicalIndicators.calculate_all_indicators(df)
        
        for i, stock in enumerate(stock_data_list):
            if i >= len(df):
                break
            
            row = df.iloc[i]
            
            if 'ma5' in row:
                stock.ma5 = float(row['ma5']) if pd.notna(row['ma5']) else None
            if 'ma10' in row:
                stock.ma10 = float(row['ma10']) if pd.notna(row['ma10']) else None
            if 'ma20' in row:
                stock.ma20 = float(row['ma20']) if pd.notna(row['ma20']) else None
            if 'ma60' in row:
                stock.ma60 = float(row['ma60']) if pd.notna(row['ma60']) else None
            
            if 'kdj_k' in row:
                stock.k = float(row['kdj_k']) if pd.notna(row['kdj_k']) else None
            if 'kdj_d' in row:
                stock.d = float(row['kdj_d']) if pd.notna(row['kdj_d']) else None
            if 'kdj_j' in row:
                stock.j = float(row['kdj_j']) if pd.notna(row['kdj_j']) else None
            
            if 'macd' in row:
                stock.macd = float(row['macd']) if pd.notna(row['macd']) else None
            if 'macd_signal' in row:
                stock.dea = float(row['macd_signal']) if pd.notna(row['macd_signal']) else None
            if 'macd_histogram' in row:
                stock.dif = float(row['macd_histogram']) if pd.notna(row['macd_histogram']) else None
            
            if 'rsi' in row:
                stock.rsi6 = float(row['rsi']) if pd.notna(row['rsi']) else None
            
            if 'bb_upper' in row:
                stock.upper = float(row['bb_upper']) if pd.notna(row['bb_upper']) else None
            if 'bb_middle' in row:
                stock.middle = float(row['bb_middle']) if pd.notna(row['bb_middle']) else None
            if 'bb_lower' in row:
                stock.lower = float(row['bb_lower']) if pd.notna(row['bb_lower']) else None
        
        self.db.commit()
    
    def get_stock_data_with_indicators(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        from app.models.stock_data import StockData
        from sqlalchemy import desc
        
        # 确保指标已计算并保存
        self.calculate_and_save_indicators(stock_code, period)
        
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        )
        
        query = query.order_by(desc(StockData.datetime))
        
        if limit:
            query = query.limit(limit)
        
        stock_data_list = query.all()
        
        if not stock_data_list:
            return []
        
        result = []
        for stock in stock_data_list:
            item = {
                'datetime': stock.datetime.isoformat() if hasattr(stock.datetime, 'isoformat') else str(stock.datetime),
                'open_price': float(stock.open_price) if stock.open_price else None,
                'high_price': float(stock.high_price) if stock.high_price else None,
                'low_price': float(stock.low_price) if stock.low_price else None,
                'close_price': float(stock.close_price) if stock.close_price else None,
                'volume': float(stock.volume) if stock.volume else None,
                'amount': float(stock.amount) if stock.amount else None,
                'ma5': float(stock.ma5) if stock.ma5 else None,
                'ma10': float(stock.ma10) if stock.ma10 else None,
                'ma20': float(stock.ma20) if stock.ma20 else None,
                'ma60': float(stock.ma60) if stock.ma60 else None,
                'kdj_k': float(stock.k) if stock.k else None,
                'kdj_d': float(stock.d) if stock.d else None,
                'kdj_j': float(stock.j) if stock.j else None,
                'macd': float(stock.macd) if stock.macd else None,
                'macd_signal': float(stock.dea) if stock.dea else None,
                'macd_histogram': float(stock.dif) if stock.dif else None,
                'rsi': float(stock.rsi6) if stock.rsi6 else None,
                'bb_upper': float(stock.upper) if stock.upper else None,
                'bb_middle': float(stock.middle) if stock.middle else None,
                'bb_lower': float(stock.lower) if stock.lower else None
            }
            
            result.append(item)
        
        return result
    
    @staticmethod
    def calculate_indicators_for_df_static(df: pd.DataFrame) -> pd.DataFrame:
        """静态方法：计算数据框的技术指标"""
        return TechnicalIndicators.calculate_all_indicators(df)
    
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
            
            if pd.notna(prev_k) and pd.notna(prev_d) and pd.notna(curr_k) and pd.notna(curr_d):
                if prev_k <= prev_d and curr_k > curr_d and curr_k < 20:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'buy',
                        'indicator': 'KDJ',
                        'reason': 'K线上穿D线，超卖区域金叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
                elif prev_k >= prev_d and curr_k < curr_d and curr_k > 80:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'sell',
                        'indicator': 'KDJ',
                        'reason': 'K线下穿D线，超买区域死叉',
                        'price': float(df.iloc[i]['close_price'])
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
            
            if pd.notna(prev_macd) and pd.notna(prev_signal) and pd.notna(curr_macd) and pd.notna(curr_signal):
                if prev_macd <= prev_signal and curr_macd > curr_signal:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'buy',
                        'indicator': 'MACD',
                        'reason': 'MACD上穿信号线，金叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
                elif prev_macd >= prev_signal and curr_macd < curr_signal:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'sell',
                        'indicator': 'MACD',
                        'reason': 'MACD下穿信号线，死叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
        
        return signals
    
    def get_all_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        kdj_signals = self.get_kdj_signals(df)
        macd_signals = self.get_macd_signals(df)
        return kdj_signals + macd_signals
