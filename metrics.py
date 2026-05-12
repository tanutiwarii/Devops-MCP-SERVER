from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

log = logging.getLogger("devops_mcp.requests")

HTTP_REQUESTS = Counter(
    "devops_http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path_group", "status_class"),
)

HTTP_REQUEST_DURATION = Histogram(
    "devops_http_request_duration_seconds",
    "HTTP request latency",
    labelnames=("method", "path_group"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

HTTP_FAILURES = Counter(
    "devops_http_failures_total",
    "HTTP responses with 5xx status",
    labelnames=("method", "path_group"),
)


def normalize_path(path: str) -> str:
    if path.startswith("/jobs/") and path.rstrip("/") != "/jobs":
        return "/jobs/{job_id}"
    return path


def metrics_response() -> StarletteResponse:
    payload = generate_latest()
    return StarletteResponse(content=payload, media_type=CONTENT_TYPE_LATEST)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path_group = normalize_path(request.url.path)
        method = request.method
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = time.perf_counter() - start
            status = getattr(response, "status_code", 500) if response is not None else 500
            status_class = f"{status // 100}xx"
            HTTP_REQUESTS.labels(method, path_group, status_class).inc()
            HTTP_REQUEST_DURATION.labels(method, path_group).observe(elapsed)
            if status >= 500:
                HTTP_FAILURES.labels(method, path_group).inc()
            log.info(
                "%s %s -> %s %.3fs",
                method,
                request.url.path,
                status,
                elapsed,
            )
