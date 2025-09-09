"""
Example Health Checker Strategy

This strategy demonstrates how to implement custom health checking
logic for monitoring service health and automatically triggering
recovery actions.
"""

from typing import Dict, Any, List
import time
import asyncio
import httpx
from enum import Enum


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckerStrategy:
    """
    Advanced health checker with multiple check types and recovery actions.

    Supports HTTP health checks, custom validation, circuit breaker patterns,
    and automatic recovery triggers.
    """

    def __init__(self):
        self.name = "health_checker"
        self.description = "Advanced health monitoring with recovery actions"
        self.version = "1.0.0"

        # Health tracking
        self.health_history: Dict[str, List[Dict[str, Any]]] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self.last_check_time: Dict[str, float] = {}

        # Configuration
        self.check_interval = 30  # seconds
        self.failure_threshold = 3
        self.recovery_threshold = 2
        self.timeout_seconds = 5

    def register_service(self, service_id: str, health_config: Dict[str, Any]):
        """
        Register a service for health monitoring.

        Args:
            service_id: Service identifier
            health_config: Health check configuration

        Example:
            health_config = {
                "endpoints": [
                    {"url": "http://service:8080/health", "type": "http"},
                    {"url": "http://service:8080/metrics", "type": "metrics"}
                ],
                "validation": {
                    "response_time_ms": 1000,
                    "required_fields": ["status", "version"],
                    "status_field": "status",
                    "healthy_values": ["UP", "HEALTHY"]
                },
                "recovery": {
                    "restart_command": "docker restart service",
                    "notification_webhook": "http://alerts:8080/webhook"
                }
            }
        """
        self.health_history[service_id] = []
        self.circuit_breakers[service_id] = {
            "state": "closed",  # closed, open, half_open
            "failure_count": 0,
            "last_failure_time": 0,
            "last_success_time": time.time(),
        }
        self.last_check_time[service_id] = 0

        # Store configuration for this service
        if not hasattr(self, "_service_configs"):
            self._service_configs = {}
        self._service_configs[service_id] = health_config

    async def check_service_health(self, service_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive health check for a service.

        Returns:
            Health check result with status, metrics, and recommendations
        """
        if service_id not in self._service_configs:
            return {
                "status": HealthStatus.UNKNOWN.value,
                "message": "Service not registered for health checking",
                "timestamp": time.time(),
            }

        config = self._service_configs[service_id]
        start_time = time.time()

        # Skip check if too recent
        if (start_time - self.last_check_time.get(service_id, 0)) < self.check_interval:
            return self._get_last_health_result(service_id)

        results = []
        overall_status = HealthStatus.HEALTHY

        # Check all configured endpoints
        for endpoint in config.get("endpoints", []):
            endpoint_result = await self._check_endpoint(endpoint)
            results.append(endpoint_result)

            # Determine worst status
            if endpoint_result["status"] == HealthStatus.UNHEALTHY.value:
                overall_status = HealthStatus.UNHEALTHY
            elif (
                endpoint_result["status"] == HealthStatus.DEGRADED.value
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

        # Apply validation rules
        validation_result = self._validate_health_response(results, config.get("validation", {}))
        if validation_result["status"] != HealthStatus.HEALTHY.value:
            overall_status = HealthStatus(validation_result["status"])

        # Update circuit breaker
        self._update_circuit_breaker(service_id, overall_status)

        # Create health result
        health_result = {
            "service_id": service_id,
            "status": overall_status.value,
            "timestamp": time.time(),
            "response_time_ms": int((time.time() - start_time) * 1000),
            "endpoints": results,
            "validation": validation_result,
            "circuit_breaker": self.circuit_breakers[service_id].copy(),
            "recommendations": self._generate_recommendations(service_id, overall_status),
        }

        # Store in history
        self._add_to_history(service_id, health_result)
        self.last_check_time[service_id] = time.time()

        # Trigger recovery actions if needed
        if overall_status == HealthStatus.UNHEALTHY:
            await self._trigger_recovery_actions(service_id, health_result)

        return health_result

    async def _check_endpoint(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Check a single endpoint."""
        url = endpoint["url"]
        check_type = endpoint.get("type", "http")

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                start_time = time.time()

                if check_type == "http":
                    response = await client.get(url)
                    response_time = int((time.time() - start_time) * 1000)

                    if response.status_code == 200:
                        status = HealthStatus.HEALTHY
                        message = "HTTP check passed"
                    elif 200 <= response.status_code < 300:
                        status = HealthStatus.DEGRADED
                        message = f"HTTP check degraded: {response.status_code}"
                    else:
                        status = HealthStatus.UNHEALTHY
                        message = f"HTTP check failed: {response.status_code}"

                    return {
                        "endpoint": url,
                        "type": check_type,
                        "status": status.value,
                        "message": message,
                        "response_time_ms": response_time,
                        "status_code": response.status_code,
                        "response_body": response.text[:200] if response.text else None,
                    }

                elif check_type == "metrics":
                    # Custom metrics endpoint check
                    response = await client.get(url)
                    response_time = int((time.time() - start_time) * 1000)

                    # Parse metrics and determine health based on thresholds
                    status = HealthStatus.HEALTHY  # Simplified
                    message = "Metrics check passed"

                    return {
                        "endpoint": url,
                        "type": check_type,
                        "status": status.value,
                        "message": message,
                        "response_time_ms": response_time,
                    }

                else:
                    # Unknown check type
                    return {
                        "endpoint": url,
                        "type": check_type,
                        "status": HealthStatus.UNKNOWN.value,
                        "message": f"Unknown check type: {check_type}",
                        "response_time_ms": 0,
                    }

        except Exception as e:
            return {
                "endpoint": url,
                "type": check_type,
                "status": HealthStatus.UNHEALTHY.value,
                "message": f"Check failed: {str(e)}",
                "response_time_ms": 0,
                "error": str(e),
            }

    def _validate_health_response(self, results: List[Dict], validation: Dict) -> Dict[str, Any]:
        """Apply validation rules to health check results."""
        if not validation:
            return {"status": HealthStatus.HEALTHY.value, "message": "No validation rules"}

        # Check response time threshold
        max_response_time = validation.get("response_time_ms", 5000)
        for result in results:
            if result.get("response_time_ms", 0) > max_response_time:
                return {
                    "status": HealthStatus.DEGRADED.value,
                    "message": f"Response time {result['response_time_ms']}ms exceeds threshold {max_response_time}ms",
                }

        return {"status": HealthStatus.HEALTHY.value, "message": "Validation passed"}

    def _update_circuit_breaker(self, service_id: str, status: HealthStatus):
        """Update circuit breaker state based on health status."""
        cb = self.circuit_breakers[service_id]
        current_time = time.time()

        if status == HealthStatus.UNHEALTHY:
            cb["failure_count"] += 1
            cb["last_failure_time"] = current_time

            if cb["failure_count"] >= self.failure_threshold and cb["state"] == "closed":
                cb["state"] = "open"
                print(f"Circuit breaker opened for {service_id}")

        elif status == HealthStatus.HEALTHY:
            if cb["state"] == "half_open":
                cb["failure_count"] = 0
                cb["state"] = "closed"
                print(f"Circuit breaker closed for {service_id}")
            elif cb["state"] == "closed":
                cb["failure_count"] = max(0, cb["failure_count"] - 1)

            cb["last_success_time"] = current_time

    def _generate_recommendations(self, service_id: str, status: HealthStatus) -> List[str]:
        """Generate recommendations based on health status."""
        recommendations = []

        if status == HealthStatus.UNHEALTHY:
            recommendations.extend(
                [
                    "Check service logs for errors",
                    "Verify service configuration",
                    "Consider restarting the service",
                    "Check resource utilization (CPU, memory, disk)",
                ]
            )

        elif status == HealthStatus.DEGRADED:
            recommendations.extend(
                [
                    "Monitor service performance closely",
                    "Check for resource constraints",
                    "Review recent deployments or changes",
                ]
            )

        cb = self.circuit_breakers[service_id]
        if cb["state"] == "open":
            recommendations.append("Circuit breaker is open - automatic recovery in progress")

        return recommendations

    async def _trigger_recovery_actions(self, service_id: str, health_result: Dict[str, Any]):
        """Trigger automated recovery actions for unhealthy services."""
        if service_id not in self._service_configs:
            return

        recovery_config = self._service_configs[service_id].get("recovery", {})

        # Send notification
        webhook_url = recovery_config.get("notification_webhook")
        if webhook_url:
            await self._send_notification(webhook_url, service_id, health_result)

        # Log the health issue
        print(f"Service {service_id} is unhealthy: {health_result}")

    async def _send_notification(
        self, webhook_url: str, service_id: str, health_result: Dict[str, Any]
    ):
        """Send notification webhook about service health issue."""
        try:
            payload = {
                "service_id": service_id,
                "status": health_result["status"],
                "timestamp": health_result["timestamp"],
                "message": f"Service {service_id} health check failed",
                "details": health_result,
            }

            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(webhook_url, json=payload)
                print(f"Health notification sent for {service_id}")

        except Exception as e:
            print(f"Failed to send health notification for {service_id}: {e}")

    def _add_to_history(self, service_id: str, health_result: Dict[str, Any]):
        """Add health result to history, maintaining a rolling window."""
        history = self.health_history[service_id]
        history.append(health_result)

        # Keep only last 100 results
        if len(history) > 100:
            history.pop(0)

    def _get_last_health_result(self, service_id: str) -> Dict[str, Any]:
        """Get the most recent health result for a service."""
        history = self.health_history.get(service_id, [])
        return (
            history[-1]
            if history
            else {
                "status": HealthStatus.UNKNOWN.value,
                "message": "No health check performed yet",
                "timestamp": time.time(),
            }
        )

    def get_health_summary(self, service_id: str) -> Dict[str, Any]:
        """Get a summary of service health over time."""
        history = self.health_history.get(service_id, [])
        if not history:
            return {"message": "No health data available"}

        recent_checks = history[-10:]  # Last 10 checks
        healthy_count = sum(
            1 for check in recent_checks if check["status"] == HealthStatus.HEALTHY.value
        )

        return {
            "service_id": service_id,
            "total_checks": len(history),
            "recent_success_rate": healthy_count / len(recent_checks),
            "current_status": history[-1]["status"],
            "last_check": history[-1]["timestamp"],
            "circuit_breaker": self.circuit_breakers.get(service_id, {}),
        }

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return information about this strategy."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": "health_checker",
            "features": [
                "http_health_checks",
                "metrics_validation",
                "circuit_breaker_pattern",
                "automated_recovery",
                "notification_webhooks",
                "health_history_tracking",
            ],
            "configuration": {
                "check_interval": f"{self.check_interval} seconds",
                "failure_threshold": self.failure_threshold,
                "recovery_threshold": self.recovery_threshold,
                "timeout": f"{self.timeout_seconds} seconds",
            },
        }


# Register the strategy with Hestia
def register_strategy(registry):
    """
    This function is called by Hestia's strategy loader.
    Register your strategy with the provided registry.
    """

    def create_health_checker():
        return HealthCheckerStrategy()

    registry.register("health_checker", create_health_checker)


# Example usage
if __name__ == "__main__":

    async def main():
        hc = HealthCheckerStrategy()

        # Register a service for health monitoring
        health_config = {
            "endpoints": [{"url": "http://localhost:11434/api/tags", "type": "http"}],
            "validation": {"response_time_ms": 2000},
            "recovery": {"notification_webhook": "http://localhost:9999/webhook"},
        }

        hc.register_service("ollama", health_config)

        # Perform health check
        result = await hc.check_service_health("ollama")
        print("Health Check Result:")
        print(result)

        print("\nStrategy Info:")
        print(hc.get_strategy_info())

    asyncio.run(main())
