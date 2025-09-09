"""
Example Custom Routing Strategy

This strategy demonstrates how to implement custom routing logic
based on request characteristics, user attributes, or business rules.
"""

from typing import Dict, Any, List
import hashlib
import time


class CustomRoutingStrategy:
    """
    Custom routing strategy with multiple routing algorithms.

    Supports user-based routing, content-aware routing, time-based routing,
    and A/B testing scenarios.
    """

    def __init__(self):
        self.name = "custom_routing"
        self.description = "Flexible routing with multiple algorithms"
        self.version = "1.0.0"

        # Routing rules and configurations
        self.routing_rules: Dict[str, List[Dict[str, Any]]] = {}
        self.ab_test_configs: Dict[str, Dict[str, Any]] = {}
        self.user_preferences: Dict[str, Dict[str, str]] = {}

    def register_routing_rules(self, service_id: str, rules: List[Dict[str, Any]]):
        """
        Register routing rules for a service.

        Args:
            service_id: Service identifier
            rules: List of routing rules with conditions and targets

        Example:
            rules = [
                {
                    "name": "premium_users",
                    "condition": {"user_tier": "premium"},
                    "target": "http://premium-ollama:11434",
                    "weight": 100
                },
                {
                    "name": "geographic_routing",
                    "condition": {"user_region": "eu"},
                    "target": "http://eu-ollama:11434",
                    "weight": 100
                },
                {
                    "name": "model_specific",
                    "condition": {"model": "llama-70b"},
                    "target": "http://large-model-server:11434",
                    "weight": 100
                },
                {
                    "name": "default",
                    "condition": {},  # Always matches
                    "target": "http://default-ollama:11434",
                    "weight": 50
                }
            ]
        """
        self.routing_rules[service_id] = rules

    def setup_ab_test(self, service_id: str, test_config: Dict[str, Any]):
        """
        Set up A/B testing for a service.

        Args:
            service_id: Service identifier
            test_config: A/B test configuration

        Example:
            test_config = {
                "name": "new_model_test",
                "variants": [
                    {"name": "control", "target": "http://ollama-v1:11434", "traffic": 80},
                    {"name": "treatment", "target": "http://ollama-v2:11434", "traffic": 20}
                ],
                "user_assignment": "hash_based",  # or "random"
                "start_time": 1640995200,  # Unix timestamp
                "end_time": 1641600000,
                "metrics": ["response_time", "user_satisfaction"]
            }
        """
        self.ab_test_configs[service_id] = test_config

    def route_request(self, service_id: str, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a request based on custom logic.

        Args:
            service_id: Service identifier
            request_context: Request context with user info, request data, etc.

        Returns:
            Routing decision with target URL and metadata
        """
        # Check for active A/B tests first
        if service_id in self.ab_test_configs:
            ab_result = self._route_ab_test(service_id, request_context)
            if ab_result["routing_strategy"].startswith("ab_test") and not ab_result[
                "routing_strategy"
            ].endswith("_inactive"):
                return ab_result

        # Apply custom routing rules
        if service_id in self.routing_rules:
            return self._route_by_rules(service_id, request_context)

        # Fallback to default routing
        return {
            "target_url": "http://localhost:11434",  # Default
            "routing_strategy": "default_fallback",
            "metadata": {"reason": "No custom rules defined"},
        }

    def _route_ab_test(self, service_id: str, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """Route request based on A/B test configuration."""
        test_config = self.ab_test_configs[service_id]
        current_time = time.time()

        # Check if test is active
        if not (
            test_config.get("start_time", 0)
            <= current_time
            <= test_config.get("end_time", float("inf"))
        ):
            return {
                "target_url": "http://localhost:11434",
                "routing_strategy": "ab_test_inactive",
                "metadata": {"reason": "A/B test not currently active"},
            }

        # Determine user assignment
        user_id = request_context.get("user_id", "anonymous")
        assignment_method = test_config.get("user_assignment", "hash_based")

        if assignment_method == "hash_based":
            # Consistent assignment based on user ID
            hash_value = int(hashlib.md5(f"{user_id}_{service_id}".encode()).hexdigest(), 16)
            assignment_value = hash_value % 100
        else:
            # Random assignment (note: not truly random without seed management)
            assignment_value = hash(user_id) % 100

        # Select variant based on traffic allocation
        cumulative_traffic = 0
        for variant in test_config["variants"]:
            cumulative_traffic += variant["traffic"]
            if assignment_value < cumulative_traffic:
                return {
                    "target_url": variant["target"],
                    "routing_strategy": "ab_test",
                    "metadata": {
                        "test_name": test_config["name"],
                        "variant": variant["name"],
                        "assignment_value": assignment_value,
                    },
                }

        # Should not reach here with proper configuration
        return {
            "target_url": "http://localhost:11434",
            "routing_strategy": "ab_test_fallback",
            "metadata": {"reason": "No variant matched traffic allocation"},
        }

    def _route_by_rules(self, service_id: str, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """Route request based on custom rules."""
        rules = self.routing_rules[service_id]

        # Evaluate rules in order
        for rule in rules:
            if self._evaluate_condition(rule["condition"], request_context):
                return {
                    "target_url": rule["target"],
                    "routing_strategy": "rule_based",
                    "metadata": {
                        "rule_name": rule["name"],
                        "condition": rule["condition"],
                        "weight": rule.get("weight", 100),
                    },
                }

        # No rules matched
        return {
            "target_url": "http://localhost:11434",  # Default
            "routing_strategy": "default_fallback",
            "metadata": {"reason": "No rules matched"},
        }

    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate if a routing condition matches the request context."""
        if not condition:  # Empty condition always matches (default rule)
            return True

        for key, expected_value in condition.items():
            context_value = context.get(key)

            if isinstance(expected_value, list):
                # Check if context value is in the list
                if context_value not in expected_value:
                    return False
            elif isinstance(expected_value, dict):
                # Handle complex conditions (ranges, operators, etc.)
                if not self._evaluate_complex_condition(expected_value, context_value):
                    return False
            else:
                # Simple equality check
                if context_value != expected_value:
                    return False

        return True

    def _evaluate_complex_condition(self, condition: Dict[str, Any], value: Any) -> bool:
        """Evaluate complex conditions like ranges, operators, etc."""
        if "range" in condition:
            min_val, max_val = condition["range"]
            return min_val <= value <= max_val

        if "operator" in condition:
            op = condition["operator"]
            expected = condition["value"]

            if op == "gt":
                return value > expected
            elif op == "gte":
                return value >= expected
            elif op == "lt":
                return value < expected
            elif op == "lte":
                return value <= expected
            elif op == "contains":
                return expected in str(value)
            elif op == "regex":
                import re

                return bool(re.match(expected, str(value)))

        return False

    def get_user_routing_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get routing history for a specific user."""
        # In a real implementation, this would query a database or cache
        return [
            {
                "timestamp": time.time() - 3600,
                "service_id": "ollama",
                "target_url": "http://premium-ollama:11434",
                "strategy": "rule_based",
                "rule": "premium_users",
            }
        ]

    def get_routing_analytics(self, service_id: str) -> Dict[str, Any]:
        """Get analytics about routing decisions."""
        # In a real implementation, this would return actual metrics
        return {
            "service_id": service_id,
            "total_requests": 1000,
            "routing_breakdown": {"rule_based": 800, "ab_test": 150, "default_fallback": 50},
            "top_rules": [
                {"name": "premium_users", "requests": 300},
                {"name": "geographic_routing", "requests": 250},
                {"name": "model_specific", "requests": 200},
            ],
            "ab_test_performance": {
                "control": {"requests": 120, "avg_response_time": 250},
                "treatment": {"requests": 30, "avg_response_time": 180},
            },
        }

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return information about this strategy."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": "custom_routing",
            "features": [
                "rule_based_routing",
                "ab_testing",
                "user_based_routing",
                "geographic_routing",
                "model_aware_routing",
                "condition_evaluation",
                "routing_analytics",
            ],
            "supported_conditions": [
                "user_tier",
                "user_region",
                "model",
                "request_size",
                "time_of_day",
                "custom_headers",
                "ip_address",
            ],
            "operators": ["eq", "gt", "gte", "lt", "lte", "contains", "regex", "range"],
        }


# Register the strategy with Hestia
def register_strategy(registry):
    """
    This function is called by Hestia's strategy loader.
    Register your strategy with the provided registry.
    """

    def create_custom_routing():
        return CustomRoutingStrategy()

    registry.register("custom_routing", create_custom_routing)


# Example usage
if __name__ == "__main__":
    router = CustomRoutingStrategy()

    # Set up routing rules
    routing_rules = [
        {
            "name": "premium_users",
            "condition": {"user_tier": "premium"},
            "target": "http://premium-ollama:11434",
            "weight": 100,
        },
        {
            "name": "large_models",
            "condition": {"model": ["llama-70b", "gpt-4"]},
            "target": "http://gpu-cluster:11434",
            "weight": 100,
        },
        {"name": "default", "condition": {}, "target": "http://default-ollama:11434", "weight": 50},
    ]
    router.register_routing_rules("ollama", routing_rules)

    # Set up A/B test
    ab_test = {
        "name": "new_model_test",
        "variants": [
            {"name": "control", "target": "http://ollama-v1:11434", "traffic": 80},
            {"name": "treatment", "target": "http://ollama-v2:11434", "traffic": 20},
        ],
        "user_assignment": "hash_based",
        "start_time": time.time() - 3600,  # Started 1 hour ago
        "end_time": time.time() + 3600 * 24 * 7,  # Ends in 1 week
    }
    router.setup_ab_test("ollama", ab_test)

    # Test routing decisions
    test_contexts = [
        {"user_id": "user123", "user_tier": "premium", "model": "llama-7b"},
        {"user_id": "user456", "user_tier": "free", "model": "llama-70b"},
        {"user_id": "user789", "user_tier": "free", "model": "llama-7b"},
    ]

    print("Routing Decisions:")
    for i, context in enumerate(test_contexts):
        result = router.route_request("ollama", context)
        print(f"Request {i + 1}: {result}")

    print("\nStrategy Info:")
    print(router.get_strategy_info())
