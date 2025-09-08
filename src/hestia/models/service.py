from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime
from .base import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    machine_selector = Column(String, nullable=False)
    health_endpoint = Column(String, nullable=True)
    warmup_seconds = Column(Integer, nullable=True)
    auth_required = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Service(id='{self.id}', name='{self.name}', strategy='{self.strategy}')>"
