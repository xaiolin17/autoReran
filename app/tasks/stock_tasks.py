import time
from app.core.celery_app import celery_app
from app.core.logger import logger


@celery_app.task(bind=True, max_retries=3)
def fetch_stock_data_task(self, stock_code: str):
    """
    异步获取股票数据的任务
    """
    try:
        logger.info(f"开始获取股票 {stock_code} 的数据...")
        time.sleep(2)  # 模拟耗时操作
        logger.info(f"股票 {stock_code} 数据获取完成")
        return {"status": "success", "stock_code": stock_code, "message": "数据获取成功"}
    except Exception as e:
        logger.error(f"获取股票 {stock_code} 数据失败: {str(e)}")
        self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task
def train_model_task(model_id: int, epochs: int = 100):
    """
    异步训练模型的任务
    """
    try:
        logger.info(f"开始训练模型 {model_id}，共 {epochs} 轮...")
        for i in range(epochs):
            if i % 10 == 0:
                logger.info(f"模型 {model_id} 训练进度: {i}/{epochs}")
            time.sleep(0.1)
        logger.info(f"模型 {model_id} 训练完成")
        return {"status": "success", "model_id": model_id, "message": "训练完成"}
    except Exception as e:
        logger.error(f"模型 {model_id} 训练失败: {str(e)}")
        return {"status": "error", "model_id": model_id, "message": str(e)}


@celery_app.task
def run_backtest_task(backtest_id: int):
    """
    异步运行回测的任务
    """
    try:
        logger.info(f"开始运行回测 {backtest_id}...")
        time.sleep(5)  # 模拟耗时操作
        logger.info(f"回测 {backtest_id} 运行完成")
        return {"status": "success", "backtest_id": backtest_id, "message": "回测完成"}
    except Exception as e:
        logger.error(f"回测 {backtest_id} 运行失败: {str(e)}")
        return {"status": "error", "backtest_id": backtest_id, "message": str(e)}
