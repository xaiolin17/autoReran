import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AReran"
    DEBUG: bool = True
    
    # 使用绝对路径的 SQLite 数据库
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'stock_data.db'}"
    
    SCHEDULER_ENABLED: bool = True
    CRAWL_INTERVAL_MINUTES: int = 60
    
    # 使用绝对路径
    MODELS_DIR: str = str(BASE_DIR / "models")
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    CORS_ORIGINS: list[str] = ["http://localhost", "http://localhost:8000"]
    
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # 使用绝对路径
    BACKUP_DIR: str = str(BASE_DIR / "backups")
    BACKUP_RETENTION_DAYS: int = 30
    
    # 爬虫配置（提供默认值）
    SINA_STOCK_URL: str = "http://hq.sinajs.cn/list="
    EASTMONEY_URL: str = "http://push2.eastmoney.com/api/qt/stock/kline/get"

    class Config:
        env_file = ".env"


settings = Settings()

# 确保必要的目录存在
os.makedirs(settings.MODELS_DIR, exist_ok=True)
os.makedirs(settings.BACKUP_DIR, exist_ok=True)
