from sqlalchemy import Column, String, Integer, JSON
from .base import Base


class RoutingRule(Base):
    __tablename__ = 'routing_rules'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    match = Column(JSON, nullable=False, default=dict)
    target_machine_role = Column(String, nullable=False)
    priority = Column(Integer, nullable=False)
    
    def __repr__(self):
        return f"<RoutingRule(id='{self.id}', name='{self.name}', priority={self.priority})>"