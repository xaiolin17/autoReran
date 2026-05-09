from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import api_router

# 创建数据库表（生产环境应使用 Alembic 迁移）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 注册 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 配置静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def index(request: Request):
    """数据查看页面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/training")
async def training(request: Request):
    """模型训练页面"""
    return templates.TemplateResponse("training.html", {"request": request})


@app.get("/backtest")
async def backtest(request: Request):
    """策略回测页面"""
    return templates.TemplateResponse("backtest.html", {"request": request})


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "股票数据分析平台运行正常"}
