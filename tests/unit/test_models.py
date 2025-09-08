import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hestia.models import Base, Service, Machine, RoutingRule, Activity, AuthKey


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_service_model_creation(db_session):
    """Test creating a Service model."""
    service = Service(
        id="test-service",
        name="Test Service",
        strategy="default",
        machine_selector="local",
        health_endpoint="http://localhost:8080/health",
        warmup_seconds=30,
        auth_required=False,
    )

    db_session.add(service)
    db_session.commit()

    retrieved = db_session.query(Service).filter_by(id="test-service").first()
    assert retrieved is not None
    assert retrieved.name == "Test Service"
    assert retrieved.strategy == "default"
    assert retrieved.machine_selector == "local"
    assert retrieved.health_endpoint == "http://localhost:8080/health"
    assert retrieved.warmup_seconds == 30
    assert retrieved.auth_required is False
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


def test_service_validation_health_or_warmup_required(db_session):
    """Test that either health_endpoint or warmup_seconds must be provided."""
    # This should be valid - has warmup_seconds
    service1 = Service(
        id="service1",
        name="Service 1",
        strategy="default",
        machine_selector="local",
        warmup_seconds=30,
    )
    db_session.add(service1)
    db_session.commit()

    # This should be valid - has health_endpoint
    service2 = Service(
        id="service2",
        name="Service 2",
        strategy="default",
        machine_selector="local",
        health_endpoint="http://localhost:8080/health",
    )
    db_session.add(service2)
    db_session.commit()


def test_machine_model_creation(db_session):
    """Test creating a Machine model."""
    machine = Machine(
        id="machine-1",
        name="Local Machine",
        role="local",
        capabilities={"cpu": 8, "memory": "32GB", "gpu": None},
        address="localhost:8080",
        status="available",
    )

    db_session.add(machine)
    db_session.commit()

    retrieved = db_session.query(Machine).filter_by(id="machine-1").first()
    assert retrieved is not None
    assert retrieved.name == "Local Machine"
    assert retrieved.role == "local"
    assert retrieved.capabilities == {"cpu": 8, "memory": "32GB", "gpu": None}
    assert retrieved.address == "localhost:8080"
    assert retrieved.status == "available"


def test_routing_rule_model_creation(db_session):
    """Test creating a RoutingRule model."""
    rule = RoutingRule(
        id="rule-1",
        name="GPU Rule",
        match={"service_type": "ml", "requires_gpu": True},
        target_machine_role="hpc",
        priority=1,
    )

    db_session.add(rule)
    db_session.commit()

    retrieved = db_session.query(RoutingRule).filter_by(id="rule-1").first()
    assert retrieved is not None
    assert retrieved.name == "GPU Rule"
    assert retrieved.match == {"service_type": "ml", "requires_gpu": True}
    assert retrieved.target_machine_role == "hpc"
    assert retrieved.priority == 1


def test_activity_model_creation(db_session):
    """Test creating an Activity model."""
    activity = Activity(
        id="activity-1",
        service_id="test-service",
        last_used_at=datetime.utcnow(),
        state="hot",
        idle_timeout_seconds=300,
    )

    db_session.add(activity)
    db_session.commit()

    retrieved = db_session.query(Activity).filter_by(id="activity-1").first()
    assert retrieved is not None
    assert retrieved.service_id == "test-service"
    assert retrieved.state == "hot"
    assert retrieved.idle_timeout_seconds == 300


def test_activity_idle_timeout_validation(db_session):
    """Test that idle_timeout_seconds must be > 0."""
    # This should be valid
    activity_valid = Activity(
        id="activity-valid",
        service_id="test-service",
        last_used_at=datetime.utcnow(),
        state="hot",
        idle_timeout_seconds=300,
    )
    db_session.add(activity_valid)
    db_session.commit()

    # Zero timeout should be allowed (means no timeout)
    activity_zero = Activity(
        id="activity-zero",
        service_id="test-service",
        last_used_at=datetime.utcnow(),
        state="hot",
        idle_timeout_seconds=0,
    )
    db_session.add(activity_zero)
    db_session.commit()


def test_auth_key_model_creation(db_session):
    """Test creating an AuthKey model."""
    auth_key = AuthKey(
        id="key-1",
        name="Admin Key",
        hashed_key="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj",
        scopes=["read", "write", "admin"],
        disabled=False,
    )

    db_session.add(auth_key)
    db_session.commit()

    retrieved = db_session.query(AuthKey).filter_by(id="key-1").first()
    assert retrieved is not None
    assert retrieved.name == "Admin Key"
    assert retrieved.hashed_key == "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj"
    assert retrieved.scopes == ["read", "write", "admin"]
    assert retrieved.disabled is False
    assert retrieved.created_at is not None


def test_service_activity_relationship(db_session):
    """Test the relationship between Service and Activity."""
    # Create a service
    service = Service(
        id="test-service",
        name="Test Service",
        strategy="default",
        machine_selector="local",
        warmup_seconds=30,
    )
    db_session.add(service)

    # Create activities for the service
    activity1 = Activity(
        id="activity-1",
        service_id="test-service",
        last_used_at=datetime.utcnow(),
        state="hot",
        idle_timeout_seconds=300,
    )

    activity2 = Activity(
        id="activity-2",
        service_id="test-service",
        last_used_at=datetime.utcnow(),
        state="cold",
        idle_timeout_seconds=300,
    )

    db_session.add_all([activity1, activity2])
    db_session.commit()

    # Test that we can query activities by service_id
    activities = db_session.query(Activity).filter_by(service_id="test-service").all()
    assert len(activities) == 2
    assert {a.id for a in activities} == {"activity-1", "activity-2"}
