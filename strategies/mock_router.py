"""
Mock routing strategy for testing purposes.
"""

from typing import Dict, Any, List


def decide_route(context: Dict[str, Any]) -> List[str]:
    """
    A simple mock routing decision function.

    Args:
        context: The request context provided by Hestia.

    Returns:
        A list of target URLs to proxy the request to.
    """
    print(f"Mock strategy received context: {context}")
    # For testing, just return the first configured host if available
    configured_hosts = context.get("configured_hosts", [])
    if configured_hosts:
        return [configured_hosts[0]["url"]]
    return []
