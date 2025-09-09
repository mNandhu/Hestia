"""
Logging Middleware for Hestia Gateway

FastAPI middleware for request/response logging with timing, status tracking,
and metrics collection integration.
"""

import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logging import EventType, clear_request_id, get_logger, get_request_id, set_request_id
from .metrics import MetricNames, get_metrics


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging and metrics."""

    def __init__(
        self,
        app: ASGIApp,
        logger_name: str = "hestia.middleware",
        exclude_paths: Optional[list] = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 1024 * 10,  # 10KB default
    ):
        """
        Initialize logging middleware.

        Args:
            app: ASGI application
            logger_name: Name for the logger instance
            exclude_paths: List of paths to exclude from logging
            log_request_body: Whether to log request bodies
            log_response_body: Whether to log response bodies
            max_body_size: Maximum body size to log (bytes)
        """
        super().__init__(app)
        self.logger = get_logger(logger_name)
        self.metrics = get_metrics()
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with logging and metrics."""
        # Skip logging for excluded paths
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        # Generate or extract request ID
        request_id = self._get_or_generate_request_id(request)
        set_request_id(request_id)

        # Initialize variables to avoid unbound errors
        start_time = time.time()
        method = request.method
        path = request.url.path
        service_id = self._extract_service_id(request)

        try:
            # Extract additional request info
            query_params = str(request.query_params) if request.query_params else None
            user_agent = request.headers.get("user-agent")
            client_ip = self._get_client_ip(request)

            # Log request body if enabled
            request_body = None
            if self.log_request_body and method in ["POST", "PUT", "PATCH"]:
                request_body = await self._get_request_body(request)

            # Log request start
            self.logger.log_request_start(
                method=method,
                path=path,
                service_id=service_id,
                metadata={
                    "request_id": request_id,
                    "query_params": query_params,
                    "user_agent": user_agent,
                    "client_ip": client_ip,
                    "request_body": request_body,
                },
            )

            # Increment request counter
            self.metrics.increment_counter(
                MetricNames.REQUESTS_TOTAL,
                labels={"method": method, "path": self._normalize_path(path)},
                service_id=service_id,
            )

            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Extract response info
            status_code = response.status_code
            content_type = response.headers.get("content-type", "")
            content_length = response.headers.get("content-length")

            # Log response body if enabled
            response_body = None
            if self.log_response_body and self._should_log_response_body(response):
                response_body = await self._get_response_body(response)

            # Log request end
            self.logger.log_request_end(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                service_id=service_id,
                metadata={
                    "request_id": request_id,
                    "content_type": content_type,
                    "content_length": content_length,
                    "response_body": response_body,
                },
            )

            # Record metrics
            self.metrics.record_timer(
                MetricNames.REQUEST_DURATION,
                duration_ms,
                service_id=service_id,
                labels={"method": method, "path": self._normalize_path(path)},
            )

            # Increment status counter
            self.metrics.increment_counter(
                MetricNames.REQUESTS_TOTAL,
                labels={
                    "method": method,
                    "path": self._normalize_path(path),
                    "status": str(status_code),
                },
                service_id=service_id,
            )

            # Record response size if available
            if content_length:
                try:
                    size_bytes = int(content_length)
                    self.metrics.record_histogram(
                        MetricNames.RESPONSE_SIZE,
                        size_bytes,
                        labels={"method": method, "path": self._normalize_path(path)},
                    )
                except ValueError:
                    pass

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            self.logger.error(
                f"Request processing error: {method} {path}",
                event_type=EventType.GATEWAY_ERROR,
                method=method,
                path=path,
                service_id=service_id,
                duration_ms=duration_ms,
                metadata={
                    "request_id": request_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            # Increment error counter
            self.metrics.increment_counter(
                "requests_errors_total",
                labels={
                    "method": method,
                    "path": self._normalize_path(path),
                    "error_type": type(e).__name__,
                },
                service_id=service_id,
            )

            # Re-raise the exception
            raise

        finally:
            # Clear request ID from context
            clear_request_id()

    def _should_exclude_path(self, path: str) -> bool:
        """Check if path should be excluded from logging."""
        return any(excluded in path for excluded in self.exclude_paths)

    def _get_or_generate_request_id(self, request: Request) -> str:
        """Get request ID from header or generate new one."""
        # Check for existing request ID in headers
        request_id = request.headers.get("x-request-id")
        if request_id:
            return request_id

        # Check if already set in context
        existing_id = get_request_id()
        if existing_id:
            return existing_id

        # Generate new request ID
        return f"req_{uuid.uuid4().hex[:12]}"

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to client address
        if hasattr(request, "client") and request.client:
            return request.client.host

        return "unknown"

    def _extract_service_id(self, request: Request) -> Optional[str]:
        """Extract service ID from request path."""
        path_parts = request.url.path.strip("/").split("/")

        # Check for /services/{serviceId}/... pattern
        if len(path_parts) >= 2 and path_parts[0] == "services":
            return path_parts[1]

        # Check for /v1/requests with serviceId in body (for dispatcher)
        if path_parts == ["v1", "requests"]:
            return "dispatcher"  # Special case for dispatcher endpoint

        return None

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (remove dynamic parts)."""
        path_parts = path.strip("/").split("/")

        # Replace service IDs with placeholder
        if len(path_parts) >= 2 and path_parts[0] == "services":
            path_parts[1] = "{serviceId}"

        # Replace other common dynamic parts
        normalized_parts = []
        for part in path_parts:
            # Replace UUIDs and IDs
            if len(part) > 10 and ("-" in part or part.isalnum()):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)

        return "/" + "/".join(normalized_parts) if normalized_parts else "/"

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """Get request body for logging."""
        try:
            body = await request.body()
            if len(body) <= self.max_body_size:
                # Try to decode as text
                try:
                    return body.decode("utf-8")
                except UnicodeDecodeError:
                    return f"<binary data, {len(body)} bytes>"
            else:
                return f"<body too large, {len(body)} bytes>"
        except Exception:
            return "<failed to read body>"

    def _should_log_response_body(self, response: Response) -> bool:
        """Check if response body should be logged."""
        content_type = response.headers.get("content-type", "")

        # Only log text-based responses
        text_types = ["application/json", "text/", "application/xml"]
        if not any(t in content_type for t in text_types):
            return False

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    return False
            except ValueError:
                pass

        return True

    async def _get_response_body(self, response: Response) -> Optional[str]:
        """Get response body for logging."""
        # Note: This is complex to implement without consuming the response body
        # For now, we'll skip response body logging to avoid issues
        # In a production system, you'd need to implement response body capture
        # during the response streaming process
        return None


def add_logging_middleware(app, **kwargs):
    """Add logging middleware to FastAPI app."""
    app.add_middleware(LoggingMiddleware, **kwargs)
    return app


# Example usage
if __name__ == "__main__":
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Create test app
    app = FastAPI()

    # Add logging middleware
    add_logging_middleware(app)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "Hello, World!"}

    @app.get("/services/{service_id}/test")
    async def service_endpoint(service_id: str):
        return {"service_id": service_id, "message": "Service endpoint"}

    # Test with client
    client = TestClient(app)

    print("Testing logging middleware...")

    # Test basic endpoint
    response = client.get("/test")
    print(f"Response: {response.status_code}")

    # Test service endpoint
    response = client.get("/services/ollama/test")
    print(f"Service response: {response.status_code}")

    # Test with custom request ID
    response = client.get("/test", headers={"X-Request-ID": "custom-req-123"})
    print(f"Custom request ID response: {response.status_code}")

    print("Logging middleware test completed!")
