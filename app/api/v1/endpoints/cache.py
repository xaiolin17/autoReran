from fastapi import APIRouter

from app.core.cache import (get_cache_stats, invalidate_all_cache,
                            invalidate_cache)
from app.core.logger import logger

router = APIRouter()


@router.get("/stats")
def cache_stats():
    """获取缓存统计信息"""
    stats = get_cache_stats()
    logger.info(f"获取缓存统计: {stats}")
    return {"success": True, "data": stats}


@router.post("/clear")
def clear_all_cache():
    """清除所有缓存"""
    invalidate_all_cache()
    return {"success": True, "message": "所有缓存已清除"}


@router.post("/clear/{pattern}")
def clear_cache_by_pattern(pattern: str):
    """按模式清除缓存"""
    count = invalidate_cache(pattern)
    return {"success": True, "message": f"清除了 {count} 条缓存", "count": count}
