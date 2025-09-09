import pytest
import os
from datetime import datetime, UTC

from hestia.persistence import DatabaseManager, reset_database_for_testing, get_database_manager
from hestia.models import Service, Machine, Activity


def test_database_manager_initialization():
    """Test basic database manager initialization."""
    # Test with custom URL
    db_manager = DatabaseManager("sqlite:///:memory:")
    assert db_manager.database_url == "sqlite:///:memory:"
    assert db_manager.engine is not None
    assert db_manager.SessionLocal is not None

    # Initialize database
    db_manager.initialize_database()
    assert db_manager._initialized is True


def test_database_manager_session_context():
    """Test session context manager."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()

    # Test successful transaction
    with db_manager.get_session() as session:
        service = Service(
            id="test-service",
            name="Test Service",
            strategy="default",
            machine_selector="local",
            warmup_seconds=30,
        )
        session.add(service)
        # Commit happens automatically on context exit

    # Verify the service was saved
    with db_manager.get_session() as session:
        retrieved = session.query(Service).filter_by(id="test-service").first()
        assert retrieved is not None
        assert getattr(retrieved, "name") == "Test Service"


def test_database_manager_session_rollback():
    """Test session rollback on exception."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()

    # Test rollback on exception
    with pytest.raises(ValueError):
        with db_manager.get_session() as session:
            service = Service(
                id="test-service-2",
                name="Test Service 2",
                strategy="default",
                machine_selector="local",
                warmup_seconds=30,
            )
            session.add(service)
            # Force an exception before commit
            raise ValueError("Test exception")

    # Verify the service was not saved due to rollback
    with db_manager.get_session() as session:
        retrieved = session.query(Service).filter_by(id="test-service-2").first()
        assert retrieved is None


def test_database_manager_create_session():
    """Test manual session creation."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()

    session = db_manager.create_session()
    service = Service(
        id="manual-session-test",
        name="Manual Session Test",
        strategy="default",
        machine_selector="local",
        warmup_seconds=30,
    )
    session.add(service)
    session.commit()
    # Verify it was saved
    retrieved = session.query(Service).filter_by(id="manual-session-test").first()
    assert retrieved is not None
    assert getattr(retrieved, "name") == "Manual Session Test"
    session.close()


def test_database_manager_reset():
    """Test database reset functionality."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()

    # Add some data
    with db_manager.get_session() as session:
        service = Service(
            id="reset-test",
            name="Reset Test",
            strategy="default",
            machine_selector="local",
            warmup_seconds=30,
        )
        session.add(service)

    # Verify data exists
    with db_manager.get_session() as session:
        count = session.query(Service).count()
        assert count == 1

    # Reset database
    db_manager.reset_database()

    # Verify data is gone
    with db_manager.get_session() as session:
        count = session.query(Service).count()
        assert count == 0


def test_global_database_manager():
    """Test global database manager functions."""
    # Reset to clean state
    reset_database_for_testing()

    # Get global manager
    db_manager = get_database_manager()
    assert db_manager is not None
    assert db_manager.database_url == "sqlite:///:memory:"

    # Test that subsequent calls return the same instance
    db_manager2 = get_database_manager()
    assert db_manager is db_manager2


def test_testing_environment_detection(monkeypatch):
    """Test that TESTING=1 environment variable uses in-memory database."""
    monkeypatch.setenv("TESTING", "1")

    # Create new database manager
    db_manager = DatabaseManager()
    assert db_manager.database_url == "sqlite:///:memory:"


def test_production_database_url():
    """Test default database URL in production."""
    # Clear any testing environment variable
    if "TESTING" in os.environ:
        del os.environ["TESTING"]

    db_manager = DatabaseManager()
    assert db_manager.database_url == "sqlite:///hestia.db"


def test_sql_debug_mode(monkeypatch):
    """Test SQL debug mode activation."""
    monkeypatch.setenv("SQL_DEBUG", "1")

    db_manager = DatabaseManager("sqlite:///:memory:")
    # Engine should be created with echo=True when SQL_DEBUG=1
    assert db_manager.engine.echo is True


def test_persistence_with_models():
    """Test persistence layer with actual model operations."""
    reset_database_for_testing()
    db_manager = get_database_manager()

    # Create a service
    with db_manager.get_session() as session:
        service = Service(
            id="persistence-test",
            name="Persistence Test Service",
            strategy="test_strategy",
            machine_selector="local",
            health_endpoint="http://localhost:8080/health",
            warmup_seconds=60,
            auth_required=True,
        )
        session.add(service)

    # Create a machine
    with db_manager.get_session() as session:
        machine = Machine(
            id="test-machine",
            name="Test Machine",
            role="local",
            capabilities={"cpu": 8, "memory": "16GB"},
            address="localhost:8080",
            status="available",
        )
        session.add(machine)

    # Create an activity
    with db_manager.get_session() as session:
        activity = Activity(
            id="test-activity",
            service_id="persistence-test",
            last_used_at=datetime.now(UTC),
            state="hot",
            idle_timeout_seconds=300,
        )
        session.add(activity)

    # Verify all data was persisted
    with db_manager.get_session() as session:
        service = session.query(Service).filter_by(id="persistence-test").first()
        assert service is not None
        assert getattr(service, "name") == "Persistence Test Service"
        assert getattr(service, "auth_required") is True

    machine = session.query(Machine).filter_by(id="test-machine").first()
    assert machine is not None
    assert getattr(machine, "role") == "local"
    expected_capabilities = {"cpu": 8, "memory": "16GB"}
    assert getattr(machine, "capabilities") == expected_capabilities

    activity = session.query(Activity).filter_by(id="test-activity").first()
    assert activity is not None
    assert getattr(activity, "service_id") == "persistence-test"
    assert getattr(activity, "state") == "hot"
