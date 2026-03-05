"""
src/utils/resilience.py
─────────────────────────────────────────────────────────────────────────────
Wrappers for external API calls with timeout, retry and fallback logic.
"""

import time
import logging
from functools import wraps
from typing import TypeVar, Callable, Any

logger = logging.getLogger("365advisers.resilience")

T = TypeVar("T")


def with_retry(
    max_retries: int = 2,
    delay: float = 1.0,
    timeout: int = 15,
    fallback: Any = None,
    label: str = "external_call",
) -> Callable:
    """
    Decorator that adds timeout, exponential backoff retry, and fallback
    to any synchronous function (e.g. yfinance calls).
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import concurrent.futures

            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(func, *args, **kwargs)
                        result = future.result(timeout=timeout)
                        return result
                except concurrent.futures.TimeoutError:
                    last_exc = TimeoutError(f"{label} timed out after {timeout}s (attempt {attempt}/{max_retries})")
                    logger.warning(str(last_exc))
                except Exception as exc:
                    last_exc = exc
                    logger.warning(f"{label} failed (attempt {attempt}/{max_retries}): {exc}")

                if attempt < max_retries:
                    sleep_time = delay * (2 ** (attempt - 1))
                    logger.info(f"{label}: retrying in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)

            logger.error(f"{label}: all {max_retries} attempts exhausted. Last error: {last_exc}")
            if fallback is not None:
                logger.info(f"{label}: returning fallback value")
                return fallback
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
