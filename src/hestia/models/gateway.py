"""
Request and response models for the gateway dispatcher API.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class GatewayRequest(BaseModel):
    """Request model for POST /v1/requests dispatcher endpoint."""

    service_id: str = Field(..., alias="serviceId", description="Target service identifier")
    method: str = Field(..., description="HTTP method (GET, POST, PUT, PATCH, DELETE)")
    path: str = Field(..., description="Path to proxy to on the target service")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers to forward")
    body: Optional[Any] = Field(default=None, description="Request body (JSON, string, or bytes)")

    model_config = ConfigDict(populate_by_name=True)


class GatewayResponse(BaseModel):
    """Response model for POST /v1/requests dispatcher endpoint."""

    status: int = Field(..., description="HTTP status code from target service")
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Response headers from target service"
    )
    body: Optional[Any] = Field(default=None, description="Response body from target service")


class ServiceStatus(BaseModel):
    """Response model for GET /v1/services/{serviceId}/status endpoint."""

    service_id: str = Field(..., alias="serviceId", description="Service identifier")
    state: str = Field(..., description="Service state: hot, cold, starting, stopping")
    machine_id: Optional[str] = Field(
        default=None, alias="machineId", description="Current machine hosting the service"
    )
    readiness: str = Field(..., description="Service readiness: ready, not_ready")
    queue_pending: Optional[int] = Field(
        default=None,
        alias="queuePending",
        description="Number of requests pending in queue for this service",
    )

    model_config = ConfigDict(populate_by_name=True)
