from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score
)
import joblib
import os
from app.models.ml_model import MLModel
from app.schemas.ml import (
    MLModelCreate,
    TrainingRequest,
    SignalPrediction,
    EnsemblePredictionRequest,
    EnsemblePredictionResponse,
    ModelPredictionDetail,
    ModelWeightConfig
)
from app.services.stock_service import StockService
from app.utils.technical_indicators import TechnicalIndicators
from app.core.logger import logger
from app.core.config import settings


class MLService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_service = StockService(db)
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
    
    def train_model(self, request: TrainingRequest) -> MLModel:
        logger.info(f"开始训练模型: {request.model_name}, 股票: {request.stock_code}")
        
        stock_data = self.stock_service.get_stock_data(
            request.stock_code, "1d", limit=1000
        )
        
        if len(stock_data) < 100:
            raise ValueError("数据量不足，至少需要100条数据")
        
        df = self.stock_service.to_dataframe(stock_data)
        df = TechnicalIndicators.calculate_all_indicators(df)
        df = df.dropna()
        
        if len(df) < 50:
            raise ValueError("有效数据不足，无法训练")
        
        feature_columns = request.feature_columns or [
            'open_price', 'high_price', 'low_price', 'close_price', 'volume',
            'kdj_k', 'kdj_d', 'kdj_j', 'macd', 'macd_signal', 'macd_histogram',
            'rsi', 'ma5', 'ma10', 'ma20'
        ]
        
        available_features = [col for col in feature_columns if col in df.columns]
        logger.debug(f"使用特征: {available_features}")
        
        if request.is_classification:
            # 分类模型：预测涨跌（1=涨，0=跌）
            df['target'] = (df['close_price'].shift(-1) > df['close_price']).astype(int)
            df = df.dropna()
            
            X = df[available_features]
            y = df['target']
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, train_size=request.train_size, shuffle=False
            )
            
            if request.model_type == "RandomForest":
                model = RandomForestClassifier(n_estimators=100, random_state=42)
            else:
                model = LogisticRegression(max_iter=1000)
            
            model.fit(X_train, y_train)
            
            y_pred = model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            
            logger.info(f"分类模型训练完成 - Accuracy: {accuracy:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}")
            
            description = f"Classification model trained with {len(X_train)} samples. Accuracy: {accuracy:.4f}"
        else:
            # 回归模型：预测价格
            df['target'] = df['close_price'].shift(-1)
            df = df.dropna()
            
            X = df[available_features]
            y = df['target']
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, train_size=request.train_size, shuffle=False
            )
            
            if request.model_type == "RandomForest":
                model = RandomForestRegressor(n_estimators=100, random_state=42)
            else:
                model = LinearRegression()
            
            model.fit(X_train, y_train)
            
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            accuracy = r2
            precision = 1 - mae / y.mean() if y.mean() != 0 else 0
            recall = 1 - np.sqrt(mse) / y.mean() if y.mean() != 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            logger.info(f"回归模型训练完成 - R2: {r2:.4f}, MSE: {mse:.4f}, MAE: {mae:.4f}")
            
            description = f"Regression model trained with {len(X_train)} samples. R2: {r2:.4f}"
        
        model_filename = f"{request.model_name}_{request.stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        model_path = os.path.join(settings.MODELS_DIR, model_filename)
        joblib.dump({
            'model': model,
            'is_classification': request.is_classification,
            'feature_columns': available_features
        }, model_path)
        
        db_model = MLModelCreate(
            model_name=request.model_name,
            stock_code=request.stock_code,
            model_type=request.model_type,
            feature_columns=available_features,
            target_column=request.target_column,
            model_path=model_path,
            description=description
        )
        
        db_ml_model = MLModel(**db_model.model_dump())
        db_ml_model.accuracy = accuracy
        db_ml_model.precision = precision
        db_ml_model.recall = recall
        db_ml_model.f1_score = f1
        db_ml_model.created_at = datetime.now()
        
        self.db.add(db_ml_model)
        self.db.commit()
        self.db.refresh(db_ml_model)
        
        logger.info(f"模型已保存: {db_ml_model.id}")
        return db_ml_model
    
    def predict(self, model_id: int, stock_code: str) -> Dict[str, Any]:
        logger.info(f"模型预测: model_id={model_id}, stock_code={stock_code}")
        
        db_model = self.db.get(MLModel, model_id)
        if not db_model:
            raise ValueError("模型不存在")
        
        if not os.path.exists(db_model.model_path):
            raise ValueError("模型文件不存在")
        
        model_data = joblib.load(db_model.model_path)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
        is_classification = model_data.get('is_classification', False) if isinstance(model_data, dict) else False
        
        stock_data = self.stock_service.get_stock_data(stock_code, "1d", limit=100)
        if not stock_data:
            raise ValueError("没有可用的股票数据")
        
        df = self.stock_service.to_dataframe(stock_data)
        df = TechnicalIndicators.calculate_all_indicators(df)
        df = df.dropna()
        
        if len(df) == 0:
            raise ValueError("有效数据不足")
        
        feature_columns = db_model.feature_columns or []
        available_features = [col for col in feature_columns if col in df.columns]
        
        if not available_features:
            raise ValueError("特征列不可用")
        
        latest_data = df.iloc[-1:][available_features]
        prediction = model.predict(latest_data)[0]
        
        current_price = df.iloc[-1]['close_price']
        
        if is_classification:
            # 分类预测
            result = {
                'model_id': model_id,
                'stock_code': stock_code,
                'current_price': float(current_price),
                'prediction': int(prediction),  # 1=涨, 0=跌
                'prediction_date': datetime.now().isoformat()
            }
        else:
            # 回归预测
            change_percent = ((prediction - current_price) / current_price) * 100
            result = {
                'model_id': model_id,
                'stock_code': stock_code,
                'current_price': float(current_price),
                'predicted_price': float(prediction),
                'change_percent': float(change_percent),
                'prediction_date': datetime.now().isoformat()
            }
        
        logger.info(f"预测完成: {result}")
        return result
    
    def predict_signal(self, model_id: int, stock_code: str) -> SignalPrediction:
        """
        专业多空信号预测：BUY/SELL/HOLD
        
        返回:
            signal: 交易信号
            signal_strength: 信号强度 0-100
            confidence: 置信度 0-1
            signal_explanation: 信号解释
        """
        logger.info(f"多空信号预测: model_id={model_id}, stock_code={stock_code}")
        
        db_model = self.db.get(MLModel, model_id)
        if not db_model:
            raise ValueError("模型不存在")
        
        if not os.path.exists(db_model.model_path):
            raise ValueError("模型文件不存在")
        
        # 加载模型
        model_data = joblib.load(db_model.model_path)
        model = model_data.get('model', model_data) if isinstance(model_data, dict) else model_data
        is_classification = model_data.get('is_classification', False) if isinstance(model_data, dict) else False
        
        # 获取最新数据
        stock_data = self.stock_service.get_stock_data(stock_code, "1d", limit=100)
        if not stock_data:
            raise ValueError("没有可用的股票数据")
        
        df = self.stock_service.to_dataframe(stock_data)
        df = TechnicalIndicators.calculate_all_indicators(df)
        df = df.dropna()
        
        if len(df) < 20:
            raise ValueError("有效数据不足，需要至少20条数据")
        
        # 获取特征
        feature_columns = db_model.feature_columns or []
        available_features = [col for col in feature_columns if col in df.columns]
        
        if not available_features:
            raise ValueError("特征列不可用")
        
        # 获取最新数据点
        latest_idx = -1
        latest_data = df.iloc[latest_idx:latest_idx+1][available_features]
        current_price = float(df.iloc[latest_idx]['close_price'])
        
        # 提取技术指标用于解释
        tech_indicators = {}
        if 'rsi' in df.columns:
            tech_indicators['rsi'] = float(df.iloc[latest_idx]['rsi'])
        if 'kdj_k' in df.columns:
            tech_indicators['kdj_k'] = float(df.iloc[latest_idx]['kdj_k'])
        if 'kdj_d' in df.columns:
            tech_indicators['kdj_d'] = float(df.iloc[latest_idx]['kdj_d'])
        if 'macd' in df.columns:
            tech_indicators['macd'] = float(df.iloc[latest_idx]['macd'])
        
        # 执行预测
        signal = "HOLD"
        signal_strength = 50.0
        confidence = 0.5
        predicted_price = None
        predicted_change_percent = None
        explanation = ""
        
        if is_classification:
            # 分类模型预测涨跌
            prediction = model.predict(latest_data)[0]
            prediction_proba = None
            
            if hasattr(model, 'predict_proba'):
                prediction_proba = model.predict_proba(latest_data)[0]
                confidence = float(np.max(prediction_proba))
            else:
                confidence = 0.6  # 默认置信度
            
            if prediction == 1:
                # 看涨信号
                signal = "BUY"
                signal_strength = min(100.0, 50 + confidence * 50)
                explanation = f"模型预测价格上涨，置信度 {confidence:.1%}。"
                
                # RSI 增强逻辑
                if 'rsi' in tech_indicators and tech_indicators['rsi'] < 30:
                    signal_strength = min(100.0, signal_strength + 20)
                    explanation += f"RSI({tech_indicators['rsi']:.1f})处于超卖区间，增强买入信号。"
                elif 'rsi' in tech_indicators and tech_indicators['rsi'] < 40:
                    signal_strength = min(100.0, signal_strength + 10)
                
            else:
                # 看跌信号
                signal = "SELL"
                signal_strength = min(100.0, 50 + confidence * 50)
                explanation = f"模型预测价格下跌，置信度 {confidence:.1%}。"
                
                if 'rsi' in tech_indicators and tech_indicators['rsi'] > 70:
                    signal_strength = min(100.0, signal_strength + 20)
                    explanation += f"RSI({tech_indicators['rsi']:.1f})处于超买区间，增强卖出信号。"
                elif 'rsi' in tech_indicators and tech_indicators['rsi'] > 60:
                    signal_strength = min(100.0, signal_strength + 10)
        
        else:
            # 回归模型预测价格
            predicted_price = float(model.predict(latest_data)[0])
            predicted_change_percent = ((predicted_price - current_price) / current_price) * 100
            
            # 基于涨跌幅确定信号
            if predicted_change_percent > 1.0:
                signal = "BUY"
                signal_strength = min(100.0, 50 + abs(predicted_change_percent) * 10)
                explanation = f"模型预测上涨 {predicted_change_percent:+.2f}%，建议买入。"
            elif predicted_change_percent < -1.0:
                signal = "SELL"
                signal_strength = min(100.0, 50 + abs(predicted_change_percent) * 10)
                explanation = f"模型预测下跌 {predicted_change_percent:+.2f}%，建议卖出。"
            else:
                signal = "HOLD"
                signal_strength = 50.0 - abs(predicted_change_percent) * 5
                explanation = f"预测波动较小 ({predicted_change_percent:+.2f}%)，建议持有观望。"
            
            # 使用模型准确性作为置信度
            confidence = max(0.3, min(0.95, db_model.accuracy or 0.5))
        
        # KDJ 增强逻辑
        if 'kdj_k' in tech_indicators and 'kdj_d' in tech_indicators:
            k, d = tech_indicators['kdj_k'], tech_indicators['kdj_d']
            if signal == "BUY" and k > d:
                signal_strength = min(100.0, signal_strength + 10)
                explanation += f"KDJ金叉，增强买入信号。"
            elif signal == "SELL" and k < d:
                signal_strength = min(100.0, signal_strength + 10)
                explanation += f"KDJ死叉，增强卖出信号。"
        
        logger.info(f"信号预测完成: {signal}, 强度={signal_strength:.1f}, 置信度={confidence:.2f}")
        
        return SignalPrediction(
            model_id=model_id,
            stock_code=stock_code,
            signal=signal,
            signal_strength=round(signal_strength, 1),
            confidence=round(confidence, 2),
            current_price=current_price,
            predicted_price=predicted_price,
            predicted_change_percent=predicted_change_percent,
            prediction_date=datetime.now(),
            signal_explanation=explanation,
            technical_indicators=tech_indicators
        )

    def ensemble_predict(self, request: EnsemblePredictionRequest) -> EnsemblePredictionResponse:
        """
        多模型综合预测
        
        支持两种方式：
        - voting（投票制）：多数模型胜出
        - weighted（加权制）：按权重和准确率综合
        
        Returns:
            EnsemblePredictionResponse: 综合预测结果，包含各模型详情
        """
        logger.info(f"开始多模型综合预测: 模型数={len(request.model_ids)}, 方法={request.ensemble_method}")
        
        # 获取所有模型
        models = []
        for model_id in request.model_ids:
            db_model = self.db.get(MLModel, model_id)
            if not db_model:
                logger.warning(f"模型不存在，跳过: {model_id}")
                continue
            models.append(db_model)
        
        if not models:
            raise ValueError("没有找到可用的模型")
        
        # 获取权重配置
        weight_map = {}
        if request.model_weights:
            weight_map = {w.model_id: w.weight for w in request.model_weights}
        
        # 对每个模型进行预测
        all_predictions = []
        current_price = 0.0
        all_changes = []
        
        for db_model in models:
            try:
                # 单个模型预测
                single_result = self.predict_signal(db_model.id, request.stock_code)
                
                if current_price == 0:
                    current_price = single_result.current_price
                
                # 获取权重
                weight = weight_map.get(db_model.id, 1.0)
                
                # 如果是加权模式，按准确率自动调整权重
                if request.ensemble_method == "weighted" and not weight_map:
                    weight = max(0.5, (db_model.accuracy or 0.5))  # 准确率作为权重
                
                # 收集预测详情
                all_predictions.append(ModelPredictionDetail(
                    model_id=db_model.id,
                    model_name=db_model.model_name,
                    model_type=db_model.model_type,
                    accuracy=db_model.accuracy,
                    signal=single_result.signal,
                    signal_strength=single_result.signal_strength,
                    confidence=single_result.confidence,
                    weight=weight
                ))
                
                # 收集预测的涨跌幅
                if single_result.predicted_change_percent is not None:
                    all_changes.append(single_result.predicted_change_percent)
                
            except Exception as e:
                logger.warning(f"模型预测失败: {db_model.model_name} - {str(e)}")
        
        if not all_predictions:
            raise ValueError("没有模型能够成功预测")
        
        # 统计信号分布
        signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        signal_weighted_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        
        for pred in all_predictions:
            signal_counts[pred.signal] += 1
            weight = pred.weight or 1.0
            signal_weighted_scores[pred.signal] += pred.signal_strength * weight
        
        # 确定最终信号
        if request.ensemble_method == "weighted":
            # 加权模式：找得分最高的信号
            final_signal = max(signal_weighted_scores.items(), key=lambda x: x[1])[0]
            max_score = max(signal_weighted_scores.values())
            total_score = sum(signal_weighted_scores.values())
            final_strength = (max_score / total_score) * 100 if total_score > 0 else 50.0
        else:
            # 投票模式：多数决定
            final_signal = max(signal_counts.items(), key=lambda x: x[1])[0]
            max_count = max(signal_counts.values())
            final_strength = (max_count / len(all_predictions)) * 100
        
        # 计算综合置信度
        total_confidence = sum(p.confidence * (p.weight or 1.0) for p in all_predictions)
        total_weight = sum(p.weight or 1.0 for p in all_predictions)
        avg_confidence = total_confidence / total_weight if total_weight > 0 else 0.5
        
        # 计算综合预测涨跌幅（如果有）
        avg_change = sum(all_changes) / len(all_changes) if all_changes else None
        
        # 生成综合解释
        explanation = self._generate_ensemble_explanation(
            final_signal, signal_counts, signal_weighted_scores,
            request.ensemble_method, len(all_predictions)
        )
        
        logger.info(f"多模型综合预测完成: 最终信号={final_signal}, 强度={final_strength:.1f}%")
        
        return EnsemblePredictionResponse(
            stock_code=request.stock_code,
            final_signal=final_signal,
            final_signal_strength=round(final_strength, 1),
            confidence=round(avg_confidence, 2),
            current_price=current_price,
            predicted_change_percent=round(avg_change, 2) if avg_change is not None else None,
            prediction_date=datetime.now(),
            ensemble_method=request.ensemble_method,
            model_predictions=all_predictions,
            consensus_explanation=explanation,
            signal_breakdown=signal_counts
        )

    def _generate_ensemble_explanation(
        self,
        final_signal: str,
        signal_counts: Dict[str, int],
        signal_weighted_scores: Dict[str, float],
        ensemble_method: str,
        model_count: int
    ) -> str:
        """生成综合预测的解释文本"""
        explanation = []
        
        if ensemble_method == "voting":
            explanation.append(f"基于 {model_count} 个模型投票决策。")
            
            buy_count = signal_counts.get("BUY", 0)
            sell_count = signal_counts.get("SELL", 0)
            hold_count = signal_counts.get("HOLD", 0)
            
            if final_signal == "BUY":
                explanation.append(f"{buy_count} 个模型看多，{sell_count} 个看空，{hold_count} 个看平。")
            elif final_signal == "SELL":
                explanation.append(f"{sell_count} 个模型看空，{buy_count} 个看多，{hold_count} 个看平。")
            else:
                explanation.append("多数模型认为当前应观望。")
        
        else:  # weighted
            explanation.append(f"基于 {model_count} 个模型加权决策。")
            
            total_score = sum(signal_weighted_scores.values())
            buy_score = signal_weighted_scores.get("BUY", 0)
            sell_score = signal_weighted_scores.get("SELL", 0)
            
            if final_signal == "BUY":
                explanation.append(f"看多得分 {buy_score:.1f}，看空得分 {sell_score:.1f}。")
            elif final_signal == "SELL":
                explanation.append(f"看空得分 {sell_score:.1f}，看多得分 {buy_score:.1f}。")
        
        if final_signal == "BUY":
            explanation.append("综合判断为做多信号。")
        elif final_signal == "SELL":
            explanation.append("综合判断为做空信号。")
        else:
            explanation.append("综合判断为观望信号。")
        
        return " ".join(explanation)
    
    def get_models(self, stock_code: Optional[str] = None) -> List[MLModel]:
        query = select(MLModel)
        if stock_code:
            query = query.where(MLModel.stock_code == stock_code)
        query = query.order_by(desc(MLModel.created_at))
        
        return self.db.execute(query).scalars().all()
    
    def get_model(self, model_id: int) -> Optional[MLModel]:
        return self.db.get(MLModel, model_id)
    
    def delete_model(self, model_id: int) -> bool:
        db_model = self.db.get(MLModel, model_id)
        if db_model:
            if db_model.model_path and os.path.exists(db_model.model_path):
                os.remove(db_model.model_path)
                logger.debug(f"删除模型文件: {db_model.model_path}")
            self.db.delete(db_model)
            self.db.commit()
            logger.info(f"删除模型: {model_id}")
            return True
        return False
