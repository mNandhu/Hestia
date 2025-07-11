"""
Database management for Hestia.

This module handles the SQLite database connection, session management,
and provides models and functions for interacting with the application's state.
"""

import os
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from dotenv import load_dotenv

load_dotenv()  # TODO: Migrate to .ini based configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./hestia.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ServiceState(Base):
    """Represents the runtime state of a managed service."""

    __tablename__ = "service_states"

    name = Column(String, primary_key=True, index=True)
    status = Column(
        String, nullable=False, default="cold"
    )  # e.g., 'cold', 'hot', 'starting', 'stopping'
    active_host_url = Column(String, nullable=True)
    last_used = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def init_db():
    """
    Initializes the database and creates tables if they don't exist.
    This should be called on application startup.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection utility to get a database session.

    Yields:
        A SQLAlchemy Session object.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_service_state(db: Session, service_name: str) -> ServiceState | None:
    """
    Retrieves the current state of a service from the database.

    Args:
        db: The database session.
        service_name: The name of the service.

    Returns:
        The ServiceState object or None if not found.
    """
    return db.query(ServiceState).filter(ServiceState.name == service_name).first()  # type: ignore


def update_service_status(
    db: Session, service_name: str, status: str, active_host_url: str | None = None
) -> ServiceState:
    """
    Creates or updates the state of a service.

    Args:
        db: The database session.
        service_name: The name of the service to update.
        status: The new status for the service.
        active_host_url: The URL of the host if the service is active.

    Returns:
        The updated ServiceState object.
    """
    service_state = get_service_state(db, service_name)
    if not service_state:
        service_state = ServiceState(name=service_name)
        db.add(service_state)

    service_state.status = status  # type: ignore
    service_state.active_host_url = active_host_url  # type: ignore
    service_state.last_used = datetime.now(timezone.utc)  # type: ignore

    db.commit()
    db.refresh(service_state)
    return service_state
