from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np
import joblib
import os
from app.models.backtest_result import BacktestResult
from app.models.ml_model import MLModel
from app.schemas.backtest import BacktestResultCreate, BacktestRequest
from app.services.stock_service import StockService
from app.services.indicator_service import IndicatorService
from app.utils.technical_indicators import TechnicalIndicators


class BacktestService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_service = StockService(db)
        self.indicator_service = IndicatorService(db)
    
    def run_backtest(self, request: BacktestRequest) -> BacktestResult:
        stock_data = self.stock_service.get_stock_data(request.stock_code, "1d")
        
        if len(stock_data) < 100:
            raise ValueError("数据量不足，至少需要100条数据")
        
        df = self.stock_service.to_dataframe(stock_data)
        df = TechnicalIndicators.calculate_all_indicators(df)
        
        if request.start_date:
            df = df[df['datetime'] >= pd.to_datetime(request.start_date)]
        if request.end_date:
            df = df[df['datetime'] <= pd.to_datetime(request.end_date)]
        
        if len(df) < 50:
            raise ValueError("指定日期范围内数据不足")
        
        # 如果指定了模型，使用模型生成信号
        if request.model_id:
            signals = self._generate_model_signals(df, request.model_id)
        else:
            signals = self._generate_signals(df, request.strategy_name, request.params or {})
        
        backtest_result = self._execute_trades(df, signals, request.initial_capital)
        
        db_backtest = BacktestResult()
        db_backtest.stock_code = request.stock_code
        db_backtest.strategy_name = request.strategy_name
        db_backtest.model_id = request.model_id
        db_backtest.start_date = df.iloc[0]['datetime'].isoformat() if hasattr(df.iloc[0]['datetime'], 'isoformat') else str(df.iloc[0]['datetime'])
        db_backtest.end_date = df.iloc[-1]['datetime'].isoformat() if hasattr(df.iloc[-1]['datetime'], 'isoformat') else str(df.iloc[-1]['datetime'])
        db_backtest.initial_capital = request.initial_capital
        db_backtest.final_capital = backtest_result['final_capital']
        db_backtest.total_return = backtest_result['total_return']
        db_backtest.annual_return = backtest_result['annual_return']
        db_backtest.max_drawdown = backtest_result['max_drawdown']
        db_backtest.win_rate = backtest_result['win_rate']
        db_backtest.total_trades = backtest_result['total_trades']
        db_backtest.trade_log = backtest_result['trade_log']
        db_backtest.created_at = datetime.now()
        
        self.db.add(db_backtest)
        self.db.commit()
        self.db.refresh(db_backtest)
        
        return db_backtest
    
    def _generate_model_signals(self, df: pd.DataFrame, model_id: int) -> List[Dict]:
        """使用训练好的模型生成买卖信号"""
        db_model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not db_model:
            raise ValueError("模型不存在")
        
        if not os.path.exists(db_model.file_path):
            raise ValueError("模型文件不存在")
        
        model = joblib.load(db_model.file_path)
        
        signals = []
        feature_columns = db_model.feature_columns or []
        
        # 同时适配两种命名方式
        column_mapping = {
            'open_price': 'open',
            'high_price': 'high', 
            'low_price': 'low',
            'close_price': 'close',
            'volume': 'volume'
        }
        
        available_features = []
        for col in feature_columns:
            if col in df.columns:
                available_features.append(col)
            elif col in column_mapping and column_mapping[col] in df.columns:
                available_features.append(column_mapping[col])
        
        if len(available_features) == 0:
            available_features = [col for col in ['open', 'high', 'low', 'close', 'volume'] if col in df.columns]
        
        # 确定价格列 - 优先使用 close_price，否则用 close
        price_col = 'close_price' if 'close_price' in df.columns else 'close'
        
        # 遍历数据，使用模型进行预测并生成信号
        for i in range(1, len(df) - 1):
            if i < 20:  # 留出足够的数据用于计算指标
                continue
            
            current_data = df.iloc[i:i+1][available_features]
            
            if len(current_data.dropna()) == 0:
                continue
            
            try:
                predicted_price = model.predict(current_data)[0]
                current_price = df.iloc[i][price_col]
                
                # 简单的信号生成策略：预测价格上涨超过一定幅度就买入，下跌就卖出
                price_change = (predicted_price - current_price) / current_price
                
                if price_change > 0.02:  # 预测上涨超过 2%，买入
                    signals.append({
                        'datetime': df.iloc[i]['datetime'],
                        'type': 'buy',
                        'indicator': 'MODEL',
                        'reason': f'Model prediction: {predicted_price:.2f} vs current: {current_price:.2f}',
                        'price': current_price
                    })
                elif price_change < -0.02:  # 预测下跌超过 2%，卖出
                    signals.append({
                        'datetime': df.iloc[i]['datetime'],
                        'type': 'sell',
                        'indicator': 'MODEL',
                        'reason': f'Model prediction: {predicted_price:.2f} vs current: {current_price:.2f}',
                        'price': current_price
                    })
            except Exception:
                continue
        
        signals.sort(key=lambda x: x['datetime'])
        return signals
    
    def _generate_signals(self, df: pd.DataFrame, strategy_name: str, params: Dict) -> List[Dict]:
        signals = []
        
        if strategy_name == "KDJ":
            kdj_signals = self.indicator_service.get_kdj_signals(df)
            signals.extend(kdj_signals)
        elif strategy_name == "MACD":
            macd_signals = self.indicator_service.get_macd_signals(df)
            signals.extend(macd_signals)
        elif strategy_name == "KDJ_MACD":
            kdj_signals = self.indicator_service.get_kdj_signals(df)
            macd_signals = self.indicator_service.get_macd_signals(df)
            signals.extend(kdj_signals)
            signals.extend(macd_signals)
        else:
            # 确保指标存在
            if 'kdj_k' not in df.columns or 'kdj_d' not in df.columns:
                df = TechnicalIndicators.calculate_kdj(df)
            if 'macd' not in df.columns:
                df = TechnicalIndicators.calculate_macd(df)
            
            # 确定价格列
            price_col = 'close_price' if 'close_price' in df.columns else 'close'
            
            for i in range(1, len(df)):
                prev_k = df.iloc[i-1].get('kdj_k', 50)
                prev_d = df.iloc[i-1].get('kdj_d', 50)
                curr_k = df.iloc[i].get('kdj_k', 50)
                curr_d = df.iloc[i].get('kdj_d', 50)
                
                if prev_k <= prev_d and curr_k > curr_d:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'],
                        'type': 'buy',
                        'indicator': 'DEFAULT',
                        'reason': 'Default buy signal',
                        'price': df.iloc[i][price_col]
                    })
                elif prev_k >= prev_d and curr_k < curr_d:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'],
                        'type': 'sell',
                        'indicator': 'DEFAULT',
                        'reason': 'Default sell signal',
                        'price': df.iloc[i][price_col]
                    })
        
        signals.sort(key=lambda x: x['datetime'])
        return signals
    
    def _execute_trades(self, df: pd.DataFrame, signals: List[Dict], initial_capital: float) -> Dict:
        capital = initial_capital
        position = 0
        entry_price = 0
        trades = []
        equity_curve = [capital]
        dates = [df.iloc[0]['datetime']]
        
        # 确定价格列
        price_col = 'close_price' if 'close_price' in df.columns else 'close'
        
        df_dict = {row['datetime']: row for _, row in df.iterrows()}
        
        for signal in signals:
            signal_datetime = signal['datetime']
            if signal_datetime not in df_dict:
                continue
            
            price = signal['price']
            
            if signal['type'] == 'buy' and position == 0:
                position = int(capital / price / 100) * 100
                if position > 0:
                    capital -= position * price
                    entry_price = price
                    trades.append({
                        'datetime': signal_datetime.isoformat() if hasattr(signal_datetime, 'isoformat') else str(signal_datetime),
                        'action': 'buy',
                        'price': price,
                        'shares': position,
                        'reason': signal['reason']
                    })
            elif signal['type'] == 'sell' and position > 0:
                capital += position * price
                profit = (price - entry_price) * position
                trades.append({
                    'datetime': signal_datetime.isoformat() if hasattr(signal_datetime, 'isoformat') else str(signal_datetime),
                    'action': 'sell',
                    'price': price,
                    'shares': position,
                    'profit': profit,
                    'reason': signal['reason']
                })
                position = 0
        
        if position > 0:
            last_price = df.iloc[-1][price_col]
            capital += position * last_price
        
        final_capital = capital
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        days = (df.iloc[-1]['datetime'] - df.iloc[0]['datetime']).days
        annual_return = 0
        if days > 0:
            annual_return = ((final_capital / initial_capital) ** (365 / days) - 1) * 100
        
        winning_trades = 0
        losing_trades = 0
        for trade in trades:
            if trade['action'] == 'sell' and 'profit' in trade:
                if trade['profit'] > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
        
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        equity = initial_capital
        peak = initial_capital
        max_drawdown = 0
        temp_position = 0
        temp_entry = 0
        
        for _, row in df.iterrows():
            price = row[price_col]
            
            for signal in signals:
                if signal['datetime'] == row['datetime']:
                    if signal['type'] == 'buy' and temp_position == 0:
                        temp_position = int(equity / price / 100) * 100
                        if temp_position > 0:
                            equity -= temp_position * price
                            temp_entry = price
                    elif signal['type'] == 'sell' and temp_position > 0:
                        equity += temp_position * price
                        temp_position = 0
            
            current_equity = equity
            if temp_position > 0:
                current_equity += temp_position * price
            
            if current_equity > peak:
                peak = current_equity
            
            drawdown = (peak - current_equity) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            'final_capital': final_capital,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'trade_log': trades
        }
    
    def get_backtests(self, stock_code: Optional[str] = None) -> List[BacktestResult]:
        query = self.db.query(BacktestResult)
        if stock_code:
            query = query.filter(BacktestResult.stock_code == stock_code)
        return query.order_by(BacktestResult.created_at.desc()).all()
    
    def get_backtest(self, backtest_id: int) -> Optional[BacktestResult]:
        return self.db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    
    def delete_backtest(self, backtest_id: int) -> bool:
        db_backtest = self.db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
        if db_backtest:
            self.db.delete(db_backtest)
            self.db.commit()
            return True
        return False
