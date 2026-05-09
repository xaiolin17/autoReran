from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.ml import MLModel, TrainingRequest, SignalPrediction
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


@router.post("/predict-signal", response_model=SignalPrediction)
def predict_signal(
    model_id: int,
    stock_code: str,
    db: Session = Depends(get_db)
):
    """
    专业多空信号预测接口
    
    返回 BUY/SELL/HOLD 信号，包括信号强度、置信度和详细解释
    """
    service = MLService(db)
    try:
        return service.predict_signal(model_id, stock_code)
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
