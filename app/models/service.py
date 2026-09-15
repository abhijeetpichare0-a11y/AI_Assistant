from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.database.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(100), nullable=True)  # e.g., Hair, Skin, Spa, Nail, Grooming, Dental, Medical
    description = Column(String(255), nullable=True)
    duration_minutes = Column(Integer, default=30)
    price = Column(Numeric(10, 2), nullable=True)
    deposit_percentage = Column(Integer, default=0)  # e.g. 20 for Hair Coloring and Full Body Spa
    required_resource_type = Column(String(100), nullable=True)  # e.g. "coloring_station", "facial_room", "spa_room", "nail_station"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="services")
