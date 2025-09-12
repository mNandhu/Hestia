"""
Structured Logging System for Hestia Gateway

Provides structured logging with request IDs, event tracking, and configurable
log levels for comprehensive observability and debugging.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union

# Context variable for tracking request ID across async operations
request_id_context: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class LogLevel(Enum):
    """Log levels for structured logging."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(Enum):
    """Event types for structured logging per FR-013."""

    # Request/Response events
    REQUEST_START = "request_start"
    REQUEST_END = "request_end"

    # Service lifecycle events
    SERVICE_START = "service_start"
    SERVICE_READY = "service_ready"
    SERVICE_STOP = "service_stop"
    SERVICE_ERROR = "service_error"
    SERVICE_STATE_CHANGE = "service_state_change"

    # Gateway events
    GATEWAY_START = "gateway_start"
    GATEWAY_STOP = "gateway_stop"
    GATEWAY_ERROR = "gateway_error"

    # Queue events
    REQUEST_QUEUED = "request_queued"
    REQUEST_DEQUEUED = "request_dequeued"
    QUEUE_TIMEOUT = "queue_timeout"

    # Proxy events
    PROXY_START = "proxy_start"
    PROXY_END = "proxy_end"
    PROXY_ERROR = "proxy_error"
    PROXY_RETRY = "proxy_retry"
    PROXY_FALLBACK = "proxy_fallback"
    PROXY_TERMINAL_ERROR = "proxy_terminal_error"

    # Strategy events
    STRATEGY_LOADED = "strategy_loaded"
    STRATEGY_ERROR = "strategy_error"

    # Health check events
    HEALTH_CHECK = "health_check"
    HEALTH_CHECK_FAILED = "health_check_failed"

    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"

    # Semaphore automation events
    SEMAPHORE_REQUEST = "semaphore_request"
    SEMAPHORE_RESPONSE = "semaphore_response"
    SEMAPHORE_ERROR = "semaphore_error"
    SEMAPHORE_TASK_START = "semaphore_task_start"
    SEMAPHORE_TASK_COMPLETE = "semaphore_task_complete"
    SEMAPHORE_TASK_TIMEOUT = "semaphore_task_timeout"


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log structure
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        request_id = request_id_context.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Add structured data if available
        if hasattr(record, "event_type"):
            log_entry["event_type"] = getattr(record, "event_type")

        if hasattr(record, "service_id"):
            log_entry["service_id"] = getattr(record, "service_id")

        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = getattr(record, "duration_ms")

        if hasattr(record, "status_code"):
            log_entry["status_code"] = getattr(record, "status_code")

        if hasattr(record, "method"):
            log_entry["method"] = getattr(record, "method")

        if hasattr(record, "path"):
            log_entry["path"] = getattr(record, "path")

        if hasattr(record, "user_id"):
            log_entry["user_id"] = getattr(record, "user_id")

        if hasattr(record, "metadata"):
            log_entry["metadata"] = getattr(record, "metadata")

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(getattr(record, "extra_fields"))

        return json.dumps(log_entry, default=str)


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that gracefully handles closed streams during shutdown."""

    def emit(self, record):
        """Emit a record, handling closed stream errors gracefully."""
        try:
            # Check if stream is still available before attempting to write
            if hasattr(self.stream, "closed") and self.stream.closed:
                return

            # Proceed with normal emission
            super().emit(record)
        except (ValueError, OSError, AttributeError) as e:
            # Handle cases where output streams are closed or unavailable
            error_msg = str(e).lower()
            if any(
                phrase in error_msg
                for phrase in ["closed file", "bad file descriptor", "i/o operation on closed file"]
            ):
                # Silently ignore logging to closed streams during shutdown
                return
            else:
                # Re-raise other exceptions that aren't stream closure related
                raise


class HestiaLogger:
    """Structured logger for Hestia Gateway."""

    def __init__(self, name: str = "hestia", level: LogLevel = LogLevel.INFO):
        """Initialize the structured logger."""
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create console handler with structured formatter using our safe handler
        handler = SafeStreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def set_level(self, level: LogLevel):
        """Set the logging level."""
        self.logger.setLevel(getattr(logging, level.value))

    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal method to log with structured data."""
        # Create log record
        extra = {}

        # Add structured fields
        if "event_type" in kwargs:
            extra["event_type"] = (
                kwargs.pop("event_type").value
                if isinstance(kwargs["event_type"], EventType)
                else kwargs.pop("event_type")
            )

        for field in [
            "service_id",
            "duration_ms",
            "status_code",
            "method",
            "path",
            "user_id",
            "metadata",
        ]:
            if field in kwargs:
                extra[field] = kwargs.pop(field)

        # Store any remaining fields as extra_fields
        if kwargs:
            extra["extra_fields"] = kwargs

        # Log the message with error handling for closed streams
        try:
            getattr(self.logger, level.value.lower())(message, extra=extra)
        except (ValueError, OSError) as e:
            # Handle cases where output streams are closed (e.g., during pytest shutdown)
            # This prevents "I/O operation on closed file" errors from background threads
            if "closed file" in str(e) or "Bad file descriptor" in str(e):
                # Silently ignore logging to closed streams during shutdown
                pass
            else:
                # Re-raise other ValueError/OSError exceptions that aren't stream-related
                raise

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def log_event(self, event_type: EventType, message: str, **kwargs):
        """Log a structured event."""
        self.info(message, event_type=event_type, **kwargs)

    def log_request_start(
        self,
        method: str,
        path: str,
        service_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ):
        """Log request start event."""
        self.log_event(
            EventType.REQUEST_START,
            f"{method} {path}",
            method=method,
            path=path,
            service_id=service_id,
            user_id=user_id,
            **kwargs,
        )

    def log_request_end(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        service_id: Optional[str] = None,
        **kwargs,
    ):
        """Log request end event."""
        self.log_event(
            EventType.REQUEST_END,
            f"{method} {path} - {status_code} ({duration_ms:.1f}ms)",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            service_id=service_id,
            **kwargs,
        )

    def log_service_start(self, service_id: str, **kwargs):
        """Log service start event."""
        self.log_event(
            EventType.SERVICE_START,
            f"Starting service: {service_id}",
            service_id=service_id,
            **kwargs,
        )

    def log_service_ready(self, service_id: str, duration_ms: Optional[float] = None, **kwargs):
        """Log service ready event."""
        message = f"Service ready: {service_id}"
        if duration_ms is not None:
            message += f" (startup took {duration_ms:.1f}ms)"

        self.log_event(
            EventType.SERVICE_READY,
            message,
            service_id=service_id,
            duration_ms=duration_ms,
            **kwargs,
        )

    def log_service_stop(self, service_id: str, reason: Optional[str] = None, **kwargs):
        """Log service stop event."""
        message = f"Service stopped: {service_id}"
        if reason:
            message += f" (reason: {reason})"

        # Merge metadata from kwargs
        base_meta = {"stop_reason": reason} if reason else {}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            if base_meta:
                base_meta.update(extra_meta)
            else:
                base_meta = extra_meta

        self.log_event(
            EventType.SERVICE_STOP,
            message,
            service_id=service_id,
            metadata=base_meta if base_meta else None,
            **kwargs,
        )

    def log_service_error(self, service_id: str, error: Union[str, Exception], **kwargs):
        """Log service error event."""
        error_msg = str(error)
        # Merge metadata
        base_meta = {"error": error_msg}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.SERVICE_ERROR,
            f"Service error: {service_id} - {error_msg}",
            service_id=service_id,
            metadata=base_meta,
            **kwargs,
        )

    def log_service_state_change(self, service_id: str, old_state: str, new_state: str, **kwargs):
        """Log service state change event."""
        # Merge metadata
        base_meta = {"old_state": old_state, "new_state": new_state}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.SERVICE_STATE_CHANGE,
            f"Service state change: {service_id} {old_state} -> {new_state}",
            service_id=service_id,
            metadata=base_meta,
            **kwargs,
        )

    def log_queue_event(
        self, event_type: EventType, service_id: str, queue_size: Optional[int] = None, **kwargs
    ):
        """Log queue-related event."""
        message = f"Queue {event_type.value}: {service_id}"
        if queue_size is not None:
            message += f" (queue size: {queue_size})"

        base_meta = {"queue_size": queue_size} if queue_size is not None else {}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            if base_meta:
                base_meta.update(extra_meta)
            else:
                base_meta = extra_meta

        self.log_event(
            event_type,
            message,
            service_id=service_id,
            metadata=base_meta if base_meta else None,
            **kwargs,
        )

    def log_proxy_start(self, service_id: str, target_url: str, method: str, path: str, **kwargs):
        """Log proxy start event."""
        base_meta = {"target_url": target_url}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.PROXY_START,
            f"Proxying {method} {path} to {target_url}",
            service_id=service_id,
            method=method,
            path=path,
            metadata=base_meta,
            **kwargs,
        )

    def log_proxy_end(
        self, service_id: str, target_url: str, status_code: int, duration_ms: float, **kwargs
    ):
        """Log proxy end event."""
        base_meta = {"target_url": target_url}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.PROXY_END,
            f"Proxy response from {target_url}: {status_code} ({duration_ms:.1f}ms)",
            service_id=service_id,
            status_code=status_code,
            duration_ms=duration_ms,
            metadata=base_meta,
            **kwargs,
        )

    def log_proxy_retry(
        self,
        service_id: str,
        target_url: str,
        attempt: int,
        max_attempts: int,
        error: str,
        **kwargs,
    ):
        """Log proxy retry attempt."""
        self.log_event(
            EventType.PROXY_RETRY,
            f"Retrying request to {target_url} (attempt {attempt + 1}/{max_attempts}): {error}",
            service_id=service_id,
            attempt=attempt + 1,
            max_attempts=max_attempts,
            target_url=target_url,
            error=error,
            **kwargs,
        )

    def log_proxy_fallback(
        self,
        service_id: str,
        primary_url: str,
        fallback_url: str,
        **kwargs,
    ):
        """Log fallback attempt after primary failed."""
        self.log_event(
            EventType.PROXY_FALLBACK,
            f"Primary endpoint {primary_url} failed, trying fallback {fallback_url}",
            service_id=service_id,
            primary_url=primary_url,
            fallback_url=fallback_url,
            **kwargs,
        )

    def log_proxy_terminal_error(
        self,
        service_id: str,
        attempted_urls: list[str],
        final_error: str,
        **kwargs,
    ):
        """Log terminal error when all endpoints failed."""
        self.log_event(
            EventType.PROXY_TERMINAL_ERROR,
            f"All endpoints failed for {service_id}: {attempted_urls} - {final_error}",
            service_id=service_id,
            attempted_urls=attempted_urls,
            final_error=final_error,
            **kwargs,
        )

    def log_health_check(
        self,
        service_id: str,
        url: str,
        status: str,
        response_time_ms: Optional[float] = None,
        **kwargs,
    ):
        """Log health check event."""
        message = f"Health check: {service_id} ({url}) - {status}"
        if response_time_ms is not None:
            message += f" ({response_time_ms:.1f}ms)"

        event_type = (
            EventType.HEALTH_CHECK if status == "healthy" else EventType.HEALTH_CHECK_FAILED
        )

        base_meta = {"health_url": url, "health_status": status}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            event_type,
            message,
            service_id=service_id,
            duration_ms=response_time_ms,
            metadata=base_meta,
            **kwargs,
        )

    def log_semaphore_request(
        self,
        action: str,
        service_id: str,
        machine_id: Optional[str] = None,
        url: Optional[str] = None,
        **kwargs,
    ):
        """Log Semaphore API request."""
        message = f"Semaphore {action} request for {service_id}"
        if machine_id:
            message += f" on {machine_id}"

        base_meta = {"action": action, "machine_id": machine_id, "url": url}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.SEMAPHORE_REQUEST,
            message,
            service_id=service_id,
            metadata=base_meta,
            **kwargs,
        )

    def log_semaphore_response(
        self,
        action: str,
        service_id: str,
        task_id: str,
        status: str,
        **kwargs,
    ):
        """Log Semaphore API response."""
        message = f"Semaphore {action} response for {service_id}: {status} (task {task_id})"

        base_meta = {"action": action, "task_id": task_id, "task_status": status}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.SEMAPHORE_RESPONSE,
            message,
            service_id=service_id,
            metadata=base_meta,
            **kwargs,
        )

    def log_semaphore_error(
        self,
        action: str,
        service_id: Optional[str] = None,
        task_id: Optional[str] = None,
        error: str = "",
        **kwargs,
    ):
        """Log Semaphore API error."""
        message = f"Semaphore {action} error"
        if service_id:
            message += f" for {service_id}"
        if task_id:
            message += f" (task {task_id})"
        if error:
            message += f": {error}"

        base_meta = {"action": action, "task_id": task_id, "error": error}
        extra_meta = kwargs.pop("metadata", None)
        if extra_meta:
            base_meta.update(extra_meta)

        self.log_event(
            EventType.SEMAPHORE_ERROR,
            message,
            service_id=service_id,
            metadata=base_meta,
            **kwargs,
        )


