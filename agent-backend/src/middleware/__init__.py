"""
src/middleware/rate_limit.py
─────────────────────────────────────────────────────────────────────────────
Simple in-memory rate limiter middleware for FastAPI.
Fixes audit finding #15 — prevents API abuse.
"""

import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("365advisers.ratelimit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token-bucket rate limiter per client IP.
    Default: 30 requests per 60-second window.
    Excludes /health and /docs from rate limiting.
    """

    EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health/docs
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune old entries
        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [ts for ts in bucket if ts > cutoff]

        if len(self._buckets[client_ip]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s."
            )

        self._buckets[client_ip].append(now)
        return await call_next(request)
