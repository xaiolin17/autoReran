from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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
    train_size: Optional[float] = 0.8
    used_marked_data: Optional[bool] = False
    num_marks_used: Optional[int] = 0
    created_at: Optional[datetime] = None
    is_active: int = 0

    class Config:
        from_attributes = True


class TradeMarkSchema(BaseModel):
    index: int
    date: Optional[str] = None
    price: float
    type: str  # 'buy' or 'sell'
    timestamp: Optional[int] = None


class TrainingRequest(BaseModel):
    stock_code: str
    model_name: str
    model_type: str = "RandomForest"
    feature_columns: Optional[List[str]] = None
    target_column: str = "close_price"
    train_size: float = 0.8
    trade_marks: Optional[List[TradeMarkSchema]] = None


class PredictionRequest(BaseModel):
    model_id: int
    stock_code: str
    data: Optional[List[Dict[str, Any]]] = None


class PredictionResponse(BaseModel):
    prediction: float
    confidence: Optional[float] = None
    current_price: Optional[float] = None
