from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any


class MLModelBase(BaseModel):
    model_name: str
    stock_code: str
    model_type: str
    feature_columns: Optional[List[str]] = None
    target_column: Optional[str] = None
    model_path: Optional[str] = None
    description: Optional[str] = None


class MLModelCreate(MLModelBase):
    pass


class MLModel(MLModelBase):
    id: int
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    created_at: Optional[datetime] = None
    is_active: int = 0
    
    class Config:
        from_attributes = True


class TrainingRequest(BaseModel):
    stock_code: str
    model_name: str
    model_type: str = "RandomForest"
    feature_columns: Optional[List[str]] = None
    target_column: str = "close_price"
    train_size: float = 0.8
    is_classification: bool = False  # 新增：是否是分类模型


class PredictionRequest(BaseModel):
    model_id: int
    stock_code: str
    data: Optional[List[Dict[str, Any]]] = None


class PredictionResponse(BaseModel):
    prediction: float
    confidence: Optional[float] = None


class SignalPrediction(BaseModel):
    """多空信号预测响应"""
    model_id: int
    stock_code: str
    signal: str  # "BUY", "SELL", "HOLD"
    signal_strength: float  # 信号强度 0-100
    confidence: float  # 置信度 0-1
    current_price: float
    predicted_price: Optional[float] = None
    predicted_change_percent: Optional[float] = None
    prediction_date: datetime
    signal_explanation: str  # 信号解释
    technical_indicators: Optional[Dict[str, float]] = None  # 使用的技术指标值
