from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from app.core.database import Base


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)  # random_forest, linear_regression, etc.
    stock_code = Column(String(20), index=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime)
    model_path = Column(String(500))
    scaler_path = Column(String(500))
    features = Column(JSON)  # 用于训练的特征列表
    target = Column(String(50))  # 预测目标
    params = Column(JSON)  # 模型参数
    metrics = Column(JSON)  # 评估指标
    description = Column(Text)
    is_active = Column(Integer, default=1)

    def __repr__(self):
        return f"<MLModel {self.model_name} {self.stock_code}>"
