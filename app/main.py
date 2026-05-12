from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.logger import logger
from app.core.monitoring import metrics_middleware, get_metrics
from app.core.serialization import ORJSONResponse
from app.core.security_middleware import setup_security_middleware
from app.core.websocket_manager import manager as ws_manager
from app.api.v1 import api_router
from app.models.stock_data import StockData
from app.services.stock_service import StockService


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG,
    default_response_class=ORJSONResponse
)

app.middleware("http")(metrics_middleware)
limiter = setup_security_middleware(app)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail
        }
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"数据库异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "数据库操作失败",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


app.include_router(api_router, prefix=settings.API_V1_STR)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/training")
async def training(request: Request):
    return templates.TemplateResponse("training.html", {"request": request})


@app.get("/backtest")
async def backtest(request: Request):
    return templates.TemplateResponse("backtest.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"success": True, "message": "股票数据分析平台运行正常"}


@app.get("/metrics")
async def metrics():
    return get_metrics()


@app.on_event("startup")
async def startup_event():
    logger.info(f"{settings.PROJECT_NAME} 启动成功")
    
    # 初始化默认数据
    try:
        await init_default_data()
    except Exception as e:
        logger.error(f"初始化数据失败: {e}")


async def init_default_data():
    """初始化默认股票数据"""
    db = SessionLocal()
    try:
        # 检查是否已有上证指数数据
        stmt = select(StockData).where(
            StockData.stock_code == "000001",
            StockData.period == "1d"
        ).limit(1)
        result = db.execute(stmt)
        exists = result.scalar_one_or_none() is not None
        
        if not exists:
            logger.info("正在初始化默认数据...")
            stock_service = StockService(db)
            
            # 上证指数
            for period in ["1d", "1h", "1w", "1M"]:
                saved = stock_service.fetch_and_save_stock_data("000001", period)
                if saved:
                    logger.info(f"✅ 上证指数 {period} 数据初始化完成: {len(saved)} 条")
            
            # 深证成指
            saved_sz = stock_service.fetch_and_save_stock_data("399001", "1d")
            if saved_sz:
                logger.info(f"✅ 深证成指 1d 数据初始化完成: {len(saved_sz)} 条")
            
            logger.info("✅ 默认数据初始化完成")
        else:
            logger.info("✅ 默认数据已存在")
    except Exception as e:
        logger.error(f"初始化数据失败: {e}")
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"{settings.PROJECT_NAME} 关闭")


# ===== WebSocket 实时通知端点 =====
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, channel="realtime")
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # 处理客户端消息
            if data.get("type") == "ping":
                await ws_manager.send_personal_message(
                    {"type": "pong", "timestamp": data.get("timestamp")},
                    websocket
                )
            elif data.get("type") == "subscribe":
                channel = data.get("channel", "realtime")
                await ws_manager.send_personal_message(
                    {"type": "subscribed", "channel": channel},
                    websocket
                )
            elif data.get("type") == "refresh":
                # 广播数据刷新通知
                await ws_manager.broadcast(
                    {"type": "refresh_needed", "reason": "manual_refresh", "sender": client_id},
                    channel="realtime"
                )
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="realtime")
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}")
        ws_manager.disconnect(websocket, channel="realtime")
