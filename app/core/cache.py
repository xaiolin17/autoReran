import time
import hashlib
import pickle
from collections import OrderedDict
from typing import Any, Callable, Optional, Union, Dict, List
from functools import wraps
from app.core.logger import logger


class CacheEntry:
    def __init__(self, value: Any, ttl: Optional[float] = None):
        self.value = value
        self.ttl = ttl
        self.created_at = time.time()
    
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class LRUCache:
    def __init__(self, maxsize: int = 128, default_ttl: Optional[float] = None):
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
    
    def _evict_expired(self) -> None:
        keys_to_remove = [k for k, v in self.cache.items() if v.is_expired()]
        for key in keys_to_remove:
            del self.cache[key]
    
    def _evict_if_needed(self) -> None:
        self._evict_expired()
        while len(self.cache) >= self.maxsize:
            self.cache.popitem(last=False)
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        if entry.is_expired():
            self.cache.pop(key)
            self.misses += 1
            return None
        
        self.cache.move_to_end(key)
        self.hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        self._evict_if_needed()
        self.cache[key] = CacheEntry(value, ttl or self.default_ttl)
    
    def delete(self, key: str) -> bool:
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def delete_pattern(self, pattern: str) -> int:
        count = 0
        keys_to_remove = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_remove:
            del self.cache[key]
            count += 1
        return count
    
    def clear(self) -> None:
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        self._evict_expired()
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            'size': len(self.cache),
            'maxsize': self.maxsize,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }


_cache_instance: Optional[LRUCache] = None


def get_cache() -> LRUCache:
    global _cache_instance
    if _cache_instance is None:
        from app.core.config import settings
        _cache_instance = LRUCache(
            maxsize=settings.CACHE_MAXSIZE,
            default_ttl=settings.CACHE_DEFAULT_TTL
        )
    return _cache_instance


def make_cache_key(*args, **kwargs) -> str:
    key_parts = []
    for arg in args:
        key_parts.append(str(arg))
    sorted_kwargs = sorted(kwargs.items())
    for k, v in sorted_kwargs:
        key_parts.append(f"{k}:{v}")
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def lru_cache(
    ttl: Optional[float] = None,
    key_prefix: str = "",
    exclude_args: Optional[List[str]] = None
) -> Callable:
    exclude_args = exclude_args or []
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            filtered_kwargs = {k: v for k, v in kwargs.items() if k not in exclude_args}
            
            key = f"{key_prefix}:{func.__name__}:{make_cache_key(*args, **filtered_kwargs)}"
            
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"缓存命中: {func.__name__}")
                return cached_result
            
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            logger.debug(f"缓存写入: {func.__name__}")
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str) -> int:
    cache = get_cache()
    count = cache.delete_pattern(pattern)
    logger.debug(f"清除缓存: {pattern}, 数量: {count}")
    return count


def invalidate_all_cache() -> None:
    cache = get_cache()
    cache.clear()
    logger.info("清除所有缓存")


def get_cache_stats() -> Dict[str, Any]:
    cache = get_cache()
    return cache.get_stats()
