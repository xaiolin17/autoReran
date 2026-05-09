from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "股票数据分析平台"
    DEBUG: bool = True
    
    DATABASE_URL: str = "sqlite:///./stock_data.db"
    
    SINA_STOCK_URL: str = "https://hq.sinajs.cn/list="
    EASTMONEY_URL: str = "https://push2.eastmoney.com/api/qt/stock/kline/get"
    
    SCHEDULER_ENABLED: bool = True
    CRAWL_INTERVAL_MINUTES: int = 5
    
    MODELS_DIR: str = "models"
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    CACHE_ENABLED: bool = True
    CACHE_MAXSIZE: int = 1024
    CACHE_DEFAULT_TTL: int = 300
    CACHE_STOCK_DATA_TTL: int = 300
    CACHE_INDICATOR_TTL: int = 600
    
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
