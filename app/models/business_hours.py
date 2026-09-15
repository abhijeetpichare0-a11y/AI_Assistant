from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base


class BusinessHours(Base):
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    day = Column(String(20), nullable=False)  # Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
    opening_time = Column(String(10), nullable=True, default="10:00")  # HH:MM in 24h format
    closing_time = Column(String(10), nullable=True, default="20:00")  # HH:MM in 24h format
    is_open = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("Business", back_populates="business_hours")
