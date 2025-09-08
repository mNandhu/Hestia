from sqlalchemy import Column, String, DateTime, Enum, Integer
from .base import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(String, primary_key=True)
    service_id = Column(String, nullable=False)
    last_used_at = Column(DateTime, nullable=False)
    state = Column(
        Enum("hot", "cold", "starting", "stopping", name="activity_state"), nullable=False
    )
    idle_timeout_seconds = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Activity(id='{self.id}', service_id='{self.service_id}', state='{self.state}')>"
