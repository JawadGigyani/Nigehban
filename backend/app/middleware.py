"""Rate limits and security headers.

Public endpoints call free LLM, voice and weather quotas, so each client IP gets a small
per-minute allowance (sliding window, in memory), and the chat has a global daily cap.
Behind a reverse proxy the client IP comes from X-Forwarded-For.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# path prefix -> (requests per minute per IP); None = default
LIMITS = {"/chat": "chat", "/tts": 4, "/advisories/draft": 6, "/subscriptions": 10, "/me/delete": 5,
          "/route/shelter": 20, "/geo/check": 30, "/board/login": 5}
EXEMPT = ("/health", "/audio/", "/geo/tehsils", "/config", "/docs", "/openapi.json")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, chat_per_min: int = 8, default_per_min: int = 60, chat_per_day: int = 1500) -> None:
        super().__init__(app)
        self.chat_per_min, self.default_per_min, self.chat_per_day = chat_per_min, default_per_min, chat_per_day
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self.chat_day: deque = deque()

    @staticmethod
    def client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path.startswith(EXEMPT) or path.startswith("/internal/"):
            return await call_next(request)
        group, limit = "default", self.default_per_min
        for prefix, value in LIMITS.items():
            if path.startswith(prefix):
                group = prefix
                limit = self.chat_per_min if value == "chat" else value
                break
        now = time.time()
        window = self.hits[(self.client_ip(request), group)]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return JSONResponse({"detail": "Too many requests. Please wait a minute."}, status_code=429,
                                headers={"Retry-After": "60"})
        if group == "/chat":
            while self.chat_day and now - self.chat_day[0] > 86400:
                self.chat_day.popleft()
            if len(self.chat_day) >= self.chat_per_day:
                return JSONResponse({"detail": "The assistant has reached today's limit. Please try tomorrow."},
                                    status_code=429)
            self.chat_day.append(now)
        window.append(now)
        if len(self.hits) > 50_000:  # forget idle clients
            for key in [k for k, v in self.hits.items() if not v or now - v[-1] > 120]:
                del self.hits[key]
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store") if request.url.path.startswith(
            ("/risk", "/alerts", "/inbox", "/board")) else None
        return response
