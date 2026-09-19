from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import re
import threading
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}

@dataclass(frozen=True)
class RatePolicy:
    requests: int
    window_seconds: int

class SlidingWindowRateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = threading.RLock()

    def allow(self, key, policy, now=None):
        current = time.monotonic() if now is None else now
        cutoff = current - policy.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= policy.requests:
                retry_after = max(1, int(policy.window_seconds - (current - events[0])))
                return False, retry_after
            events.append(current)
            return True, 0

class SecurityBoundaryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings, limiter=None):
        super().__init__(app)
        self.settings = settings
        self.limiter = limiter or SlidingWindowRateLimiter()
        self.login_policy = RatePolicy(settings.login_rate_limit, settings.rate_limit_window_seconds)
        self.mutation_policy = RatePolicy(settings.mutation_rate_limit, settings.rate_limit_window_seconds)

    async def dispatch(self, request: Request, call_next):
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else uuid.uuid4().hex
        request.state.request_id = request_id

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.settings.max_request_body_bytes:
                    return self._response(413, "request_too_large", "Request body exceeds the configured limit", request_id)
            except ValueError:
                return self._response(400, "invalid_content_length", "Invalid Content-Length header", request_id)

        policy = None
        if request.method == "POST" and request.url.path == "/auth/login":
            policy = self.login_policy
        elif request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path in {"/record", "/record_mobile"}:
            policy = self.mutation_policy
        if policy:
            client_host = request.client.host if request.client else "unknown"
            allowed, retry_after = self.limiter.allow(f"{client_host}:{request.url.path}", policy)
            if not allowed:
                response = self._response(429, "rate_limit_exceeded", "Request rate limit exceeded", request_id)
                response.headers["Retry-After"] = str(retry_after)
                return response

        response = await call_next(request)
        self._secure(response, request_id)
        return response

    @staticmethod
    def _secure(response, request_id):
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        response.headers["X-Request-ID"] = request_id

    @classmethod
    def _response(cls, status_code, code, message, request_id):
        response = JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "request_id": request_id}})
        cls._secure(response, request_id)
        return response
