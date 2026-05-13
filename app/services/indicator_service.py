from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import pandas as pd
from app.utils.technical_indicators import TechnicalIndicators


class IndicatorService:
    def __init__(self, db: Session):
        self.db = db
    
    def _stock_list_to_dataframe(self, stock_data_list):
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
        return df.sort_values('datetime').reset_index(drop=True)
    
    def _save_indicators_to_database(self, stock_data_list, df):
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
                stock.dif = float(row['macd']) if pd.notna(row['macd']) else None
            if 'macd_signal' in row:
                stock.dea = float(row['macd_signal']) if pd.notna(row['macd_signal']) else None
            if 'macd_histogram' in row:
                stock.macd = float(row['macd_histogram']) if pd.notna(row['macd_histogram']) else None
            
            if 'rsi' in row:
                stock.rsi6 = float(row['rsi']) if pd.notna(row['rsi']) else None
            
            if 'bb_upper' in row:
                stock.upper = float(row['bb_upper']) if pd.notna(row['bb_upper']) else None
            if 'bb_middle' in row:
                stock.middle = float(row['bb_middle']) if pd.notna(row['bb_middle']) else None
            if 'bb_lower' in row:
                stock.lower = float(row['bb_lower']) if pd.notna(row['bb_lower']) else None
        
        self.db.commit()
    
    def _format_result(self, stock_data_list):
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
                'macd': float(stock.dif) if stock.dif else None,
            'macd_signal': float(stock.dea) if stock.dea else None,
            'macd_histogram': float(stock.macd) if stock.macd else None,
                'rsi': float(stock.rsi6) if stock.rsi6 else None,
                'bb_upper': float(stock.upper) if stock.upper else None,
                'bb_middle': float(stock.middle) if stock.middle else None,
                'bb_lower': float(stock.lower) if stock.lower else None
            }
            result.append(item)
        return result
    
    def _format_result_with_calculated_indicators(self, stock_data_list, df):
        result = []
        for i, stock in enumerate(stock_data_list):
            if i >= len(df):
                break
            row = df.iloc[i]
            
            item = {
                'datetime': stock.datetime.isoformat() if hasattr(stock.datetime, 'isoformat') else str(stock.datetime),
                'open_price': float(stock.open_price) if stock.open_price else None,
                'high_price': float(stock.high_price) if stock.high_price else None,
                'low_price': float(stock.low_price) if stock.low_price else None,
                'close_price': float(stock.close_price) if stock.close_price else None,
                'volume': float(stock.volume) if stock.volume else None,
                'amount': float(stock.amount) if stock.amount else None,
            }
            
            item['ma5'] = float(stock.ma5) if stock.ma5 else (float(row['ma5']) if 'ma5' in row and pd.notna(row['ma5']) else None)
            item['ma10'] = float(stock.ma10) if stock.ma10 else (float(row['ma10']) if 'ma10' in row and pd.notna(row['ma10']) else None)
            item['ma20'] = float(stock.ma20) if stock.ma20 else (float(row['ma20']) if 'ma20' in row and pd.notna(row['ma20']) else None)
            item['ma60'] = float(stock.ma60) if stock.ma60 else (float(row['ma60']) if 'ma60' in row and pd.notna(row['ma60']) else None)
            
            item['kdj_k'] = float(stock.k) if stock.k else (float(row['kdj_k']) if 'kdj_k' in row and pd.notna(row['kdj_k']) else None)
            item['kdj_d'] = float(stock.d) if stock.d else (float(row['kdj_d']) if 'kdj_d' in row and pd.notna(row['kdj_d']) else None)
            item['kdj_j'] = float(stock.j) if stock.j else (float(row['kdj_j']) if 'kdj_j' in row and pd.notna(row['kdj_j']) else None)
            
            item['macd'] = float(stock.dif) if stock.dif else (float(row['macd']) if 'macd' in row and pd.notna(row['macd']) else None)
            item['macd_signal'] = float(stock.dea) if stock.dea else (float(row['macd_signal']) if 'macd_signal' in row and pd.notna(row['macd_signal']) else None)
            item['macd_histogram'] = float(stock.macd) if stock.macd else (float(row['macd_histogram']) if 'macd_histogram' in row and pd.notna(row['macd_histogram']) else None)
            
            item['rsi'] = float(stock.rsi6) if stock.rsi6 else (float(row['rsi']) if 'rsi' in row and pd.notna(row['rsi']) else None)
            
            item['bb_upper'] = float(stock.upper) if stock.upper else (float(row['bb_upper']) if 'bb_upper' in row and pd.notna(row['bb_upper']) else None)
            item['bb_middle'] = float(stock.middle) if stock.middle else (float(row['bb_middle']) if 'bb_middle' in row and pd.notna(row['bb_middle']) else None)
            item['bb_lower'] = float(stock.lower) if stock.lower else (float(row['bb_lower']) if 'bb_lower' in row and pd.notna(row['bb_lower']) else None)
            
            result.append(item)
        return result
    
    def get_stock_data_with_indicators(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        auto_save: bool = True
    ) -> List[Dict[str, Any]]:
        from app.models.stock_data import StockData
        from sqlalchemy import desc
        
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        )
        
        if limit:
            query = query.order_by(StockData.datetime).limit(limit)
        else:
            query = query.order_by(StockData.datetime)
        
        stock_data_list = query.all()
        
        if not stock_data_list:
            return []
        
        has_missing_indicators = False
        for stock in stock_data_list:
            if (stock.ma5 is None or stock.k is None or stock.macd is None):
                has_missing_indicators = True
                break
        
        if not has_missing_indicators:
            return self._format_result(stock_data_list)
        
        from app.core.logger import logger
        logger.info(f"检测到缺失指标，开始计算: {stock_code} {period}")
        df = self._stock_list_to_dataframe(stock_data_list)
        df = TechnicalIndicators.calculate_all_indicators(df)
        
        if auto_save:
            self._save_indicators_to_database(stock_data_list, df)
        
        return self._format_result_with_calculated_indicators(stock_data_list, df)
    
    def calculate_and_save_indicators(self, stock_code: str, period: str = "1d"):
        from app.models.stock_data import StockData
        from sqlalchemy import desc
        
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(StockData.datetime)
        
        stock_data_list = query.all()
        
        if not stock_data_list:
            return 0
        
        df = self._stock_list_to_dataframe(stock_data_list)
        df = TechnicalIndicators.calculate_all_indicators(df)
        
        self._save_indicators_to_database(stock_data_list, df)
        return len(stock_data_list)
    
    @staticmethod
    def calculate_indicators_for_df_static(df: pd.DataFrame) -> pd.DataFrame:
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
