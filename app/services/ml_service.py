from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import os
from app.models.ml_model import MLModel
from app.schemas.ml import MLModelCreate, TrainingRequest
from app.services.stock_service import StockService
from app.utils.technical_indicators import TechnicalIndicators


class MLService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_service = StockService(db)
        self.models_dir = "models"
        os.makedirs(self.models_dir, exist_ok=True)
    
    def train_model(self, request: TrainingRequest) -> MLModel:
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
        
        model_filename = f"{request.model_name}_{request.stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        model_path = os.path.join(self.models_dir, model_filename)
        joblib.dump(model, model_path)
        
        db_model = MLModelCreate(
            model_name=request.model_name,
            stock_code=request.stock_code,
            model_type=request.model_type,
            feature_columns=available_features,
            target_column=request.target_column,
            model_path=model_path,
            description=f"Model trained with {len(X_train)} samples. R2: {r2:.4f}"
        )
        
        db_ml_model = MLModel(**db_model.dict())
        db_ml_model.accuracy = r2
        db_ml_model.precision = 1 - mae / y.mean() if y.mean() != 0 else 0
        db_ml_model.recall = 1 - np.sqrt(mse) / y.mean() if y.mean() != 0 else 0
        db_ml_model.f1_score = 2 * (db_ml_model.precision * db_ml_model.recall) / (db_ml_model.precision + db_ml_model.recall) if (db_ml_model.precision + db_ml_model.recall) > 0 else 0
        db_ml_model.created_at = datetime.now()
        
        self.db.add(db_ml_model)
        self.db.commit()
        self.db.refresh(db_ml_model)
        
        return db_ml_model
    
    def predict(self, model_id: int, stock_code: str) -> Dict[str, Any]:
        db_model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not db_model:
            raise ValueError("模型不存在")
        
        if not os.path.exists(db_model.model_path):
            raise ValueError("模型文件不存在")
        
        model = joblib.load(db_model.model_path)
        
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
        change_percent = ((prediction - current_price) / current_price) * 100
        
        return {
            'model_id': model_id,
            'stock_code': stock_code,
            'current_price': float(current_price),
            'predicted_price': float(prediction),
            'change_percent': float(change_percent),
            'prediction_date': datetime.now().isoformat()
        }
    
    def get_models(self, stock_code: Optional[str] = None) -> List[MLModel]:
        query = self.db.query(MLModel)
        if stock_code:
            query = query.filter(MLModel.stock_code == stock_code)
        return query.order_by(MLModel.created_at.desc()).all()
    
    def get_model(self, model_id: int) -> Optional[MLModel]:
        return self.db.query(MLModel).filter(MLModel.id == model_id).first()
    
    def delete_model(self, model_id: int) -> bool:
        db_model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if db_model:
            if db_model.model_path and os.path.exists(db_model.model_path):
                os.remove(db_model.model_path)
            self.db.delete(db_model)
            self.db.commit()
            return True
        return False
