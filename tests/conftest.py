"""
Test fixtures and configuration for Hestia tests.
"""

import pytest
from pathlib import Path
from typing import Generator, Any
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient
from unittest.mock import Mock

from hestia.db import Base, get_db
from hestia.app import app, get_app_config
from hestia.config import AppConfig, ServiceConfig, HostConfig, AppSettings


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Creates a temporary SQLite database for testing."""
    # Create in-memory SQLite database shared across connections/threads
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Store the session for later cleanup
    db_session = TestingSessionLocal()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass  # Don't close here, we'll do it later

    app.dependency_overrides[get_db] = override_get_db

    yield db_session

    # Clean up
    db_session.close()
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]


@pytest.fixture
def test_config() -> AppConfig:
    """Creates a test configuration."""
    return AppConfig(
        app=AppSettings(
            task_runner_api_url="http://test-server:8080/run",
            task_runner_api_key="test-secret-key",
            janitor_interval_seconds=300,
        ),
        services=[
            ServiceConfig(
                name="test_service",
                strategy="strategies/mock_router.py",
                hosts=[
                    HostConfig(
                        name="test_host_1",
                        url="http://localhost:8001",
                        metadata={"max_model_size_gb": 10},
                    ),
                    HostConfig(
                        name="test_host_2",
                        url="http://localhost:8002",
                        metadata={"max_model_size_gb": 20},
                    ),
                ],
            ),
            ServiceConfig(
                name="empty_service", strategy="strategies/empty_router.py", hosts=[]
            ),
        ],
    )


@pytest.fixture
def test_config_file(tmp_path: Path, test_config: AppConfig) -> str:
    """Creates a temporary config file."""
    config_file = tmp_path / "test_config.yml"
    config_data: dict[str, Any] = {
        "app": {
            "task_runner_api_url": test_config.app.task_runner_api_url,
            "task_runner_api_key": test_config.app.task_runner_api_key,
            "janitor_interval_seconds": test_config.app.janitor_interval_seconds,
        },
        "services": [],
    }

    for service in test_config.services:
        service_data: dict[str, Any] = {
            "name": service.name,
            "strategy": service.strategy,
            "hosts": [],
        }
        for host in service.hosts:
            host_data: dict[str, Any] = {
                "name": host.name,
                "url": host.url,
                "metadata": host.metadata,
            }
            service_data["hosts"].append(host_data)
        config_data["services"].append(service_data)

    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return str(config_file)


@pytest.fixture
def mock_strategy_file(tmp_path: Path) -> str:
    """Creates a mock strategy file for testing."""
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()

    mock_strategy = strategy_dir / "mock_router.py"
    mock_strategy.write_text("""
def decide_route(context):
    configured_hosts = context.get("configured_hosts", [])
    if configured_hosts:
        return [configured_hosts[0]["url"]]
    return []
""")

    empty_strategy = strategy_dir / "empty_router.py"
    empty_strategy.write_text("""
def decide_route(context):
    return []
""")

    return str(strategy_dir)


@pytest.fixture
def client(test_config: AppConfig) -> Generator[TestClient, None, None]:
    """Creates a test client with overridden dependencies."""

    def override_get_app_config() -> AppConfig:
        return test_config

    # Mock database functions to avoid real database interaction
    def mock_get_db() -> Generator[Mock, None, None]:
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        yield mock_session

    app.dependency_overrides[get_app_config] = override_get_app_config
    app.dependency_overrides[get_db] = mock_get_db

    with TestClient(app) as client:
        yield client

    # Clean up overrides
    if get_app_config in app.dependency_overrides:
        del app.dependency_overrides[get_app_config]
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]


@pytest.fixture
def client_with_db(
    test_db: Session, test_config: AppConfig
) -> Generator[TestClient, None, None]:
    """Creates a test client with real database for tests that need it."""

    def override_get_app_config() -> AppConfig:
        return test_config

    app.dependency_overrides[get_app_config] = override_get_app_config

    with TestClient(app) as client:
        yield client

    # Clean up overrides
    if get_app_config in app.dependency_overrides:
        del app.dependency_overrides[get_app_config]


@pytest.fixture
def mock_execute_strategy() -> Generator[Mock, None, None]:
    """Mock the execute_strategy function."""
    from unittest.mock import patch

    with patch("hestia.app.execute_strategy") as mock:
        yield mock
