"""Disk-cache utility wrapping diskcache for repository-level memoization."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from diskcache import Cache

from backend.infrastructure.akshare_client import ak_call_with_retry

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "akshare"
_cache = Cache(str(_CACHE_DIR))

TTL_STOCK_INFO = 10 * 60        # 10 minutes
TTL_FINANCIAL = 24 * 60 * 60    # 1 day
TTL_PRICE = 24 * 60 * 60        # 1 day


def cache_get(key: str) -> Any | None:
    return _cache.get(key)


def cache_set(key: str, value: Any, ttl: int) -> None:
    _cache.set(key, value, expire=ttl)


def cached_call(cache_key: str, ttl: int, func: Callable, *args, **kwargs):
    """Try disk cache first; on miss, call ``func`` via the retry wrapper and store."""
    result = _cache.get(cache_key)
    if result is not None:
        logger.debug("Cache HIT: %s", cache_key)
        return result
    logger.debug("Cache MISS: %s", cache_key)
    result = ak_call_with_retry(func, *args, **kwargs)
    _cache.set(cache_key, result, expire=ttl)
    return result


def clear_all_caches() -> None:
    """Clear all disk-cached data."""
    _cache.clear()
    logger.info("All AKShare caches cleared.")