# Global logger instance
logger = HestiaLogger()


def get_logger(name: str = "hestia") -> HestiaLogger:
    """Get a logger instance."""
    if name == "hestia":
        return logger
    return HestiaLogger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set request ID in context. If not provided, generates a new one."""
    if request_id is None:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

    request_id_context.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_context.get()


def clear_request_id():
    """Clear request ID from context."""
    request_id_context.set(None)


class RequestTimer:
    """Context manager for timing requests."""

    def __init__(
        self, logger: HestiaLogger, method: str, path: str, service_id: Optional[str] = None
    ):
        self.logger = logger
        self.method = method
        self.path = path
        self.service_id = service_id
        self.start_time = None
        self.status_code = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.log_request_start(self.method, self.path, self.service_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            status_code = self.status_code or (500 if exc_type else 200)
            self.logger.log_request_end(
                self.method, self.path, status_code, duration_ms, self.service_id
            )

    def set_status_code(self, status_code: int):
        """Set the response status code."""
        self.status_code = status_code


def configure_logging(level: LogLevel = LogLevel.INFO, enable_debug: bool = False):
    """Configure global logging settings."""
    global logger

    if enable_debug:
        level = LogLevel.DEBUG

    logger.set_level(level)

    # Log configuration
    logger.info(
        "Logging configured",
        event_type=EventType.GATEWAY_START,
        metadata={"log_level": level.value, "debug_enabled": enable_debug},
    )


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    configure_logging(LogLevel.DEBUG)

    # Set a request ID
    req_id = set_request_id()
    print(f"Request ID: {req_id}")

    # Test various log events
    logger.info("Testing structured logging system")

    # Service events
    logger.log_service_start("ollama", metadata={"base_url": "http://localhost:11434"})
    logger.log_service_ready("ollama", duration_ms=1250.5)
    logger.log_service_state_change("ollama", "cold", "hot")

    # Request events with timer
    with RequestTimer(logger, "GET", "/v1/models", "ollama") as timer:
        time.sleep(0.01)  # Simulate work
        timer.set_status_code(200)

    # Queue events
    logger.log_queue_event(EventType.REQUEST_QUEUED, "ollama", queue_size=3)
    logger.log_queue_event(EventType.REQUEST_DEQUEUED, "ollama", queue_size=2)

    # Proxy events
    logger.log_proxy_start("ollama", "http://localhost:11434", "GET", "/api/tags")
    logger.log_proxy_end("ollama", "http://localhost:11434", 200, 45.2)

    # Health check
    logger.log_health_check("ollama", "http://localhost:11434/api/tags", "healthy", 23.1)

    # Error logging
    logger.log_service_error("ollama", "Connection refused")

    # Generic logging with custom fields
    logger.info(
        "Custom event",
        service_id="ollama",
        custom_field="custom_value",
        metadata={"additional": "data"},
    )

    print("\nStructured logging test completed!")
