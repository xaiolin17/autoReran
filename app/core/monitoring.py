from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time
from app.core.logger import logger

# 请求计数
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# 请求耗时
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# 活跃请求数
ACTIVE_REQUESTS = Gauge(
    'http_active_requests',
    'Number of active HTTP requests',
    ['method', 'endpoint']
)

# 股票数据获取次数
STOCK_DATA_FETCHES = Counter(
    'stock_data_fetches_total',
    'Total number of stock data fetches',
    ['stock_code', 'source']
)

# 模型训练次数
MODEL_TRAINS = Counter(
    'model_trains_total',
    'Total number of model trainings',
    ['model_type', 'stock_code']
)

# 回测执行次数
BACKTEST_RUNS = Counter(
    'backtest_runs_total',
    'Total number of backtest runs',
    ['strategy_name', 'stock_code']
)

# Celery 任务状态
CELERY_TASKS = Counter(
    'celery_tasks_total',
    'Total number of Celery tasks',
    ['task_type', 'status']
)

# 数据库连接数
DB_CONNECTIONS = Gauge(
    'db_connections',
    'Number of database connections'
)


async def metrics_middleware(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    
    # 跳过 metrics 端点自身的记录
    if endpoint == '/metrics':
        return await call_next(request)
    
    ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).inc()
    start_time = time.time()
    
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        
        # 记录请求计数
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        # 记录请求耗时
        duration = time.time() - start_time
        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        return response
    finally:
        ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).dec()


def get_metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def record_stock_data_fetch(stock_code: str, source: str):
    STOCK_DATA_FETCHES.labels(stock_code=stock_code, source=source).inc()
    logger.debug(f"记录股票数据获取: {stock_code} from {source}")


def record_model_train(model_type: str, stock_code: str):
    MODEL_TRAINS.labels(model_type=model_type, stock_code=stock_code).inc()
    logger.debug(f"记录模型训练: {model_type} for {stock_code}")


def record_backtest_run(strategy_name: str, stock_code: str):
    BACKTEST_RUNS.labels(strategy_name=strategy_name, stock_code=stock_code).inc()
    logger.debug(f"记录回测运行: {strategy_name} for {stock_code}")


def record_celery_task(task_type: str, status: str):
    CELERY_TASKS.labels(task_type=task_type, status=status).inc()
    logger.debug(f"记录 Celery 任务: {task_type} - {status}")
