"""
Example Load Balancer Strategy

This strategy demonstrates how to implement custom load balancing
logic for distributing requests across multiple service instances.
"""

from typing import List, Dict, Any, Optional
import time


class LoadBalancerStrategy:
    """
    Round-robin load balancer with health tracking.

    Distributes requests across multiple service instances,
    automatically removing unhealthy instances from rotation.
    """

    def __init__(self):
        self.name = "load_balancer"
        self.description = "Round-robin load balancer with health tracking"
        self.version = "1.0.0"

        # Track service instances and their health
        self.service_instances: Dict[str, List[Dict[str, Any]]] = {}
        self.current_index: Dict[str, int] = {}
        self.health_status: Dict[str, Dict[str, bool]] = {}
        self.last_health_check: Dict[str, Dict[str, float]] = {}

    def register_service_instances(self, service_id: str, instances: List[Dict[str, Any]]):
        """
        Register multiple instances for a service.

        Args:
            service_id: Service identifier
            instances: List of instance configs with 'url', 'weight', etc.

        Example:
            instances = [
                {"url": "http://ollama-1:11434", "weight": 1, "region": "us-east"},
                {"url": "http://ollama-2:11434", "weight": 2, "region": "us-west"},
                {"url": "http://ollama-3:11434", "weight": 1, "region": "eu-west"}
            ]
        """
        self.service_instances[service_id] = instances
        self.current_index[service_id] = 0
        self.health_status[service_id] = {instance["url"]: True for instance in instances}
        self.last_health_check[service_id] = {instance["url"]: 0 for instance in instances}

    def get_next_instance(
        self, service_id: str, request_context: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Get the next healthy instance URL using round-robin selection.

        Args:
            service_id: Service identifier
            request_context: Optional context (user location, request type, etc.)

        Returns:
            URL of the selected instance, or None if no healthy instances
        """
        if service_id not in self.service_instances:
            return None

        instances = self.service_instances[service_id]
        healthy_instances = [
            instance
            for instance in instances
            if self.health_status[service_id].get(instance["url"], True)
        ]

        if not healthy_instances:
            # No healthy instances, return the first one as fallback
            return instances[0]["url"] if instances else None

        # Apply regional preference if available in request context
        if request_context and "user_region" in request_context:
            user_region = request_context["user_region"]
            regional_instances = [
                instance for instance in healthy_instances if instance.get("region") == user_region
            ]
            if regional_instances:
                healthy_instances = regional_instances

        # Round-robin selection
        current_idx = self.current_index[service_id]
        selected_instance = healthy_instances[current_idx % len(healthy_instances)]

        # Update index for next request
        self.current_index[service_id] = (current_idx + 1) % len(healthy_instances)

        return selected_instance["url"]

    def mark_instance_unhealthy(self, service_id: str, instance_url: str, error: Exception):
        """Mark an instance as unhealthy after a failed request."""
        if service_id in self.health_status and instance_url in self.health_status[service_id]:
            self.health_status[service_id][instance_url] = False
            print(f"Marked {instance_url} as unhealthy for {service_id}: {error}")

    def mark_instance_healthy(self, service_id: str, instance_url: str):
        """Mark an instance as healthy after a successful request."""
        if service_id in self.health_status and instance_url in self.health_status[service_id]:
            self.health_status[service_id][instance_url] = True
            print(f"Marked {instance_url} as healthy for {service_id}")

    def should_check_health(
        self, service_id: str, instance_url: str, interval_seconds: int = 30
    ) -> bool:
        """Determine if an instance health should be checked."""
        if service_id not in self.last_health_check:
            return True

        last_check = self.last_health_check[service_id].get(instance_url, 0)
        return (time.time() - last_check) > interval_seconds

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return information about this strategy."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": "load_balancer",
            "features": [
                "round_robin_selection",
                "health_tracking",
                "regional_preference",
                "automatic_failover",
            ],
            "configuration": {
                "health_check_interval": "30 seconds",
                "selection_algorithm": "round_robin",
                "regional_awareness": "enabled",
            },
        }


# Register the strategy with Hestia
def register_strategy(registry):
    """
    This function is called by Hestia's strategy loader.
    Register your strategy with the provided registry.
    """

    def create_load_balancer():
        return LoadBalancerStrategy()

    registry.register("load_balancer", create_load_balancer)


# Example usage in application code:
if __name__ == "__main__":
    # Example of how this strategy might be used
    lb = LoadBalancerStrategy()

    # Register Ollama instances across regions
    ollama_instances = [
        {"url": "http://ollama-us-east:11434", "weight": 1, "region": "us-east"},
        {"url": "http://ollama-us-west:11434", "weight": 1, "region": "us-west"},
        {"url": "http://ollama-eu:11434", "weight": 1, "region": "eu-west"},
    ]
    lb.register_service_instances("ollama", ollama_instances)

    # Simulate requests
    for i in range(10):
        # Request from US user
        instance = lb.get_next_instance("ollama", {"user_region": "us-east"})
        print(f"Request {i + 1}: {instance}")

    print("\nStrategy Info:")
    print(lb.get_strategy_info())
