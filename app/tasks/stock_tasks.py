from datetime import datetime

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.logger import logger
from app.models.task_status import TaskStatus
from app.schemas.backtest import BacktestRequest
from app.schemas.ml import TrainingRequest
from app.services.backtest_service import BacktestService
from app.services.ml_service import MLService
from app.services.stock_service import StockService


def update_task_status(
    task_id, task_type, status, progress=0, result=None, error_message=None
):
    db = SessionLocal()
    try:
        task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
        if task:
            task.status = status
            task.progress = progress
            task.result = result
            task.error_message = error_message
            task.updated_at = datetime.now()
        else:
            task = TaskStatus(
                task_id=task_id,
                task_type=task_type,
                status=status,
                progress=progress,
                result=result,
                error_message=error_message,
            )
            db.add(task)
        db.commit()
        db.refresh(task)
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def fetch_stock_data_task(
    self,
    stock_code: str,
    period: str = "1d",
    start_date: str = None,
    end_date: str = None,
):
    task_id = self.request.id
    task_type = "fetch_stock_data"
    logger.info(f"开始获取股票 {stock_code} 数据，任务ID: {task_id}")

    update_task_status(task_id, task_type, "processing", 10)

    try:
        db = SessionLocal()
        stock_service = StockService(db)

        update_task_status(task_id, task_type, "processing", 30)

        saved_stocks = stock_service.fetch_and_save_stock_data(
            stock_code, period, start_date, end_date
        )

        update_task_status(task_id, task_type, "processing", 80)

        result = {
            "status": "success",
            "stock_code": stock_code,
            "period": period,
            "count": len(saved_stocks),
            "message": f"成功获取并保存 {len(saved_stocks)} 条股票数据",
        }

        update_task_status(task_id, task_type, "completed", 100, result)
        db.close()
        logger.info(f"股票 {stock_code} 数据获取完成")
        return result

    except Exception as e:
        error_msg = f"获取股票 {stock_code} 数据失败: {str(e)}"
        logger.error(error_msg)
        update_task_status(task_id, task_type, "failed", 0, None, error_msg)
        self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(bind=True)
def train_model_task(
    self,
    stock_code: str,
    model_name: str,
    model_type: str = "RandomForest",
    feature_columns: list = None,
    target_column: str = "close_price",
    train_size: float = 0.8,
):
    task_id = self.request.id
    task_type = "train_model"
    logger.info(f"开始训练模型 {model_name}，任务ID: {task_id}")

    update_task_status(task_id, task_type, "processing", 10)

    try:
        db = SessionLocal()
        ml_service = MLService(db)

        update_task_status(task_id, task_type, "processing", 30)

        request = TrainingRequest(
            stock_code=stock_code,
            model_name=model_name,
            model_type=model_type,
            feature_columns=feature_columns,
            target_column=target_column,
            train_size=train_size,
        )

        model = ml_service.train_model(request)

        update_task_status(task_id, task_type, "processing", 80)

        result = {
            "status": "success",
            "model_id": model.id,
            "model_name": model_name,
            "stock_code": stock_code,
            "accuracy": model.accuracy,
            "precision": model.precision,
            "recall": model.recall,
            "f1_score": model.f1_score,
            "message": "模型训练完成",
        }

        update_task_status(task_id, task_type, "completed", 100, result)
        db.close()
        logger.info(f"模型 {model_name} 训练完成")
        return result

    except Exception as e:
        error_msg = f"模型 {model_name} 训练失败: {str(e)}"
        logger.error(error_msg)
        update_task_status(task_id, task_type, "failed", 0, None, error_msg)
        return {"status": "error", "model_name": model_name, "message": str(e)}


@celery_app.task(bind=True)
def run_backtest_task(
    self,
    stock_code: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    params: dict = None,
):
    task_id = self.request.id
    task_type = "run_backtest"
    logger.info(
        f"开始运行回测，股票: {stock_code}，策略: {strategy_name}，任务ID: {task_id}"
    )

    update_task_status(task_id, task_type, "processing", 10)

    try:
        db = SessionLocal()
        backtest_service = BacktestService(db)

        update_task_status(task_id, task_type, "processing", 30)

        request = BacktestRequest(
            stock_code=stock_code,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            params=params or {},
        )

        backtest_result = backtest_service.run_backtest(request)

        update_task_status(task_id, task_type, "processing", 80)

        result = {
            "status": "success",
            "backtest_id": backtest_result.id,
            "stock_code": stock_code,
            "strategy_name": strategy_name,
            "total_return": backtest_result.total_return,
            "annual_return": backtest_result.annual_return,
            "max_drawdown": backtest_result.max_drawdown,
            "win_rate": backtest_result.win_rate,
            "total_trades": backtest_result.total_trades,
            "message": "回测完成",
        }

        update_task_status(task_id, task_type, "completed", 100, result)
        db.close()
        logger.info(f"回测 {backtest_result.id} 运行完成")
        return result

    except Exception as e:
        error_msg = f"回测运行失败: {str(e)}"
        logger.error(error_msg)
        update_task_status(task_id, task_type, "failed", 0, None, error_msg)
        return {
            "status": "error",
            "stock_code": stock_code,
            "strategy_name": strategy_name,
            "message": str(e),
        }


@celery_app.task
def get_task_status(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
        if task:
            return {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "result": task.result,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        return None
    finally:
        db.close()
