"""
Semaphore API client for remote service orchestration.

This module provides an HTTP client for interacting with Semaphore automation
server to start and stop services remotely.
"""

import asyncio
from typing import Dict, Optional, Any

import httpx
from pydantic import BaseModel

from .logging import get_logger


class SemaphoreTaskRequest(BaseModel):
    """Request model for Semaphore task creation."""

    project_id: int = 1
    template_id: int
    environment: Dict[str, str] = {}
    extra_vars: Dict[str, Any] = {}


class SemaphoreTaskResponse(BaseModel):
    """Response model for Semaphore task operations."""

    task_id: str
    status: str  # running, success, error
    message: Optional[str] = None


class SemaphoreClient:
    """
    HTTP client for Semaphore automation server.

    Provides methods to start/stop services and poll task status.
    """

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize Semaphore client.

        Args:
            base_url: Semaphore server URL (e.g., http://semaphore:3000)
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = get_logger("hestia.semaphore")

    async def start_service(
        self,
        service_id: str,
        machine_id: str,
        template_id: int = 1,
        environment: Optional[Dict[str, str]] = None,
    ) -> Optional[SemaphoreTaskResponse]:
        """
        Start a service via Semaphore.

        Args:
            service_id: Unique service identifier
            machine_id: Target machine/server identifier
            template_id: Semaphore template ID for start task
            environment: Additional environment variables

        Returns:
            Task response if successful, None if failed
        """
        url = f"{self.base_url}/api/project/1/tasks"

        # Prepare task payload
        env_vars = environment or {}
        env_vars.update({"SERVICE_ID": service_id, "MACHINE_ID": machine_id, "ACTION": "start"})

        payload = {
            "template_id": template_id,
            "environment": env_vars,
            "extra_vars": {"service_id": service_id, "machine_id": machine_id},
        }

        try:
            self.logger.log_semaphore_request(
                action="start_service", service_id=service_id, machine_id=machine_id, url=url
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                task_response = SemaphoreTaskResponse(
                    task_id=str(data.get("task_id", data.get("id"))),
                    status=data.get("status", "running"),
                    message=data.get("message"),
                )

                self.logger.log_semaphore_response(
                    action="start_service",
                    service_id=service_id,
                    task_id=task_response.task_id,
                    status=task_response.status,
                )

                return task_response

        except Exception as e:
            self.logger.log_semaphore_error(
                action="start_service", service_id=service_id, error=str(e)
            )
            return None

    async def stop_service(
        self,
        service_id: str,
        machine_id: str,
        template_id: int = 2,
        environment: Optional[Dict[str, str]] = None,
    ) -> Optional[SemaphoreTaskResponse]:
        """
        Stop a service via Semaphore.

        Args:
            service_id: Unique service identifier
            machine_id: Target machine/server identifier
            template_id: Semaphore template ID for stop task
            environment: Additional environment variables

        Returns:
            Task response if successful, None if failed
        """
        url = f"{self.base_url}/api/project/1/tasks"

        # Prepare task payload
        env_vars = environment or {}
        env_vars.update({"SERVICE_ID": service_id, "MACHINE_ID": machine_id, "ACTION": "stop"})

        payload = {
            "template_id": template_id,
            "environment": env_vars,
            "extra_vars": {"service_id": service_id, "machine_id": machine_id},
        }

        try:
            self.logger.log_semaphore_request(
                action="stop_service", service_id=service_id, machine_id=machine_id, url=url
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                task_response = SemaphoreTaskResponse(
                    task_id=str(data.get("task_id", data.get("id"))),
                    status=data.get("status", "running"),
                    message=data.get("message"),
                )

                self.logger.log_semaphore_response(
                    action="stop_service",
                    service_id=service_id,
                    task_id=task_response.task_id,
                    status=task_response.status,
                )

                return task_response

        except Exception as e:
            self.logger.log_semaphore_error(
                action="stop_service", service_id=service_id, error=str(e)
            )
            return None

    async def get_task_status(self, task_id: str) -> Optional[SemaphoreTaskResponse]:
        """
        Get status of a Semaphore task.

        Args:
            task_id: Task identifier returned from start/stop operations

        Returns:
            Task status if successful, None if failed
        """
        url = f"{self.base_url}/api/project/1/tasks/{task_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()
                return SemaphoreTaskResponse(
                    task_id=task_id,
                    status=data.get("status", "unknown"),
                    message=data.get("message"),
                )

        except Exception as e:
            self.logger.log_semaphore_error(action="get_task_status", task_id=task_id, error=str(e))
            return None

    async def wait_for_task_completion(
        self, task_id: str, timeout_seconds: int = 300, poll_interval: float = 2.0
    ) -> Optional[SemaphoreTaskResponse]:
        """
        Wait for a Semaphore task to complete.

        Args:
            task_id: Task identifier to monitor
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between status checks

        Returns:
            Final task status, or None if timeout/error
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check current time
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                self.logger.log_semaphore_error(
                    action="wait_for_task_completion",
                    task_id=task_id,
                    error=f"Timeout after {timeout_seconds}s",
                )
                return None

            # Get current status
            status_response = await self.get_task_status(task_id)
            if status_response is None:
                return None

            # Check if task is complete
            if status_response.status in ("success", "error", "failed"):
                return status_response

            # Wait before next poll
            await asyncio.sleep(poll_interval)


# Global client instance
_semaphore_client: Optional[SemaphoreClient] = None


def get_semaphore_client(base_url: Optional[str] = None) -> Optional[SemaphoreClient]:
    """
    Get global Semaphore client instance.

    Args:
        base_url: Semaphore server URL, if None uses environment variable

    Returns:
        Semaphore client instance, or None if not configured
    """
    global _semaphore_client

    if _semaphore_client is None and base_url:
        _semaphore_client = SemaphoreClient(base_url)

    return _semaphore_client


def reset_semaphore_client():
    """Reset the global Semaphore client (for testing)."""
    global _semaphore_client
    _semaphore_client = None
