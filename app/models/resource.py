from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class BusinessResource(Base):
    __tablename__ = "business_resources"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Hair Coloring Station 1", "Facial Room 1"
    resource_type = Column(String(100), nullable=False)  # e.g., "coloring_station", "facial_room", "spa_room", "nail_station"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="resources")
