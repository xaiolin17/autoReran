import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.logger import logger
from app.core.websocket_manager import manager as ws_manager
from app.services.initialization_service import InitializationService

# 获取项目根目录的绝对路径
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# 确保目录存在
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup 事件
    logger.info("应用启动 - 开始初始化")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"创建表结构时出错: {e}")
        logger.info("提示: 如果已存在旧数据库，可能需要删除 stock_data.db")

    # 初始化默认数据 (容错处理)
    try:
        db = SessionLocal()
        try:
            init_service = InitializationService(db)
            init_service.check_and_initialize_default_data()
        except Exception as e:
            logger.error(f"初始化数据时出错: {e}", exc_info=True)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"初始化服务异常: {e}", exc_info=True)

    yield
    # Shutdown 事件
    logger.info("AReran 正在关闭...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# 注册 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 配置静态文件
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR), html=True),
    name="static",
)


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(CacheControlMiddleware)


@app.get("/test")
async def test():
    """测试页面"""
    return {"message": "AReran is working!", "status": "ok"}


def read_template(filename):
    """读取模板文件内容"""
    try:
        with open(TEMPLATES_DIR / filename, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"


@app.get("/", response_class=HTMLResponse)
async def index():
    """数据查看页面"""
    return HTMLResponse(content=read_template("index.html"))


@app.get("/training", response_class=HTMLResponse)
async def training():
    """模型训练页面"""
    return HTMLResponse(content=read_template("training.html"))


@app.get("/backtest", response_class=HTMLResponse)
async def backtest():
    """策略回测页面"""
    return HTMLResponse(content=read_template("backtest.html"))


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "AReran 运行正常"}


# ===== WebSocket 实时通知端点 =====
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, channel="realtime")

    try:
        while True:
            data = await websocket.receive_json()

            # 处理客户端消息
            if data.get("type") == "ping":
                await ws_manager.send_personal_message({"type": "pong", "timestamp": data.get("timestamp")}, websocket)
            elif data.get("type") == "subscribe":
                channel = data.get("channel", "realtime")
                await ws_manager.send_personal_message({"type": "subscribed", "channel": channel}, websocket)
            elif data.get("type") == "refresh":
                # 广播数据刷新通知
                await ws_manager.broadcast(
                    {
                        "type": "refresh_needed",
                        "reason": "manual_refresh",
                        "sender": client_id,
                    },
                    channel="realtime",
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="realtime")
    except Exception:
        ws_manager.disconnect(websocket, channel="realtime")
