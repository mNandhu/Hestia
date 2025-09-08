from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, JSON
from .base import Base


class Machine(Base):
    __tablename__ = "machines"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(Enum("local", "remote", "hpc", name="machine_role"), nullable=False)
    capabilities = Column(JSON, nullable=False, default=dict)
    address = Column(String, nullable=False)
    status = Column(Enum("available", "unavailable", name="machine_status"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Machine(id='{self.id}', name='{self.name}', role='{self.role}', status='{self.status}')>"
