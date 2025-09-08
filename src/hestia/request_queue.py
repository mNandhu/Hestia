"""
Request queue for cold services.
Provides FIFO queuing with bounded size and per-service timeouts.
"""

import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from collections import deque


class QueueTimeoutError(Exception):
    """Raised when a request times out while queued."""

    pass


@dataclass
class QueuedRequest:
    """Represents a request waiting in the queue."""

    service_id: str
    request_data: Dict[str, Any]
    timeout_seconds: float
    future: asyncio.Future
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class RequestQueue:
    """Thread-safe request queue for cold services."""

    def __init__(self, max_queue_size: int = 100, default_timeout_seconds: int = 60):
        """Initialize request queue with configuration."""
        self.max_queue_size = max_queue_size
        self.default_timeout_seconds = default_timeout_seconds
        self._service_queues: Dict[str, deque] = {}
        self._lock = threading.RLock()
        self._startup_in_progress: Dict[str, bool] = {}

    async def queue_request(
        self, service_id: str, request_data: Dict[str, Any], timeout_seconds: Optional[float] = None
    ) -> asyncio.Future:
        """
        Queue a request for a service. Returns a future that will be resolved
        when the service is ready and the request can be processed.
        """
        if timeout_seconds is None:
            timeout_seconds = self.default_timeout_seconds

        with self._lock:
            # Check queue size limit
            if service_id in self._service_queues:
                if len(self._service_queues[service_id]) >= self.max_queue_size:
                    raise ValueError(
                        f"Queue for service {service_id} is full (max {self.max_queue_size})"
                    )
            else:
                self._service_queues[service_id] = deque()

            # Create future for this request
            future = asyncio.Future()

            # Create queued request
            queued_request = QueuedRequest(
                service_id=service_id,
                request_data=request_data,
                timeout_seconds=timeout_seconds,
                future=future,
                created_at=datetime.utcnow(),
            )

            # Add to queue
            self._service_queues[service_id].append(queued_request)

        # Set up timeout
        loop = asyncio.get_event_loop()
        timeout_handle = loop.call_later(
            timeout_seconds, self._timeout_request, service_id, future, timeout_seconds
        )

        # Clean up timeout handle when future completes
        future.add_done_callback(lambda f: timeout_handle.cancel())

        return future

    def _timeout_request(self, service_id: str, future: asyncio.Future, timeout_seconds: float):
        """Handle request timeout."""
        if not future.done():
            # Remove from queue
            with self._lock:
                if service_id in self._service_queues:
                    # Find and remove the timed out request
                    queue = self._service_queues[service_id]
                    for i, req in enumerate(queue):
                        if req.future is future:
                            del queue[i]
                            break

            # Set timeout exception
            future.set_exception(
                QueueTimeoutError(f"Request timed out after {timeout_seconds} seconds")
            )

    def process_next_request(self, service_id: str, response_data: Any) -> Optional[bool]:
        """
        Process the next request in queue for a service.
        Returns True if a request was processed, False if queue was empty, None if service doesn't exist.
        """
        with self._lock:
            if service_id not in self._service_queues or not self._service_queues[service_id]:
                return None if service_id not in self._service_queues else False

            # Get next request (FIFO)
            queued_request = self._service_queues[service_id].popleft()

            # Resolve the future with response data
            if not queued_request.future.done():
                queued_request.future.set_result(response_data)

            return True

    def process_all_requests(self, service_id: str, response_data: Any) -> int:
        """
        Process all queued requests for a service (when service becomes ready).
        Returns number of requests processed.
        """
        processed_count = 0
        while self.process_next_request(service_id, response_data):
            processed_count += 1
        return processed_count

    def get_queue_status(self, service_id: str) -> Dict[str, Any]:
        """Get status information for a service queue."""
        with self._lock:
            if service_id not in self._service_queues:
                pending_requests = 0
            else:
                pending_requests = len(self._service_queues[service_id])

            return {"pending_requests": pending_requests, "max_size": self.max_queue_size}

    def clear_queue(self, service_id: str) -> int:
        """
        Clear all requests for a service (e.g., on service failure).
        Returns number of requests cancelled.
        """
        with self._lock:
            if service_id not in self._service_queues:
                return 0

            queue = self._service_queues[service_id]
            cancelled_count = len(queue)

            # Cancel all futures
            while queue:
                queued_request = queue.popleft()
                if not queued_request.future.done():
                    queued_request.future.cancel()

            return cancelled_count

    def is_service_starting(self, service_id: str) -> bool:
        """Check if a service startup is already in progress."""
        with self._lock:
            return self._startup_in_progress.get(service_id, False)

    def mark_service_starting(self, service_id: str) -> bool:
        """
        Mark a service as starting to prevent duplicate startups.
        Returns True if successfully marked, False if already starting.
        """
        with self._lock:
            if self._startup_in_progress.get(service_id, False):
                return False

            self._startup_in_progress[service_id] = True
            return True

    def mark_service_ready(self, service_id: str):
        """Mark a service as ready (startup complete)."""
        with self._lock:
            self._startup_in_progress[service_id] = False

    def get_all_queue_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all service queues."""
        with self._lock:
            status = {}
            for service_id in self._service_queues:
                status[service_id] = self.get_queue_status(service_id)
            return status
