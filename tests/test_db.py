"""
Tests for the database module.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from hestia.db import (
    Base,
    ServiceState,
    get_service_state,
    update_service_status,
)


class TestDatabase:
    """Test database functionality."""

    @pytest.fixture
    def in_memory_db(self) -> Session:
        """Create an in-memory SQLite database for testing."""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()

    def test_service_state_creation(self, in_memory_db: Session) -> None:
        """Test creating a new ServiceState."""
        service_state = ServiceState(
            name="test_service", status="cold", active_host_url=None
        )
        in_memory_db.add(service_state)
        in_memory_db.commit()

        # Verify the service was created
        retrieved = (
            in_memory_db.query(ServiceState)
            .filter(ServiceState.name == "test_service")
            .first()
        )
        assert retrieved is not None
        assert getattr(retrieved, "name") == "test_service"
        assert getattr(retrieved, "status") == "cold"
        assert getattr(retrieved, "active_host_url") is None

    def test_get_service_state_existing(self, in_memory_db: Session) -> None:
        """Test retrieving an existing service state."""
        # Create a service state
        service_state = ServiceState(
            name="existing_service",
            status="hot",
            active_host_url="http://localhost:8001",
        )
        in_memory_db.add(service_state)
        in_memory_db.commit()

        # Retrieve it using the function
        retrieved = get_service_state(in_memory_db, "existing_service")
        assert retrieved is not None
        assert getattr(retrieved, "name") == "existing_service"
        assert getattr(retrieved, "status") == "hot"
        assert getattr(retrieved, "active_host_url") == "http://localhost:8001"

    def test_get_service_state_nonexistent(self, in_memory_db: Session) -> None:
        """Test retrieving a non-existent service state."""
        retrieved = get_service_state(in_memory_db, "nonexistent_service")
        assert retrieved is None

    def test_update_service_status_new_service(self, in_memory_db: Session) -> None:
        """Test updating status for a new service."""
        updated_state = update_service_status(
            in_memory_db, "new_service", "hot", "http://localhost:8002"
        )

        assert updated_state is not None
        assert getattr(updated_state, "name") == "new_service"
        assert getattr(updated_state, "status") == "hot"
        assert getattr(updated_state, "active_host_url") == "http://localhost:8002"
        assert getattr(updated_state, "last_used") is not None

    def test_update_service_status_existing_service(
        self, in_memory_db: Session
    ) -> None:
        """Test updating status for an existing service."""
        # Create initial service
        initial_state = update_service_status(
            in_memory_db, "existing_service", "cold", None
        )
        initial_last_used = getattr(initial_state, "last_used")

        # Update the service
        updated_state = update_service_status(
            in_memory_db, "existing_service", "hot", "http://localhost:8003"
        )

        assert getattr(updated_state, "name") == "existing_service"
        assert getattr(updated_state, "status") == "hot"
        assert getattr(updated_state, "active_host_url") == "http://localhost:8003"
        # last_used should be updated
        assert getattr(updated_state, "last_used") >= initial_last_used

    def test_update_service_status_without_host_url(
        self, in_memory_db: Session
    ) -> None:
        """Test updating service status without providing host URL."""
        updated_state = update_service_status(
            in_memory_db, "service_no_host", "starting"
        )

        assert getattr(updated_state, "name") == "service_no_host"
        assert getattr(updated_state, "status") == "starting"
        assert getattr(updated_state, "active_host_url") is None

    def test_service_state_timestamps(self, in_memory_db: Session) -> None:
        """Test that timestamps are properly set."""
        before_creation = datetime.now(timezone.utc)

        service_state = ServiceState(name="timestamp_test", status="cold")
        in_memory_db.add(service_state)
        in_memory_db.commit()
        in_memory_db.refresh(service_state)

        after_creation = datetime.now(timezone.utc)

        last_used = getattr(service_state, "last_used")
        updated_at = getattr(service_state, "updated_at")

        # Ensure the retrieved datetimes are timezone-aware for comparison
        if last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        assert before_creation <= last_used <= after_creation
        assert before_creation <= updated_at <= after_creation

    def test_multiple_services(self, in_memory_db: Session) -> None:
        """Test handling multiple services."""
        # Create multiple services
        services = ["service1", "service2", "service3"]
        for service_name in services:
            update_service_status(in_memory_db, service_name, "cold")

        # Verify all services exist
        for service_name in services:
            state = get_service_state(in_memory_db, service_name)
            assert state is not None
            assert getattr(state, "name") == service_name
            assert getattr(state, "status") == "cold"

    def test_service_state_status_transitions(self, in_memory_db: Session) -> None:
        """Test various status transitions."""
        service_name = "transition_test"

        # Start with cold
        state = update_service_status(in_memory_db, service_name, "cold")
        assert getattr(state, "status") == "cold"

        # Transition to starting
        state = update_service_status(
            in_memory_db, service_name, "starting", "http://localhost:8001"
        )
        assert getattr(state, "status") == "starting"
        assert getattr(state, "active_host_url") == "http://localhost:8001"

        # Transition to hot
        state = update_service_status(
            in_memory_db, service_name, "hot", "http://localhost:8001"
        )
        assert getattr(state, "status") == "hot"

        # Transition to stopping
        state = update_service_status(in_memory_db, service_name, "stopping")
        assert getattr(state, "status") == "stopping"

        # Back to cold
        state = update_service_status(in_memory_db, service_name, "cold")
        assert getattr(state, "status") == "cold"
