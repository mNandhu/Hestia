from datetime import datetime, UTC
from sqlalchemy import Column, String, DateTime, Boolean, JSON
from .base import Base


class AuthKey(Base):
    __tablename__ = "auth_keys"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    hashed_key = Column(String, nullable=False)
    scopes = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    disabled = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<AuthKey(id='{self.id}', name='{self.name}', disabled={self.disabled})>"
