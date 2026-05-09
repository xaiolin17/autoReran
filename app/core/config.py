from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "股票数据分析平台"
    DEBUG: bool = True
    
    DATABASE_URL: str = "sqlite:///./stock_data.db"
    
    SINA_STOCK_URL: str = "https://hq.sinajs.cn/list="
    EASTMONEY_URL: str = "https://push2.eastmoney.com/api/qt/stock/kline/get"
    EASTMONEY_OPTION_CHAIN_URL: str = "https://push2.eastmoney.com/api/qt/official/stock/ls"
    EASTMONEY_OPTION_QUOTE_URL: str = "https://push2.eastmoney.com/api/qt/stock/details/get"
    
    MODELS_DIR: str = "models"
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str | None = None
    
    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
