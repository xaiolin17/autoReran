from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.core.database import engine, Base
from app.core.logger import logger
from app.core.monitoring import metrics_middleware, get_metrics
from app.core.serialization import ORJSONResponse
from app.core.security_middleware import setup_security_middleware
from app.core.websocket_manager import manager as ws_manager
from app.api.v1 import api_router


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
