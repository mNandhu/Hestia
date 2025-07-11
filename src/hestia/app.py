import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Union

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from hestia.config import load_config, AppConfig, ServiceConfig
from hestia.db import get_db, init_db, get_service_state, update_service_status
from hestia.schemas import NoRouteResponse, ProxyResponse, ColdStartResponse
from hestia.strategies import execute_strategy

# Load environment variables from .env file
load_dotenv()

# --- Globals ---
# Load application configuration
CONFIG_PATH = os.environ.get("HESTIA_CONFIG_PATH", "config/default_hestia_config.yml")
try:
    app_config: AppConfig = load_config(CONFIG_PATH)
except (FileNotFoundError, ValueError) as e:
    print(f"FATAL: Could not load configuration from '{CONFIG_PATH}'. Error: {e}")
    exit(1)


# --- App Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Only initialize database if not in test mode
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        print("Initializing database...")
        init_db()
        print("Database initialized.")
    yield
    print("Hestia is shutting down.")


app = FastAPI(
    title="Hestia - Programmable Gateway",
    description="A programmable, application-aware orchestration gateway.",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Dependencies ---
def get_app_config() -> AppConfig:
    """Dependency to get the application configuration."""
    return app_config


# --- API Endpoints ---
@app.get("/")
def index():
    """Root endpoint to check if the service is alive."""
    return {"status": "Hestia is alive"}


@app.api_route(
    "/api/{service_name}/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def gateway(
    request: Request,
    service_name: str,
    full_path: str,
    db: Session = Depends(get_db),
    config: AppConfig = Depends(get_app_config),
) -> Union[NoRouteResponse, ProxyResponse, ColdStartResponse]:
    """
    Main gateway endpoint for routing and orchestrating services.

    This endpoint performs the core decision-making logic without proxying
    the request in Phase 1.
    """
    # 1. Find the service configuration
    service_config: ServiceConfig | None = next(
        (s for s in config.services if s.name == service_name), None
    )
    if not service_config:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found in configuration.",
        )

    # 2. Get current service state from DB
    service_state = get_service_state(db, service_name)
    if not service_state:
        # First time seeing this service, create a default state
        service_state = update_service_status(db, service_name, "cold")

    # 3. Assemble context for the strategy
    context: Dict[str, Any] = {
        "request_headers": dict(request.headers),
        "request_method": request.method,
        "request_path": f"/{full_path}",
        "service_name": service_name,
        "current_status": service_state.status,
        "configured_hosts": [h.model_dump() for h in service_config.hosts],
        # In a real scenario, you might add more, like a cache of healthy hosts
    }

    # 4. Execute the routing strategy to get a decision
    try:
        # Construct absolute path for strategy script
        strategy_script_path = os.path.abspath(service_config.strategy)
        target_urls = execute_strategy(strategy_script_path, context)
    except (FileNotFoundError, AttributeError, Exception) as e:
        # TODO: Improve error handling and logging
        raise HTTPException(status_code=500, detail=f"Strategy execution failed: {e}")

    # 5. Determine action based on strategy outcome
    if not target_urls:
        # Strategy decided not to route, or no hosts available
        return NoRouteResponse(
            decision="no_route",
            service=service_name,
            reason="Strategy returned no target URLs.",
            context=context,
        )

    # This is the "hot path" decision
    service_status = getattr(service_state, "status")
    active_host = getattr(service_state, "active_host_url")

    if service_status == "hot" and active_host and active_host in target_urls:
        # The service is already running and the strategy agrees
        updated_state = update_service_status(
            db, service_name, "hot", active_host
        )  # Update last_used
        return ProxyResponse(
            decision="proxy_request",
            service=service_name,
            target_url=getattr(updated_state, "active_host_url", ""),
            path=full_path,
            reason="Service is hot and strategy selected the active host.",
        )

    # This is the "cold start" decision
    # For Phase 1, we just describe the action, not perform it.
    target_url = target_urls[0]  # Use the first URL from the strategy
    update_service_status(db, service_name, "starting", target_url)  # Tentative state
    return ColdStartResponse(
        decision="initiate_cold_start",
        service=service_name,
        target_url=target_url,
        path=full_path,
        reason="Service is cold or strategy chose a new host. Orchestration would be triggered.",
        next_steps=[
            f"Trigger task to start service on host for {target_url}",
            "Poll for service health at the target URL.",
            "Once healthy, update service state to 'hot'.",
            "Proxy the original request.",
        ],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=int(os.environ.get("PORT", 7777)), host="0.0.0.0")
