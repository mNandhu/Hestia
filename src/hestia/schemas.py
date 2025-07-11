"""
Pydantic models for API responses in Hestia.
"""

from typing import List, Dict, Any, Literal, Union

from pydantic import BaseModel


class NoRouteResponse(BaseModel):
    """Response when no route is found or strategy declines."""

    decision: Literal["no_route"]
    service: str
    reason: str
    context: Dict[str, Any]


class ProxyResponse(BaseModel):
    """Response for a 'hot' service that is ready to be proxied."""

    decision: Literal["proxy_request"]
    service: str
    reason: str
    target_url: str
    path: str


class ColdStartResponse(BaseModel):
    """Response when a service is cold and needs to be started."""

    decision: Literal["initiate_cold_start"]
    service: str
    reason: str
    target_url: str
    path: str
    next_steps: List[str]


# Union type for all possible response types
GatewayResponse = Union[NoRouteResponse, ProxyResponse, ColdStartResponse]
