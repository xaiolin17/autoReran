from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.ml import MLModel, TrainingRequest
from app.services.ml_service import MLService

router = APIRouter()


@router.post("/train", response_model=MLModel)
def train_model(request: TrainingRequest, db: Session = Depends(get_db)):
    service = MLService(db)
    try:
        return service.train_model(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/predict")
def predict(
    model_id: int,
    stock_code: str,
    db: Session = Depends(get_db)
):
    service = MLService(db)
    try:
        return service.predict(model_id, stock_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/predict/{stock_code}")
def predict_latest(
    stock_code: str,
    db: Session = Depends(get_db)
):
    """获取最新模型对指定股票的预测"""
    from datetime import datetime
    try:
        # 简单的模拟预测，实际项目中应该使用训练好的模型
        return {
            "signal": "hold",  # buy, sell, hold
            "date": datetime.now().strftime("%Y-%m-%d"),
            "confidence": 0.65,
            "target_price": None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/models", response_model=List[MLModel])
def get_models(
    stock_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = MLService(db)
    return service.get_models(stock_code)


@router.get("/models/{model_id}", response_model=Optional[MLModel])
def get_model(
    model_id: int,
    db: Session = Depends(get_db)
):
    service = MLService(db)
    model = service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/models/{model_id}")
def delete_model(
    model_id: int,
    db: Session = Depends(get_db)
):
    service = MLService(db)
    success = service.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"message": "Model deleted successfully"}
