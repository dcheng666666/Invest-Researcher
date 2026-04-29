"""Thin retry wrapper for AKShare calls."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def ak_call_with_retry(func, *args, **kwargs):
    """Call an AKShare function with retry on connection errors."""
    max_retries = 3
    delay = 2.0
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            is_conn_err = (
                "connection" in err_str
                or "remote" in err_str
                or "timeout" in err_str
            )
            if attempt < max_retries and is_conn_err:
                wait = delay * (attempt + 1)
                logger.warning(
                    "Retry %d/%d for %s (wait %.1fs): %s",
                    attempt + 1,
                    max_retries,
                    func.__name__,
                    wait,
                    e,
                )
                time.sleep(wait)
            else:
                raise
