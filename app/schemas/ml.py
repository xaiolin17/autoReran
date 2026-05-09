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


class PredictionRequest(BaseModel):
    model_id: int
    stock_code: str
    data: Optional[List[Dict[str, Any]]] = None


class PredictionResponse(BaseModel):
    prediction: float
    confidence: Optional[float] = None
