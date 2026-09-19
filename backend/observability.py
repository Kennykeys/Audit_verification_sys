from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware

SENSITIVE_FIELD_PATTERN = re.compile(
    r"password|token|authorization|secret|phone_number|member_id|description",
    re.IGNORECASE,
)


def redact_value(name, value):
    if SENSITIVE_FIELD_PATTERN.search(str(name)):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {key: redact_value(key, item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(name, item) for item in value]
    return value


def configure_structured_logging(level="INFO"):
    logger = logging.getLogger("audit_verification")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.propagate = False
    return logger


class StructuredEventLogger:
    def __init__(self, logger=None, clock=None):
        self.logger = logger or configure_structured_logging()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def emit(self, event, request_id=None, severity="INFO", **fields):
        payload = {
            "timestamp": self.clock().isoformat(),
            "severity": severity.upper(),
            "event": event,
            "request_id": request_id,
        }
        payload.update(
            {key: redact_value(key, value) for key, value in fields.items()}
        )
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return payload


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, event_logger=None):
        super().__init__(app)
        self.event_logger = event_logger or StructuredEventLogger()

    async def dispatch(self, request, call_next):
        started = time.monotonic()
        request_id = getattr(request.state, "request_id", None)
        response = await call_next(request)
        request_id = getattr(request.state, "request_id", None) or request_id
        event = self._event_name(request.method, request.url.path, response.status_code)
        severity = "WARNING" if response.status_code >= 400 else "INFO"
        self.event_logger.emit(
            event,
            request_id=request_id,
            severity=severity,
            method=request.method,
            route=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return response

    @staticmethod
    def _event_name(method, route, status_code):
        if status_code == 401:
            return "authentication_failed"
        if status_code == 403:
            return "access_denied"
        if method == "POST" and route in {"/record", "/record_mobile"}:
            return "recording_succeeded" if status_code < 400 else "recording_failed"
        return "http_request_completed"
