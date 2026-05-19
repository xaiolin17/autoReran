from fastapi import APIRouter

from app.crawlers.scheduler import get_scheduler

router = APIRouter()


@router.get("/status")
def get_scheduler_status():
    scheduler = get_scheduler()
    return scheduler.get_status()


@router.post("/start")
def start_scheduler(interval_minutes: int = 5):
    scheduler = get_scheduler()
    scheduler.start(interval_minutes)
    return {"message": "Scheduler started"}


@router.post("/stop")
def stop_scheduler():
    scheduler = get_scheduler()
    scheduler.stop()
    return {"message": "Scheduler stopped"}


@router.post("/add/{stock_code}")
def add_stock_to_scheduler(stock_code: str):
    scheduler = get_scheduler()
    scheduler.add_stock(stock_code)
    return {"message": f"Added {stock_code} to scheduler"}


@router.delete("/remove/{stock_code}")
def remove_stock_from_scheduler(stock_code: str):
    scheduler = get_scheduler()
    scheduler.remove_stock(stock_code)
    return {"message": f"Removed {stock_code} from scheduler"}
