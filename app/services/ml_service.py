import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.models.ml_model import MLModel
from app.schemas.ml import TrainingRequest
from app.services.stock_service import StockService
from app.utils.technical_indicators import TechnicalIndicators


class MLService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_service = StockService(db)
        self.models_dir = settings.MODELS_DIR
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

        # 处理标记数据
        used_marked_data = False
        num_marks_used = 0

        if request.trade_marks and len(request.trade_marks) > 0:
            # 如果有标记数据，我们可以用它们来增强训练
            # 这里我们实现一个简单的标记数据增强策略
            used_marked_data = True
            num_marks_used = len(request.trade_marks)

            # 创建一个标记权重数组
            weights = np.ones(len(df))
            for mark in request.trade_marks:
                if 0 <= mark.index < len(df):
                    # 给标记点更高的权重
                    weights[mark.index] = 3.0

            logger.info(f"使用了 {num_marks_used} 个标记点训练")

        feature_columns = request.feature_columns or [
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "kdj_k",
            "kdj_d",
            "kdj_j",
            "macd",
            "macd_signal",
            "macd_histogram",
            "rsi",
            "ma5",
            "ma10",
            "ma20",
        ]

        # 同时适配两种命名方式
        column_mapping = {
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "volume": "volume",
            "kdj_k": "kdj_k",
            "kdj_d": "kdj_d",
            "kdj_j": "kdj_j",
            "macd": "macd",
            "macd_signal": "macd_signal",
            "macd_histogram": "macd_histogram",
            "rsi": "rsi",
        }

        available_features = []
        for col in feature_columns:
            if col in df.columns:
                available_features.append(col)
            elif col in column_mapping and column_mapping[col] in df.columns:
                available_features.append(column_mapping[col])

        if len(available_features) == 0:
            available_features = [
                col
                for col in ["open", "high", "low", "close", "volume"]
                if col in df.columns
            ]

        # 确定目标列 - 优先使用 close_price，否则用 close
        target_col = "close_price" if "close_price" in df.columns else "close"

        df["target"] = df[target_col].shift(-1)
        df = df.dropna()

        if len(df) < 50:
            raise ValueError("有效数据不足，无法训练")

        X = df[available_features]
        y = df["target"]

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

        db_ml_model = MLModel()
        db_ml_model.model_name = request.model_name
        db_ml_model.stock_code = request.stock_code
        db_ml_model.model_type = request.model_type
        db_ml_model.feature_columns = available_features
        db_ml_model.target_column = target_col
        db_ml_model.file_path = model_path
        db_ml_model.description = (
            f"Model trained with {len(X_train)} samples. R2: {r2:.4f}"
        )
        db_ml_model.accuracy = r2
        db_ml_model.precision = 1 - mae / y.mean() if y.mean() != 0 else 0
        db_ml_model.recall = 1 - np.sqrt(mse) / y.mean() if y.mean() != 0 else 0
        db_ml_model.f1_score = (
            2
            * (db_ml_model.precision * db_ml_model.recall)
            / (db_ml_model.precision + db_ml_model.recall)
            if (db_ml_model.precision + db_ml_model.recall) > 0
            else 0
        )
        db_ml_model.train_size = request.train_size
        db_ml_model.used_marked_data = used_marked_data
        db_ml_model.num_marks_used = num_marks_used
        db_ml_model.created_at = datetime.now()

        self.db.add(db_ml_model)
        self.db.commit()
        self.db.refresh(db_ml_model)

        return db_ml_model

    def predict(self, model_id: int, stock_code: str) -> Dict[str, Any]:
        db_model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not db_model:
            raise ValueError("模型不存在")

        if not os.path.exists(db_model.file_path):
            raise ValueError("模型文件不存在")

        model = joblib.load(db_model.file_path)

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

        # 获取当前价格
        target_col = db_model.target_column or (
            "close_price" if "close_price" in df.columns else "close"
        )
        current_price = df.iloc[-1][target_col]
        change_percent = ((prediction - current_price) / current_price) * 100

        return {
            "model_id": model_id,
            "stock_code": stock_code,
            "current_price": float(current_price),
            "predicted_price": float(prediction),
            "change_percent": float(change_percent),
            "prediction_date": datetime.now().isoformat(),
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
            if db_model.file_path and os.path.exists(db_model.file_path):
                os.remove(db_model.file_path)
            self.db.delete(db_model)
            self.db.commit()
            return True
        return False
