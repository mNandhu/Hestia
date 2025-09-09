"""
Model-aware router strategy.

Selects upstream instance based on a mapping in service_config.routing["by_model"].
If not matched, delegates to load_balancer if available; otherwise returns None
so the caller can fallback to service_config.base_url.
"""

from typing import Any, Dict, Optional, Callable


class ModelRouterStrategy:
    name = "model_router"

    def __init__(self, load_balancer_factory: Optional[Callable[[], Any]] = None):
        # Lazy dependency to LB; not required, but useful for fallback
        self._get_lb = load_balancer_factory

    def route_request(
        self, service_id: str, request_context: Dict[str, Any], config: Any
    ) -> Optional[str]:
        routing = getattr(config, "routing", {}) or {}
        instances = getattr(config, "instances", []) or []

        # Determine key name for model
        model_key = routing.get("model_key", "model")
        model_value = request_context.get(model_key) or request_context.get("model")
        by_model: Dict[str, str] = routing.get("by_model", {}) or {}

        # Prefer explicit by_model mapping
        if model_value and model_value in by_model:
            return by_model[model_value]

        # No explicit mapping; delegate to LB if instances configured
        if instances and self._get_lb:
            try:
                lb = self._get_lb()
                # Ensure service instances are registered
                if hasattr(lb, "register_service_instances"):
                    lb.register_service_instances(service_id, instances)
                if hasattr(lb, "get_next_instance"):
                    return lb.get_next_instance(service_id, request_context)
            except Exception:
                return None

        return None


def register_strategy(registry):
    # capture registry to get LB on demand
    lb_factory = None

    def get_lb():
        nonlocal lb_factory
        if lb_factory is None:
            try:
                lb_factory = registry.get_strategy("load_balancer")
            except Exception:
                return None
        return lb_factory()

    def create_model_router():
        return ModelRouterStrategy(load_balancer_factory=get_lb)

    registry.register("model_router", create_model_router)
