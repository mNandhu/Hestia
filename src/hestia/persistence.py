"""
Persistence provider for Hestia using SQLite.
Provides database engine, session management, and initialization.
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from hestia.models import Base


class DatabaseManager:
    """Manages SQLite database connection and sessions."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager with optional custom URL."""
        if database_url is None:
            # Default to hestia.db in current directory, or in-memory for tests
            if os.getenv("TESTING") == "1":
                database_url = "sqlite:///:memory:"
            else:
                database_url = "sqlite:///hestia.db"

        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            # SQLite-specific settings
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
            echo=os.getenv("SQL_DEBUG") == "1",  # Enable SQL logging in debug mode
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._initialized = False

    def initialize_database(self) -> None:
        """Create all tables if they don't exist."""
        if not self._initialized:
            Base.metadata.create_all(bind=self.engine)
            self._initialized = True

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_session(self) -> Session:
        """Create a new database session (caller responsible for cleanup)."""
        return self.SessionLocal()

    def reset_database(self) -> None:
        """Drop and recreate all tables (mainly for testing)."""
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._initialized = True

    def close(self) -> None:
        """Close the database engine."""
        self.engine.dispose()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize_database()
    return _db_manager


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for getting database sessions."""
    db_manager = get_database_manager()
    with db_manager.get_session() as session:
        yield session


def init_database(database_url: Optional[str] = None) -> None:
    """Initialize the database with optional custom URL."""
    global _db_manager
    _db_manager = DatabaseManager(database_url)
    _db_manager.initialize_database()


def reset_database_for_testing() -> None:
    """Reset database for testing (creates in-memory DB)."""
    global _db_manager
    _db_manager = DatabaseManager("sqlite:///:memory:")
    _db_manager.initialize_database()
